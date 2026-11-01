"""Trusted migration battery, no application runtime bearer or retained SQL-only documents."""

import json
import logging
import multiprocessing
import re
from pathlib import Path
from queue import Empty
from uuid import UUID, uuid4

import sqlalchemy as sa
from f01_admin import DAY_ACTOR
from f01_daily import session
from f02_common import engine
from f03_fixtures import ROOT, snapshot
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from rag_platform.control.models import DbLocation, Instance, ProvisioningOperation, Tenant
from rag_platform.documents.migrations import apply_documents, migrate_documents_controlled
from rag_platform.documents.schema import VERSION
from rag_platform.documents.schema_f03_0002 import build_metadata
from rag_platform.provisioning.migration_control import migrate_controlled
from rag_platform.provisioning.migrations import MigrationError, migration_session
from rag_platform.provisioning.postgres import Names, Target
from rag_platform.tenancy.contracts import SecretRef
from rag_platform.tenancy.resolver import AdministrativeTenant, CatalogResolver, TenantAccessError

CA = Path("/run/f01-ca.crt")


class ProbeFailure(RuntimeError):
    pass


def denied(c, statement, values=None, expected="42501"):
    try:
        with c.begin_nested():
            c.execute(sa.text(statement), values or {})
    except sa.exc.DBAPIError as error:
        if getattr(error.orig, "sqlstate", None) == expected:
            return
        raise ProbeFailure("WRONG_SQL_DENIAL") from None
    raise ProbeFailure("SQL_UNEXPECTEDLY_ALLOWED")


def connection_engine(target, names, credential):
    return sa.create_engine(
        "postgresql+psycopg://",
        creator=lambda: target.connect(names.database, credential),
        poolclass=NullPool,
        hide_parameters=True,
    )


def lock_contender(host, port, names, credential, output):
    try:
        output.put("ATTEMPTING_LOCK")
        with migration_session(Target(host, port, CA), names, credential) as c:
            apply_documents(c, names, ROOT)
        output.put("UNEXPECTED_SUCCESS")
    except MigrationError as error:
        output.put(error.code)
    except Exception:
        output.put("UNEXPECTED_FAILURE")


def lock_probe(target, names, credential):
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    process = context.Process(
        target=lock_contender, args=(target.host, target.port, names, credential, queue)
    )
    outcome = "START_TIMEOUT"
    try:
        with migration_session(target, names, credential):
            process.start()
            try:
                started = queue.get(timeout=45)
            except Empty:
                started = None
            if started == "ATTEMPTING_LOCK":
                try:
                    outcome = queue.get(timeout=20)
                except Empty:
                    outcome = "RESULT_TIMEOUT"
            process.join(5)
        if outcome != "MIGRATION_BUSY":
            allowed = {
                "UNEXPECTED_SUCCESS",
                "UNEXPECTED_FAILURE",
                "MIGRATION_FAILED",
                "IDENTITY_CONFLICT",
                "VERSION_MISMATCH",
                "START_TIMEOUT",
                "RESULT_TIMEOUT",
            }
            raise ProbeFailure("LOCK_" + (outcome if outcome in allowed else "NOT_ENFORCED"))
    finally:
        if process.is_alive():
            process.terminate()
            process.join(5)
        queue.close()
        process.close()


def fresh_ddl_probe(target, names, credential):
    translated = {name: "f03_replay_" + name for name in ("knowledge", "security", "ops")}
    completed = False
    try:
        with migration_session(target, names, credential) as c:
            for temporary in translated.values():
                if (
                    c.scalar(sa.text("SELECT to_regnamespace(:name)"), {"name": temporary})
                    is not None
                ):
                    raise ProbeFailure("REPLAY_SCHEMA_CONFLICT")
                c.exec_driver_sql("CREATE SCHEMA " + temporary)
            build_metadata().create_all(
                c.execution_options(schema_translate_map=translated), checkfirst=False
            )
            completed = True
            raise MigrationError()
    except MigrationError:
        if not completed:
            raise ProbeFailure("FRESH_DDL_FAILED") from None
    with migration_session(target, names, credential) as c:
        for temporary in translated.values():
            if c.scalar(sa.text("SELECT to_regnamespace(:name)"), {"name": temporary}) is not None:
                raise ProbeFailure("REPLAY_DDL_RETAINED")
        if c.scalar(sa.text("SELECT version_num FROM public.alembic_version_tenant")) != VERSION:
            raise ProbeFailure("REPLAY_CHANGED_VERSION")


def sql_probe(target, names, app, readonly):
    app_engine = connection_engine(target, names, app)
    read_engine = connection_engine(target, names, readonly)
    try:
        with app_engine.connect() as c:
            # Everything inserted in these probes is rolled back. No RECEIVED metadata
            # survives without an S3 original, no SQL-only synthetic document is published.
            baseline_documents = c.scalar(sa.text("SELECT count(*) FROM knowledge.documents"))
            actor, repo_a, repo_b = uuid4(), uuid4(), uuid4()
            first_name = "A-" + uuid4().hex
            for repo, name in ((repo_a, first_name), (repo_b, "B-" + uuid4().hex)):
                c.execute(
                    sa.text(
                        "INSERT INTO knowledge.repositories(id,name,owner_id) "
                        "VALUES (:id,:name,:actor)"
                    ),
                    {"id": repo, "name": name, "actor": actor},
                )
                c.execute(
                    sa.text(
                        "INSERT INTO security.repository_acl"
                        "(repository_id,principal_id,role) VALUES (:repo,:actor,'owner')"
                    ),
                    {"repo": repo, "actor": actor},
                )
            source_a, source_b = uuid4(), uuid4()
            for source, repo in ((source_a, repo_a), (source_b, repo_b)):
                c.execute(
                    sa.text(
                        "INSERT INTO knowledge.sources(id,repository_id,created_by) "
                        "VALUES (:id,:repo,:actor)"
                    ),
                    {"id": source, "repo": repo, "actor": actor},
                )
            doc, version = uuid4(), uuid4()
            c.execute(
                sa.text(
                    "INSERT INTO knowledge.documents(id,repository_id,source_id,current_version_id,"
                    "created_by) VALUES (:doc,:repo,:source,:version,:actor)"
                ),
                {
                    "doc": doc,
                    "repo": repo_a,
                    "source": source_a,
                    "version": version,
                    "actor": actor,
                },
            )
            base = {
                "id": version,
                "doc": doc,
                "repo": repo_a,
                "filename": "synthetic.txt",
                "mime": "text/plain",
                "size": 5,
                "hash": "a" * 64,
                "key": f"f03/{repo_a.hex}/{version.hex}",
            }
            insert = (
                "INSERT INTO knowledge.document_versions(id,document_id,repository_id,"
                "filename,mime,byte_size,content_hash,blob_key) "
                "VALUES (:id,:doc,:repo,:filename,:mime,:size,:hash,:key)"
            )
            c.execute(sa.text(insert), base)
            c.execute(sa.text("SET CONSTRAINTS ALL IMMEDIATE"))
            denied(
                c,
                "INSERT INTO knowledge.documents(id,repository_id,source_id,"
                "current_version_id,created_by) VALUES (:id,:repo,:source,:version,:actor)",
                {
                    "id": uuid4(),
                    "repo": repo_a,
                    "source": source_b,
                    "version": version,
                    "actor": actor,
                },
                "23503",
            )
            denied(
                c,
                "INSERT INTO knowledge.documents(id,repository_id,source_id,"
                "current_version_id,created_by) VALUES (:id,:repo,:source,:version,:actor)",
                {
                    "id": uuid4(),
                    "repo": repo_b,
                    "source": source_b,
                    "version": version,
                    "actor": actor,
                },
                "23503",
            )
            foreign_version = uuid4()
            denied(
                c,
                insert,
                {
                    **base,
                    "id": foreign_version,
                    "repo": repo_b,
                    "key": f"f03/{repo_b.hex}/{foreign_version.hex}",
                },
                "23503",
            )
            for changes in (
                {"filename": "../escape.txt"},
                {"filename": "line\nbreak.txt"},
                {"mime": "application/x-executable"},
                {"size": 0},
                {"size": 1073741825},
                {"hash": "not-a-hash"},
                {"key": "foreign/owned-by-another-repository"},
            ):
                identity = uuid4()
                values = {
                    **base,
                    "id": identity,
                    "key": f"f03/{repo_a.hex}/{identity.hex}",
                    **changes,
                }
                denied(c, insert, values, "23514")
            for config in (
                '{"language":null}',
                '{"language":"auto","secret":"x"}',
                '{"language":"../../other"}',
            ):
                denied(
                    c,
                    "UPDATE knowledge.repositories SET config=CAST(:value AS jsonb) WHERE id=:id",
                    {"value": config, "id": repo_a},
                    "23514",
                )
            denied(
                c,
                "UPDATE knowledge.repositories SET name=E'bad\\nname' WHERE id=:id",
                {"id": repo_a},
                "23514",
            )
            denied(
                c,
                "UPDATE knowledge.repositories SET name=:name WHERE id=:id",
                {"id": repo_b, "name": first_name.lower()},
                "23505",
            )
            denied(
                c,
                "UPDATE security.repository_acl SET role='root' WHERE repository_id=:repo",
                {"repo": repo_a},
                "23514",
            )
            receipt = {
                "id": uuid4(),
                "repo": repo_a,
                "actor": actor,
                "key": "synthetic-idempotency-key",
                "hash": "b" * 64,
                "doc": uuid4(),
                "version": uuid4(),
                "attempt": uuid4(),
            }
            receipt_sql = (
                "INSERT INTO ops.document_receipts(id,repository_id,principal_id,idempotency_key,"
                "fingerprint,candidate_document_id,version_id,"
                "byte_size,state,attempt_id,lease_until) "
                "VALUES (:id,:repo,:actor,:key,:hash,:doc,:version,5,'PENDING',:attempt,"
                "CURRENT_TIMESTAMP+interval '1 minute')"
            )
            c.execute(sa.text(receipt_sql), receipt)
            denied(
                c,
                receipt_sql,
                {**receipt, "id": uuid4(), "doc": uuid4(), "version": uuid4()},
                "23505",
            )
            denied(
                c,
                "UPDATE ops.document_receipts SET state='COMMITTED',lease_until=NULL WHERE id=:id",
                {"id": receipt["id"]},
                "23514",
            )
            denied(
                c,
                "UPDATE ops.document_receipts SET committed_version_id=:version,"
                "state='COMMITTED',lease_until=NULL,version_id=:version WHERE id=:id",
                {"id": receipt["id"], "version": version},
                "23503",
            )
            denied(
                c,
                "UPDATE ops.document_receipts SET lease_until=NULL WHERE id=:id",
                {"id": receipt["id"]},
                "23514",
            )
            for statement in (
                "CREATE TABLE knowledge.f03_forbidden(x integer)",
                "SELECT * FROM public.ops_identity",
                "SELECT * FROM public.alembic_version_tenant",
                "DELETE FROM knowledge.repositories WHERE false",
                "UPDATE knowledge.document_versions SET filename='changed.txt' WHERE false",
                "UPDATE ops.audit_events SET outcome='OK' WHERE false",
            ):
                denied(c, statement)
            if (
                c.scalar(sa.text("SELECT count(*) FROM knowledge.documents"))
                != baseline_documents + 1
            ):
                raise ProbeFailure("OWN_CRUD")
            c.rollback()
        with read_engine.connect() as c:
            if c.scalar(sa.text("SELECT count(*) FROM knowledge.documents")) != baseline_documents:
                raise ProbeFailure("PROBE_NOT_ROLLED_BACK")
            for statement in (
                "INSERT INTO knowledge.repositories(id,name,owner_id) VALUES "
                "(gen_random_uuid(),'forbidden',gen_random_uuid())",
                "DELETE FROM security.repository_acl WHERE false",
                "SELECT * FROM ops.document_receipts",
                "CREATE TABLE knowledge.f03_forbidden(x integer)",
            ):
                denied(c, statement)
    finally:
        app_engine.dispose()
        read_engine.dispose()


def prove():
    control = engine("migrator")
    stage = "CATALOG"
    try:
        scope = json.loads((ROOT / "ops/f03/application-scope.json").read_text())
        with session() as (store, _, _):
            before = snapshot(control)
            for fixture in scope["fixtures"]:
                tag = fixture["name"].upper().replace("-", "_")
                stage = tag + "/CATALOG"
                tenant_id = UUID(fixture["tenant"])
                with Session(control) as catalog:
                    location = catalog.get(DbLocation, tenant_id)
                    instance = catalog.get(Instance, location.instance_id)
                    operation = catalog.scalar(
                        sa.select(ProvisioningOperation).where(
                            ProvisioningOperation.tenant_id == tenant_id
                        )
                    )
                    names = Names(tenant_id, operation.id)
                    target = Target(instance.host, instance.port, CA)
                    refs = [
                        SecretRef(
                            getattr(location, role + "_secret_ref"),
                            getattr(location, role + "_secret_version"),
                        )
                        for role in ("migrator", "app", "readonly")
                    ]
                migrator, app, readonly = (store.read(ref) for ref in refs)
                stage = tag + "/MIGRATE"
                for _ in range(2):
                    if (
                        migrate_documents_controlled(control, tenant_id, DAY_ACTOR, store, CA, ROOT)
                        != VERSION
                    ):
                        raise ProbeFailure("VERSION_NOT_PUBLISHED")
                stage = tag + "/RESOLVE"
                resolved = CatalogResolver(control, profile="documents").resolve(
                    AdministrativeTenant(tenant_id)
                )
                if resolved.host != target.host or resolved.role != "app":
                    raise ProbeFailure("WRONG_DESTINATION")
                try:
                    CatalogResolver(control).resolve(AdministrativeTenant(tenant_id))
                except TenantAccessError as error:
                    if error.code != "SCHEMA_INCOMPATIBLE":
                        raise ProbeFailure("WRONG_PROFILE_DENIAL") from None
                else:
                    raise ProbeFailure("BASELINE_ACCEPTED_NEW_SCHEMA")
                stage = tag + "/FRESH_DDL"
                fresh_ddl_probe(target, names, migrator)
                stage = tag + "/SQL"
                sql_probe(target, names, app, readonly)
                stage = tag + "/ROLLBACK"

                def failed_ddl(target, names, credential, repository):
                    with migration_session(target, names, credential) as c:
                        c.exec_driver_sql("CREATE TABLE ops.f03_rollback_probe(x integer)")
                        c.exec_driver_sql("SELECT 1/0")

                try:
                    migrate_controlled(
                        control,
                        tenant_id,
                        DAY_ACTOR,
                        store,
                        CA,
                        ROOT,
                        runner=failed_ddl,
                        profile="documents",
                    )
                except MigrationError:
                    pass
                else:
                    raise ProbeFailure("DDL_FAILURE_ACCEPTED")
                with Session(control) as catalog:
                    row = catalog.get(Tenant, tenant_id)
                    if (row.state, row.migration_state, row.observed_version) != (
                        "FAILED",
                        "MIGRATION_FAILED",
                        None,
                    ):
                        raise ProbeFailure("FALSE_READY")
                with migration_session(target, names, migrator) as c:
                    if (
                        c.scalar(sa.text("SELECT to_regclass('ops.f03_rollback_probe')"))
                        is not None
                    ):
                        raise ProbeFailure("DDL_NOT_ROLLED_BACK")
                migrate_documents_controlled(control, tenant_id, DAY_ACTOR, store, CA, ROOT)
                stage = tag + "/LOCK"
                lock_probe(target, names, migrator)
                stage = tag
                print(
                    f"PASS F03 SCHEMA {stage}: versión real/repetible; constraints y roles mínimos."
                )
                print(
                    f"PASS F03 SCHEMA {stage}: DDL revertido; FAILED sin versión falsa; lock real."
                )
            if snapshot(control) != before:
                raise ProbeFailure("LEGACY_CHANGED")
        print(
            "PASS F03 SCHEMA: cuatro fixtures; catálogo previo intacto; probes sin datos retenidos."
        )
    except (Exception, KeyboardInterrupt) as error:
        allowed = {
            "REPLAY_SCHEMA_CONFLICT",
            "FRESH_DDL_FAILED",
            "REPLAY_DDL_RETAINED",
            "REPLAY_CHANGED_VERSION",
            "WRONG_SQL_DENIAL",
            "SQL_UNEXPECTEDLY_ALLOWED",
            "LOCK_NOT_ENFORCED",
            "LOCK_UNEXPECTED_SUCCESS",
            "LOCK_UNEXPECTED_FAILURE",
            "LOCK_MIGRATION_FAILED",
            "LOCK_IDENTITY_CONFLICT",
            "LOCK_VERSION_MISMATCH",
            "LOCK_TIMEOUT",
            "LOCK_START_TIMEOUT",
            "LOCK_RESULT_TIMEOUT",
            "OWN_CRUD",
            "PROBE_NOT_ROLLED_BACK",
            "VERSION_NOT_PUBLISHED",
            "WRONG_DESTINATION",
            "WRONG_PROFILE_DENIAL",
            "BASELINE_ACCEPTED_NEW_SCHEMA",
            "DDL_FAILURE_ACCEPTED",
            "FALSE_READY",
            "DDL_NOT_ROLLED_BACK",
            "LEGACY_CHANGED",
        }
        code = (
            str(error) if isinstance(error, ProbeFailure) and str(error) in allowed else "REFUSED"
        )
        if isinstance(error, MigrationError):
            code = error.code
        state = getattr(getattr(error, "orig", error), "sqlstate", None)
        if isinstance(state, str) and re.fullmatch("[A-Z0-9]{5}", state):
            code = "SQLSTATE_" + state
        raise SystemExit(f"F03 SCHEMA {stage}: {code}; sin detalles sensibles.") from None
    finally:
        control.dispose()


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    prove()
