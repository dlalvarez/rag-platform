"""Trusted F04 development adoption: additive, explicit scope, truthful failure/recovery."""

import json
import logging
import re
from pathlib import Path
from uuid import UUID

import sqlalchemy as sa
from f01_admin import DAY_ACTOR
from f01_daily import session
from f02_common import credential, engine
from f03_fixtures import ROOT, snapshot
from f03_schema_check import connection_engine, denied
from f04_schema_check import fingerprint
from sqlalchemy.orm import Session

from rag_platform.control.identity_models import IdentityBase
from rag_platform.control.migrations import upgrade_ingestion
from rag_platform.control.models import DbLocation, Instance, ProvisioningOperation, Tenant
from rag_platform.documents.schema_f03_0002 import build_metadata
from rag_platform.identity_api import private_file
from rag_platform.ingestion.logging_setup import SETTINGS, apply_role_logging, local_private_logging
from rag_platform.ingestion.migrations import apply_ingestion, migrate_ingestion_controlled
from rag_platform.ingestion.queue_schema import jobs
from rag_platform.ingestion.schema import VERSION
from rag_platform.providers.secrets import Credential
from rag_platform.provisioning.migration_control import migrate_controlled
from rag_platform.provisioning.migrations import MigrationError, migration_session
from rag_platform.provisioning.postgres import Names, Target
from rag_platform.tenancy.contracts import SecretRef
from rag_platform.tenancy.resolver import AdministrativeTenant, CatalogResolver, TenantAccessError

CA = Path("/run/f01-ca.crt")
PHASE = "START"


def target_data(control, tenant):
    with Session(control) as c:
        tenant_row = c.get(Tenant, tenant)
        if (
            tenant_row is None
            or tenant_row.state == "SUSPENDED"
            or tenant_row.desired_version not in ("f03_tenant_0002", VERSION)
        ):
            raise RuntimeError("CATALOG_CONFLICT")
        location = c.get(DbLocation, tenant)
        operation = c.scalar(
            sa.select(ProvisioningOperation).where(ProvisioningOperation.tenant_id == tenant)
        )
        if location is None or operation is None or operation.state != "SUCCEEDED":
            raise RuntimeError("CATALOG_CONFLICT")
        instance = c.get(Instance, location.instance_id)
        names = Names(tenant, operation.id)
        if (
            location.db_name != names.database
            or instance.host not in {"postgres", "postgres2"}
            or instance.port != 5432
        ):
            raise RuntimeError("CATALOG_CONFLICT")
        refs = {
            kind: SecretRef(
                getattr(location, kind + "_secret_ref"), getattr(location, kind + "_secret_version")
            )
            for kind in ("migrator", "app", "readonly")
        }
        return Target(instance.host, instance.port, CA), names, refs


def role_login(target, names, secret, kind):
    e = connection_engine(target, names, secret)
    try:
        with e.connect() as c:
            row = c.execute(
                sa.text(
                    "SELECT current_database(),current_user,"
                    "(SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid())"
                )
            ).one()
            assert tuple(row) == (names.database, names.role(kind), True)
            for key, value in SETTINGS.items():
                assert c.scalar(sa.text("SELECT current_setting(:key)"), {"key": key}) == value
            assert c.scalar(sa.text("SELECT count(*) FROM knowledge.documents")) >= 0
            denied(c, "SELECT * FROM public.ops_identity")
            denied(c, "CREATE TABLE knowledge.f04_forbidden(x integer)")
            if kind == "readonly":
                denied(c, "SELECT * FROM ops.ingestion_intents")
                denied(
                    c,
                    "INSERT INTO knowledge.repositories(id,name,owner_id) VALUES "
                    "(gen_random_uuid(),'forbidden',gen_random_uuid())",
                )
            else:
                denied(
                    c, "UPDATE knowledge.document_versions SET filename='changed.txt' WHERE false"
                )
            c.rollback()
    finally:
        e.dispose()


def run():
    global PHASE
    control = engine("migrator")
    scope = json.loads((ROOT / "ops/f03/application-scope.json").read_text())["fixtures"]
    tenants = tuple(UUID(f["tenant"]) for f in scope)
    try:
        PHASE = "SCOPE"
        assert len(tenants) == len(set(tenants)) == 4
        before = snapshot(control)
        queue_before = None
        queue_count = 0
        with control.connect() as c:
            identities_before = fingerprint(c, list(IdentityBase.metadata.tables.values()))
            if c.scalar(sa.text("SELECT to_regclass('public.job_envelopes') IS NOT NULL")):
                queue_before = fingerprint(c, [jobs])
                queue_count = c.scalar(
                    sa.select(sa.func.count())
                    .select_from(jobs)
                    .where(jobs.c.tenant_id.in_(tenants))
                )
                assert (
                    c.scalar(
                        sa.text(
                            "SELECT count(*) FROM public.job_envelopes WHERE tenant_id=ANY(:ids) "
                            "AND status='RUNNING'"
                        ),
                        {"ids": list(tenants)},
                    )
                    == 0
                )
        user, password = credential("bootstrap")
        bootstraps = {
            "postgres": Credential(user, password),
            "postgres2": Credential(
                user, private_file("/run/secrets/postgres2_password", 4096).decode()
            ),
        }
        with session() as (store, _, _):
            for fixture in scope:
                tag = fixture["name"].upper().replace("-", "_")
                tenant = UUID(fixture["tenant"])
                PHASE = tag + "/CATALOG"
                target, names, refs = target_data(control, tenant)
                bootstrap = connection_engine(target, names, bootstraps[target.host])
                try:
                    with bootstrap.connect() as c:
                        old = fingerprint(c, list(build_metadata().tables.values()))
                        prior = c.scalar(
                            sa.text("SELECT version_num FROM public.alembic_version_tenant")
                        )
                        assert prior in ("f03_tenant_0002", VERSION)
                        assert not c.scalar(
                            sa.text("SELECT to_regclass('ops.f04_rollback_probe') IS NOT NULL")
                        )
                    with bootstrap.begin() as c:
                        local_private_logging(c)
                        PHASE = tag + "/ROLE_PRIVACY"
                        apply_role_logging(c, names)
                    PHASE = tag + "/FAILED_DDL"

                    ddl_error_seen = False

                    def failed_ddl(target, names, secret, repository):
                        nonlocal ddl_error_seen
                        with migration_session(target, names, secret) as c:
                            apply_ingestion(c, names, repository)
                            c.exec_driver_sql("CREATE TABLE ops.f04_rollback_probe(x integer)")
                            try:
                                c.exec_driver_sql("SELECT 1/0")
                            except sa.exc.DBAPIError as error:
                                assert getattr(error.orig, "sqlstate", None) == "22012"
                                ddl_error_seen = True
                                raise

                    try:
                        migrate_controlled(
                            control,
                            tenant,
                            DAY_ACTOR,
                            store,
                            CA,
                            ROOT,
                            runner=failed_ddl,
                            profile="ingestion",
                        )
                    except MigrationError:
                        pass
                    else:
                        raise RuntimeError("DDL_FAILURE_ACCEPTED")
                    assert ddl_error_seen
                    with Session(control) as catalog:
                        row = catalog.get(Tenant, tenant)
                        assert (row.state, row.migration_state, row.observed_version) == (
                            "FAILED",
                            "MIGRATION_FAILED",
                            None,
                        )
                    with bootstrap.connect() as c:
                        assert (
                            c.scalar(
                                sa.text("SELECT version_num FROM public.alembic_version_tenant")
                            )
                            == prior
                        )
                        assert not c.scalar(
                            sa.text("SELECT to_regclass('ops.f04_rollback_probe') IS NOT NULL")
                        )
                        assert fingerprint(c, list(build_metadata().tables.values())) == old
                    PHASE = tag + "/MIGRATE_RECOVER"
                    for _ in range(2):
                        assert (
                            migrate_ingestion_controlled(
                                control, tenant, DAY_ACTOR, store, CA, ROOT
                            )
                            == VERSION
                        )
                    PHASE = tag + "/LOGIN"
                    for kind in ("app", "readonly"):
                        role_login(target, names, store.read(refs[kind]), kind)
                    with bootstrap.connect() as c:
                        assert fingerprint(c, list(build_metadata().tables.values())) == old
                    resolved = CatalogResolver(control, profile="ingestion").resolve(
                        AdministrativeTenant(tenant)
                    )
                    assert resolved.host == target.host
                    for profile in ("identity", "documents"):
                        try:
                            CatalogResolver(control, profile=profile).resolve(
                                AdministrativeTenant(tenant)
                            )
                        except TenantAccessError as error:
                            assert error.code == "SCHEMA_INCOMPATIBLE"
                        else:
                            raise RuntimeError("WRONG_PROFILE_ACCEPTED")
                    print(
                        "PASS F04 ADOPT "
                        + tag
                        + ": DDL rollback/FAILED honesto; recuperación/repetición."
                    )
                    print(
                        "PASS F04 ADOPT "
                        + tag
                        + ": datos conservados; TLS/logs/roles app/readonly reales."
                    )
                finally:
                    bootstrap.dispose()
            PHASE = "CONTROL_QUEUE"
            with control.begin() as c:
                upgrade_ingestion(c, ROOT)
                upgrade_ingestion(c, ROOT)
                c.exec_driver_sql("REVOKE ALL ON public.job_envelopes FROM PUBLIC")
                c.exec_driver_sql("REVOKE ALL ON public.job_envelopes FROM f02_identity_app")
                c.exec_driver_sql(
                    "GRANT SELECT,INSERT,UPDATE ON public.job_envelopes TO f02_identity_app"
                )
            app = engine()
            try:
                with app.connect() as c:
                    for action in ("SELECT", "INSERT", "UPDATE"):
                        assert c.scalar(
                            sa.text(
                                "SELECT has_table_privilege("
                                "current_user,'public.job_envelopes',:action)"
                            ),
                            {"action": action},
                        )
                    for action in ("DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"):
                        assert not c.scalar(
                            sa.text(
                                "SELECT has_table_privilege("
                                "current_user,'public.job_envelopes',:action)"
                            ),
                            {"action": action},
                        )
                    assert (
                        c.scalar(
                            sa.text(
                                "SELECT count(*) FROM public.job_envelopes "
                                "WHERE tenant_id=ANY(:ids)"
                            ),
                            {"ids": list(tenants)},
                        )
                        == queue_count
                    )
            finally:
                app.dispose()
        PHASE = "FINAL"
        if queue_before is not None:
            with control.connect() as c:
                assert fingerprint(c, [jobs]) == queue_before
        assert snapshot(control) == before
        with control.connect() as c:
            assert fingerprint(c, list(IdentityBase.metadata.tables.values())) == identities_before
        print(
            "PASS F04 ADOPT: cola pública aditiva/repetible; control app solo SELECT/INSERT/UPDATE."
        )
        print(
            "PASS F04 ADOPT: identidades y tenants previos conservados; sesión diaria sin cambios."
        )
        print("F04 ADOPT: head F04 en cuatro fixtures; falta promoción coordinada API/worker.")
    finally:
        control.dispose()


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    try:
        run()
    except Exception as error:
        state = getattr(getattr(error, "orig", None), "sqlstate", None)
        code = (
            "SQLSTATE_" + state
            if isinstance(state, str) and re.fullmatch("[A-Z0-9]{5}", state)
            else "REFUSED"
        )
        print(
            "F04-ADOPT "
            + PHASE
            + " "
            + type(error).__name__
            + " "
            + code
            + "; recursos conservados."
        )
        raise SystemExit(1) from None
