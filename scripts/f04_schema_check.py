"""Trusted SQL-only F04 schema probes; every tenant transaction is rolled back."""

import hashlib
import json
import logging
import re
from pathlib import Path
from uuid import UUID, uuid4, uuid5

import sqlalchemy as sa
from f02_common import credential, engine
from sqlalchemy.pool import NullPool

from rag_platform.control.identity_models import IdentityBase
from rag_platform.control.models import Base, DbLocation, Instance, ProvisioningOperation, Tenant
from rag_platform.documents.schema_f03_0002 import build_metadata as original_metadata
from rag_platform.identity_api import private_file
from rag_platform.ingestion.extraction import (
    CHUNKER,
    NORMALIZER,
    PARSERS,
    ChunkConfig,
    from_wire,
)
from rag_platform.ingestion.extraction import (
    chunks as make_chunks,
)
from rag_platform.ingestion.logging_setup import SETTINGS, apply_role_logging, local_private_logging
from rag_platform.ingestion.migrations import apply_ingestion
from rag_platform.ingestion.schema import (
    VERSION,
    audit,
    blocks,
    chunks,
    documents,
    intents,
    versions,
)
from rag_platform.providers.secrets import Credential
from rag_platform.provisioning.migrations import MigrationError
from rag_platform.provisioning.postgres import Names, Target

ROOT = Path(__file__).resolve().parents[1]
CA = Path("/run/f01-ca.crt")
PHASE = "START"


def fingerprint(connection, tables):
    result = {}
    for table in tables:
        rows = connection.execute(sa.select(*table.c)).all()
        encoded = sorted(json.dumps(list(row), default=str, sort_keys=True) for row in rows)
        result[table.fullname] = hashlib.sha256("".join(encoded).encode()).hexdigest()
    return result


def role(connection, names, kind):
    connection.exec_driver_sql("RESET ROLE")
    if kind is not None:
        quote = connection.dialect.identifier_preparer.quote
        connection.exec_driver_sql("SET LOCAL ROLE " + quote(names.role(kind)))


def denied(connection, statement, expected="23514"):
    try:
        with connection.begin_nested():
            if callable(statement):
                statement()
            else:
                connection.execute(statement)
    except sa.exc.DBAPIError as error:
        state = getattr(error.orig, "sqlstate", None)
        if state != expected:
            raise RuntimeError("WRONG_SQL_DENIAL") from None
    else:
        raise RuntimeError("UNEXPECTED_SQL_SUCCESS")


def fixture(c):
    actor, repo, source, doc, raw = (uuid4() for _ in range(5))
    body = b"F04 SQL rollback fixture, not an S3 original."
    c.execute(
        sa.text("INSERT INTO knowledge.repositories(id,name,owner_id) VALUES(:id,:name,:actor)"),
        {"id": repo, "name": "F04-schema-" + repo.hex, "actor": actor},
    )
    c.execute(
        sa.text(
            "INSERT INTO security.repository_acl(repository_id,principal_id,role) "
            "VALUES(:repo,:actor,'owner')"
        ),
        {"repo": repo, "actor": actor},
    )
    c.execute(
        sa.text(
            "INSERT INTO knowledge.sources(id,repository_id,created_by) VALUES(:id,:repo,:actor)"
        ),
        {"id": source, "repo": repo, "actor": actor},
    )
    c.execute(
        sa.insert(documents).values(
            id=doc, repository_id=repo, source_id=source, current_version_id=raw, created_by=actor
        )
    )
    c.execute(
        sa.insert(versions).values(
            id=raw,
            document_id=doc,
            repository_id=repo,
            filename="rollback.txt",
            mime="text/plain",
            byte_size=len(body),
            content_hash=hashlib.sha256(body).hexdigest(),
            blob_key="f03/" + repo.hex + "/" + raw.hex,
        )
    )
    return {"actor": actor, "repo": repo, "doc": doc, "raw": raw, "body": body}


def candidate(c, f, **changes):
    config = ChunkConfig(128, 32)
    values = {
        "id": uuid4(),
        "document_id": f["doc"],
        "repository_id": f["repo"],
        "filename": "rollback.txt",
        "mime": "text/plain",
        "byte_size": len(f["body"]),
        "content_hash": hashlib.sha256(f["body"]).hexdigest(),
        "blob_key": None,
        "kind": "PROCESSED",
        "original_version_id": f["raw"],
        "processing_actor_id": f["actor"],
        "parser_id": PARSERS["text/plain"],
        "normalizer_id": NORMALIZER,
        "chunker_id": CHUNKER,
        "config_hash": config.fingerprint("text/plain"),
        "chunk_size": config.size,
        "chunk_overlap": config.overlap,
    }
    values.update(changes)
    c.execute(sa.insert(versions).values(**values))
    return values["id"], config


def parsed():
    # SQL-only data, never committed or claimed as extraction from S3.
    text1 = "F04_SQL_PRIVATE_CANARY SELECT a, b FROM tabla; parámetro.\n" * 5
    text2 = "F04_SQL_PRIVATE_CANARY segunda sección con procedencia.\n" * 3
    return from_wire(
        {
            "version": 1,
            "parser": PARSERS["text/plain"],
            "normalizer": NORMALIZER,
            "page_count": None,
            "blocks": [
                {"text": text1, "page": None, "section": ["Uno"], "kind": "text"},
                {"text": text2, "page": None, "section": ["Dos"], "kind": "text"},
            ],
        },
        "text/plain",
    )


def block_rows(f, version, data):
    return [
        {
            "version_id": version,
            "document_id": f["doc"],
            "repository_id": f["repo"],
            "ordinal": b.ordinal,
            "start_offset": b.start,
            "end_offset": b.end,
            "text": b.text,
            "page": b.page,
            "section": list(b.section),
            "kind": b.kind,
        }
        for b in data.blocks
    ]


def chunk_rows(f, version, data, config):
    result = []
    for item in make_chunks(data, config):
        block = data.blocks[item.block_ordinal]
        result.append(
            {
                "id": uuid5(version, str(item.ordinal)),
                "version_id": version,
                "document_id": f["doc"],
                "repository_id": f["repo"],
                "ordinal": item.ordinal,
                "block_ordinal": item.block_ordinal,
                "block_start": block.start,
                "block_end": block.end,
                "start_offset": item.start,
                "end_offset": item.end,
                "text": item.text,
                "content_hash": item.content_hash,
                "page": item.page,
                "section": list(item.section),
                "kind": item.kind,
            }
        )
    return result


def stage(c, f, *, partial=False):
    version, config = candidate(c, f)
    c.execute(sa.update(versions).where(versions.c.id == version).values(state="CHUNKING"))
    data = parsed()
    c.execute(sa.insert(blocks), block_rows(f, version, data)[: 1 if partial else None])
    rows = chunk_rows(f, version, data, config)
    c.execute(sa.insert(chunks), rows[: 1 if partial else None])
    return version, config, data, rows


def complete(version, data, rows, **changes):
    values = {
        "state": "READY_FOR_EMBEDDING",
        "normalized_hash": hashlib.sha256(data.text.encode()).hexdigest(),
        "character_count": len(data.text),
        "page_count": data.page_count,
        "block_count": len(data.blocks),
        "chunk_count": len(rows),
        "completed_at": sa.func.clock_timestamp(),
    }
    values.update(changes)
    return sa.update(versions).where(versions.c.id == version).values(**values)


def frame(c, operation):
    with c.begin_nested() as savepoint:
        f = fixture(c)
        operation(f)
        savepoint.rollback()


def probes(c, names):
    global PHASE
    PHASE = "ORIGINAL"

    def original(f):
        denied(c, sa.update(versions).where(versions.c.id == f["raw"]).values(state="RECEIVED"))
        denied(
            c,
            sa.update(versions).where(versions.c.id == f["raw"]).values(filename="changed.txt"),
            "42501",
        )
        version, _ = candidate(c, f)
        denied(c, lambda: candidate(c, f), "23505")
        denied(
            c,
            sa.insert(versions).values(
                id=uuid4(),
                document_id=f["doc"],
                repository_id=f["repo"],
                filename="rollback.txt",
                mime="text/plain",
                byte_size=len(f["body"]),
                content_hash=hashlib.sha256(f["body"]).hexdigest(),
                blob_key=None,
                kind="PROCESSED",
                original_version_id=version,
                processing_actor_id=f["actor"],
                parser_id=PARSERS["text/plain"],
                normalizer_id=NORMALIZER,
                chunker_id=CHUNKER,
                config_hash="1" * 64,
                chunk_size=128,
                chunk_overlap=32,
            ),
            "23503",
        )
        denied(
            c,
            sa.insert(intents).values(
                id=uuid4(),
                version_id=version,
                document_id=f["doc"],
                repository_id=f["repo"],
                actor_id=uuid4(),
            ),
            "23503",
        )
        c.execute(
            sa.insert(intents).values(
                id=uuid4(),
                version_id=version,
                document_id=f["doc"],
                repository_id=f["repo"],
                actor_id=f["actor"],
            )
        )
        denied(
            c,
            sa.update(intents).where(intents.c.version_id == version).values(actor_id=uuid4()),
            "42501",
        )

    frame(c, original)

    PHASE = "PARTIAL"

    def partial(f):
        version, _config, data, rows = stage(c, f, partial=True)
        denied(c, complete(version, data, rows))
        assert c.scalar(sa.select(versions.c.state).where(versions.c.id == version)) == "CHUNKING"

    frame(c, partial)

    PHASE = "PROVENANCE"

    def provenance(f):
        version, config = candidate(c, f)
        c.execute(sa.update(versions).where(versions.c.id == version).values(state="CHUNKING"))
        data = parsed()
        c.execute(sa.insert(blocks), block_rows(f, version, data))
        row = chunk_rows(f, version, data, config)[0]
        for changes in (
            {"text": "incorrect", "content_hash": hashlib.sha256(b"incorrect").hexdigest()},
            {"content_hash": "0" * 64},
            {"page": 2},
            {"section": ["invented"]},
            {"repository_id": uuid4()},
        ):
            denied(c, sa.insert(chunks).values(**(row | changes)))
        complete_rows = chunk_rows(f, version, data, config)
        c.execute(sa.insert(chunks), complete_rows)
        denied(c, sa.insert(chunks).values(**complete_rows[0]), "23505")
        denied(
            c,
            complete(version, data, chunk_rows(f, version, data, config), normalized_hash="0" * 64),
        )

    frame(c, provenance)

    PHASE = "AUDIT"

    def missing_audit(f):
        version, _config, data, rows = stage(c, f)
        c.execute(complete(version, data, rows))
        denied(c, sa.text("SET CONSTRAINTS ALL IMMEDIATE"))
        c.exec_driver_sql("SET CONSTRAINTS ALL DEFERRED")

    frame(c, missing_audit)

    PHASE = "READY"

    def ready(f):
        version, _config, data, rows = stage(c, f)
        c.execute(complete(version, data, rows))
        c.execute(
            sa.insert(audit).values(
                id=uuid4(),
                principal_id=f["actor"],
                repository_id=f["repo"],
                target_id=version,
                request_id=uuid4(),
                action="INGESTION_READY",
                outcome="OK",
            )
        )
        c.exec_driver_sql("SET CONSTRAINTS ALL IMMEDIATE")
        c.exec_driver_sql("SET CONSTRAINTS ALL DEFERRED")
        assert (
            c.scalar(sa.select(versions.c.state).where(versions.c.id == version))
            == "READY_FOR_EMBEDDING"
        )
        denied(
            c,
            sa.update(versions)
            .where(versions.c.id == version)
            .values(error_code="PROCESSING_FAILED"),
        )
        extra = block_rows(f, version, data)[0] | {"ordinal": 100}
        denied(c, sa.insert(blocks).values(**extra))
        role(c, names, "readonly")
        assert c.scalar(sa.select(sa.func.count()).select_from(chunks)) >= len(rows)
        denied(c, sa.insert(chunks).values(**rows[0]), "42501")
        denied(c, sa.select(intents), "42501")
        denied(c, sa.text("SELECT * FROM public.ops_identity"), "42501")
        role(c, names, "app")

    frame(c, ready)

    PHASE = "TOMBSTONE"

    def tombstone(f):
        version, _config, data, rows = stage(c, f)
        c.execute(
            sa.update(documents)
            .where(documents.c.id == f["doc"])
            .values(
                state="TOMBSTONED",
                tombstoned_at=sa.func.clock_timestamp(),
                tombstoned_by=f["actor"],
            )
        )
        denied(c, complete(version, data, rows))

    frame(c, tombstone)

    PHASE = "ACL"

    def revoked(f):
        version, _config, data, rows = stage(c, f)
        c.execute(
            sa.text(
                "DELETE FROM security.repository_acl WHERE repository_id=:repo "
                "AND principal_id=:actor"
            ),
            {"repo": f["repo"], "actor": f["actor"]},
        )
        denied(c, complete(version, data, rows))

    frame(c, revoked)


def role_configuration(c, names):
    return {
        kind: c.scalar(
            sa.text("SELECT rolconfig FROM pg_roles WHERE rolname=:name"),
            {"name": names.role(kind)},
        )
        for kind in ("app", "readonly", "migrator")
    }


def prove_tenant(target, names, bootstrap):
    global PHASE
    e = sa.create_engine(
        "postgresql+psycopg://",
        creator=lambda: target.connect(names.database, bootstrap),
        poolclass=NullPool,
        hide_parameters=True,
    )
    tables = list(original_metadata().tables.values())
    try:
        PHASE = "TENANT_CONNECT"
        with e.connect() as c:
            transaction = c.begin()
            try:
                PHASE = "LOCAL_PRIVACY"
                local_private_logging(c)
                c.exec_driver_sql(
                    "DO $probe$ BEGIN RAISE LOG 'F04_SQL_LOG_PROBE_ACTIVE_V1'; END $probe$"
                )
                PHASE = "TENANT_SNAPSHOT"
                before = fingerprint(c, tables)
                original = c.scalar(
                    sa.text("SELECT version_num FROM public.alembic_version_tenant")
                )
                old_roles = role_configuration(c, names)
                old_tables = {
                    name: c.scalar(sa.text("SELECT to_regclass(:name) IS NOT NULL"), {"name": name})
                    for name in (
                        "knowledge.extracted_blocks",
                        "knowledge.chunks",
                        "ops.ingestion_intents",
                    )
                }
                PHASE = "ROLE_PRIVACY"
                apply_role_logging(c, names)
                role(c, names, "owner")
                PHASE = "MIGRATION"
                assert apply_ingestion(c, names, ROOT) == VERSION
                assert apply_ingestion(c, names, ROOT) == VERSION
                assert fingerprint(c, tables) == before
                role(c, names, "app")
                assert all(
                    c.scalar(sa.text("SELECT current_setting(:key)"), {"key": k}) == v
                    for k, v in SETTINGS.items()
                )
                probes(c, names)
                role(c, names, "owner")
                assert fingerprint(c, tables) == before
            finally:
                transaction.rollback()
            PHASE = "ROLLBACK"
            assert (
                c.scalar(sa.text("SELECT version_num FROM public.alembic_version_tenant"))
                == original
            )
            assert fingerprint(c, tables) == before and role_configuration(c, names) == old_roles
            assert all(
                c.scalar(sa.text("SELECT to_regclass(:name) IS NOT NULL"), {"name": name}) == exists
                for name, exists in old_tables.items()
            )
    finally:
        e.dispose()


def run():
    global PHASE
    PHASE = "CONTROL"
    control = engine("migrator")
    try:
        with control.connect() as c:
            before = fingerprint(
                c, list(Base.metadata.tables.values()) + list(IdentityBase.metadata.tables.values())
            )
        scope = json.loads((ROOT / "ops/f03/application-scope.json").read_text())
        PHASE = "BOOTSTRAP_FILES"
        user, password = credential("bootstrap")
        primary = Credential(user, password)
        secondary = Credential(
            "f01_bootstrap", private_file("/run/secrets/postgres2_password", 4096).decode()
        )
        PHASE = "CATALOG"
        for fixture in scope["fixtures"]:
            tenant = UUID(fixture["tenant"])
            with control.connect() as c:
                row = c.execute(
                    sa.select(
                        Tenant.state,
                        Tenant.migration_state,
                        Tenant.desired_version,
                        Tenant.observed_version,
                        Instance.host,
                        Instance.port,
                        ProvisioningOperation.id,
                        DbLocation.db_name,
                    )
                    .select_from(Tenant)
                    .join(DbLocation, DbLocation.tenant_id == Tenant.id)
                    .join(Instance, Instance.id == DbLocation.instance_id)
                    .join(ProvisioningOperation, ProvisioningOperation.tenant_id == Tenant.id)
                    .where(Tenant.id == tenant, ProvisioningOperation.state == "SUCCEEDED")
                ).one()
            assert row.state == "READY" and row.migration_state == "READY"
            assert row.desired_version == row.observed_version
            assert row.desired_version in ("f03_tenant_0002", VERSION)
            assert row.host in ("postgres", "postgres2") and row.port == 5432
            names = Names(tenant, row.id)
            assert row.db_name == names.database
            prove_tenant(
                Target(row.host, row.port, CA),
                names,
                primary if row.host == "postgres" else secondary,
            )
            print(
                "PASS T003 "
                + fixture["name"].upper().replace("-", "_")
                + ": migración/repetición y originales inmutables; FK/procedencia/roles correctos."
            )
            print("PASS T003: parcial/auditoría/baja/ACL sin READY; rollback íntegro.")
        with control.connect() as c:
            assert (
                fingerprint(
                    c,
                    list(Base.metadata.tables.values())
                    + list(IdentityBase.metadata.tables.values()),
                )
                == before
            )
        print("T003: cuatro fixtures/ambas instancias; sin esquema/perfil/worker F04 persistidos.")
    finally:
        control.dispose()


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    try:
        run()
    except Exception as error:
        print("F04-T003 ERROR_CLASS " + type(error).__name__)
        state = getattr(getattr(error, "orig", None), "sqlstate", None)
        code = (
            "SQLSTATE_" + state
            if isinstance(state, str) and re.fullmatch("[A-Z0-9]{5}", state)
            else (error.code if isinstance(error, MigrationError) else "REFUSED")
        )
        print("F04-T003 " + PHASE + " " + code + "; rollback y recursos conservados.")
        raise SystemExit(1) from None
