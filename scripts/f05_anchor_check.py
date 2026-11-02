"""Original anchor SQL proof on existing F05 fixtures; all DDL/data rolled back."""

import json
import logging
import re
from pathlib import Path
from uuid import UUID, uuid4

import sqlalchemy as sa
from f02_common import credential, engine
from f04_schema_check import candidate, denied, fingerprint, fixture, role
from sqlalchemy.pool import NullPool

from rag_platform.control.identity_models import IdentityBase
from rag_platform.control.models import Base, DbLocation, Instance, ProvisioningOperation, Tenant
from rag_platform.embeddings.anchor_migrations import apply_original_anchor
from rag_platform.embeddings.original_anchor_f05_0005 import VERSION
from rag_platform.identity_api import private_file
from rag_platform.ingestion.logging_setup import local_private_logging
from rag_platform.ingestion.schema_f04_0003 import build_metadata as historical
from rag_platform.providers.secrets import Credential
from rag_platform.provisioning.migrations import MigrationError
from rag_platform.provisioning.postgres import Names, Target

ROOT = Path(__file__).resolve().parents[1]
CA = Path("/run/f01-ca.crt")
PHASE = "START"


def prove(target, names, bootstrap):
    global PHASE
    e = sa.create_engine(
        "postgresql+psycopg://",
        creator=lambda: target.connect(names.database, bootstrap),
        poolclass=NullPool,
        hide_parameters=True,
    )
    tables = list(historical().tables.values())
    try:
        with e.connect() as c:
            transaction = c.begin()
            try:
                local_private_logging(c)
                c.exec_driver_sql("SET LOCAL lock_timeout='5s'")
                before = fingerprint(c, tables)
                old_head = c.scalar(
                    sa.text("SELECT version_num FROM public.alembic_version_tenant")
                )
                assert old_head == "f05_tenant_0004"
                role(c, names, "owner")
                PHASE = "UNKNOWN_SOURCE_REFUSED"
                with c.begin_nested() as unknown:
                    c.exec_driver_sql(
                        "UPDATE public.alembic_version_tenant SET version_num='unknown_future'"
                    )
                    try:
                        apply_original_anchor(c, names, ROOT)
                    except MigrationError as error:
                        assert error.code == "VERSION_MISMATCH"
                    else:
                        raise AssertionError("UNKNOWN_SOURCE_ACCEPTED")
                    unknown.rollback()
                PHASE = "DDL_FAILURE_ROLLBACK"
                denied(
                    c,
                    lambda: (
                        apply_original_anchor(c, names, ROOT),
                        c.exec_driver_sql("SELECT 1/0"),
                    ),
                    "22012",
                )
                assert (
                    c.scalar(sa.text("SELECT version_num FROM public.alembic_version_tenant"))
                    == old_head
                )
                assert "original_version_id" not in {
                    x["name"] for x in sa.inspect(c).get_columns("documents", schema="knowledge")
                }
                PHASE = "BACKFILL_REPEAT"
                assert apply_original_anchor(c, names, ROOT) == VERSION
                assert apply_original_anchor(c, names, ROOT) == VERSION
                assert (
                    c.scalar(
                        sa.text(
                            "SELECT count(*) FROM knowledge.documents "
                            "WHERE original_version_id IS DISTINCT FROM current_version_id"
                        )
                    )
                    == 0
                )
                assert fingerprint(c, tables) == before
                PHASE = "DISABLED_GUARD_REFUSED"
                with c.begin_nested() as tamper:
                    c.exec_driver_sql(
                        "ALTER TABLE knowledge.documents DISABLE TRIGGER f05_original_anchor"
                    )
                    try:
                        apply_original_anchor(c, names, ROOT)
                    except MigrationError as error:
                        assert error.code == "VERSION_MISMATCH"
                    else:
                        raise AssertionError("DISABLED_GUARD_ACCEPTED")
                    tamper.rollback()
                PHASE = "APP_INSERT_COMPATIBILITY"
                role(c, names, "app")
                with c.begin_nested() as synthetic:
                    f = fixture(c)
                    processed, _ = candidate(c, f)
                    c.exec_driver_sql("SET CONSTRAINTS ALL IMMEDIATE")
                    c.exec_driver_sql("SET CONSTRAINTS ALL DEFERRED")
                    params = {"doc": f["doc"], "raw": f["raw"]}
                    assert (
                        c.scalar(
                            sa.text(
                                "SELECT original_version_id FROM knowledge.documents WHERE id=:doc"
                            ),
                            params,
                        )
                        == f["raw"]
                    )
                    PHASE = "APP_ANCHOR_UPDATE_DENIED"
                    denied(
                        c,
                        lambda: c.execute(
                            sa.text(
                                "UPDATE knowledge.documents SET original_version_id=:raw "
                                "WHERE id=:doc"
                            ),
                            params,
                        ),
                        "42501",
                    )
                    role(c, names, "owner")
                    PHASE = "ANCHOR_IMMUTABLE"
                    for value in (None, uuid4(), processed):
                        denied(
                            c,
                            lambda value=value: c.execute(
                                sa.text(
                                    "UPDATE knowledge.documents SET original_version_id=:value "
                                    "WHERE id=:doc"
                                ),
                                params | {"value": value},
                            ),
                        )
                    denied(
                        c,
                        lambda: c.execute(
                            sa.text(
                                "UPDATE knowledge.documents SET original_version_kind='PROCESSED' "
                                "WHERE id=:doc"
                            ),
                            params,
                        ),
                    )
                    c.execute(
                        sa.text(
                            "UPDATE knowledge.documents SET original_version_id=:raw WHERE id=:doc"
                        ),
                        params,
                    )

                    PHASE = "ANCHOR_CROSS_DOCUMENT"

                    PHASE = "INSERT_ANCHOR_MISMATCH"
                    denied(
                        c,
                        lambda: c.execute(
                            sa.text(
                                "INSERT INTO knowledge.documents(id,repository_id,source_id,"
                                "current_version_id,original_version_id,created_by) "
                                "SELECT :new,d.repository_id,d.source_id,"
                                ":current,:anchor,d.created_by "
                                "FROM knowledge.documents d WHERE d.id=:doc"
                            ),
                            {
                                "new": uuid4(),
                                "current": uuid4(),
                                "anchor": uuid4(),
                                "doc": f["doc"],
                            },
                        ),
                    )
                    PHASE = "ANCHOR_CROSS_DOCUMENT"

                    # A new document cannot anchor an original belonging to another document.
                    def cross_document():
                        c.execute(
                            sa.text(
                                "INSERT INTO knowledge.documents(id,repository_id,source_id,"
                                "current_version_id,original_version_id,created_by) "
                                "SELECT :new,id.repository_id,id.source_id,:raw,:raw,id.created_by "
                                "FROM knowledge.documents id WHERE id.id=:doc"
                            ),
                            params | {"new": uuid4()},
                        )
                        c.exec_driver_sql("SET CONSTRAINTS knowledge.f05_original_anchor IMMEDIATE")

                    denied(c, cross_document, "23503")
                    synthetic.rollback()
                assert fingerprint(c, tables) == before
            finally:
                transaction.rollback()
            PHASE = "FINAL_ROLLBACK"
            assert (
                c.scalar(sa.text("SELECT version_num FROM public.alembic_version_tenant"))
                == old_head
            )
            assert "original_version_id" not in {
                x["name"] for x in sa.inspect(c).get_columns("documents", schema="knowledge")
            }
            assert fingerprint(c, tables) == before
    finally:
        e.dispose()


def run():
    global PHASE
    control = engine("migrator")
    try:
        ctables = list(Base.metadata.tables.values()) + list(IdentityBase.metadata.tables.values())
        with control.connect() as c:
            before = fingerprint(c, ctables)
        primary = Credential(*credential("bootstrap"))
        secondary = Credential(
            "f01_bootstrap", private_file("/run/secrets/postgres2_password", 4096).decode()
        )
        fixtures = json.loads((ROOT / "ops/f03/application-scope.json").read_text())["fixtures"]
        for fixture in fixtures:
            PHASE = "CATALOG"
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
            assert row.state == row.migration_state == "READY"
            assert row.desired_version == row.observed_version == "f05_tenant_0004"
            assert row.host in ("postgres", "postgres2") and row.port == 5432
            names = Names(tenant, row.id)
            assert row.db_name == names.database
            prove(
                Target(row.host, row.port, CA),
                names,
                primary if row.host == "postgres" else secondary,
            )
            print(
                "PASS F05 ANCHOR "
                + fixture["name"]
                + ": backfill/FK/immutable/legacy insert; rollback intact."
            )
        with control.connect() as c:
            assert fingerprint(c, ctables) == before
        print("F05 ANCHOR: four fixtures/two instances; no persistent adoption or publication.")
    finally:
        control.dispose()


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    try:
        run()
    except Exception as error:
        state = getattr(getattr(error, "orig", error), "sqlstate", None)
        code = (
            "SQLSTATE_" + state
            if isinstance(state, str) and re.fullmatch("[A-Z0-9]{5}", state)
            else "REFUSED"
        )
        print(
            "F05-ANCHOR "
            + PHASE
            + " "
            + code
            + " "
            + type(error).__name__
            + "; rollback/resources retained."
        )
        raise SystemExit(1) from None
