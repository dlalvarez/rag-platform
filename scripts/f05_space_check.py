"""SQL-only F05 space probes on existing fixtures; all tenant DDL/data rolled back."""

import json
import logging
import re
from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid4, uuid5

import sqlalchemy as sa
from f02_common import credential, engine
from f04_schema_check import denied, fingerprint, role
from sqlalchemy.pool import NullPool

from rag_platform.control.identity_models import IdentityBase
from rag_platform.control.models import Base, DbLocation, Instance, ProvisioningOperation, Tenant
from rag_platform.embeddings.migrations import VERSION, apply_spaces, register_space
from rag_platform.embeddings.qwen import qwen_profile
from rag_platform.embeddings.space_ddl import table_name
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
                assert old_head == "f04_tenant_0003"
                assert not c.scalar(
                    sa.text("SELECT to_regclass('knowledge.embedding_spaces') IS NOT NULL")
                )
                role(c, names, "owner")
                PHASE = "DDL_FAILURE_ROLLBACK"
                denied(
                    c,
                    lambda: (apply_spaces(c, names, ROOT), c.exec_driver_sql("SELECT 1/0")),
                    "22012",
                )
                assert (
                    c.scalar(sa.text("SELECT version_num FROM public.alembic_version_tenant"))
                    == old_head
                )
                assert not c.scalar(
                    sa.text("SELECT to_regclass('knowledge.embedding_spaces') IS NOT NULL")
                )
                PHASE = "MIGRATION_REPEAT"
                assert apply_spaces(c, names, ROOT) == VERSION
                assert apply_spaces(c, names, ROOT) == VERSION
                assert fingerprint(c, tables) == before
                PHASE = "SPACE_REPEAT"
                profile = qwen_profile()
                space = uuid5(names.tenant, "F05/rollback/space1")
                assert register_space(c, names, space, profile) == space
                assert register_space(c, names, space, profile) == space
                table = "knowledge." + table_name(space)
                assert c.scalar(sa.text("SELECT count(*) FROM knowledge.embedding_spaces")) == 1
                chunk = c.execute(
                    sa.text(
                        "SELECT c.id,c.version_id,c.document_id,c.repository_id "
                        "FROM knowledge.chunks c JOIN knowledge.documents d ON d.id=c.document_id "
                        "WHERE d.state='RECEIVED' ORDER BY c.id LIMIT 1"
                    )
                ).one()
                params = dict(
                    zip(("chunk", "version", "document", "repository"), chunk, strict=True)
                )
                params |= {
                    "space": space,
                    "dimension": profile.dimension,
                    "fingerprint": profile.fingerprint(),
                    "vector": "[" + ",".join(["1"] + ["0"] * 1023) + "]",
                }
                insert = sa.text(
                    "INSERT INTO "
                    + table
                    + "(chunk_id,version_id,document_id,repository_id,space_id,dimension,"
                    "profile_fingerprint,embedding) VALUES"
                    "(:chunk,:version,:document,:repository,:space,:dimension,:fingerprint,"
                    "CAST(:vector AS vector))"
                )
                PHASE = "TYPED_NEGATIVES"
                role(c, names, "app")
                denied(c, lambda: c.execute(insert, params | {"vector": "[1,0]"}), "22000")
                denied(
                    c,
                    lambda: c.execute(
                        insert, params | {"vector": "[" + ",".join(["0"] * 1024) + "]"}
                    ),
                )
                denied(c, lambda: c.execute(insert, params | {"fingerprint": "0" * 64}))
                denied(c, lambda: c.execute(insert, params | {"repository": uuid4()}), "23503")
                c.execute(insert, params)
                assert c.scalar(sa.text("SELECT count(*) FROM " + table)) == 1
                denied(c, lambda: c.execute(insert, params), "23505")
                denied(c, sa.text("UPDATE " + table + " SET dimension=1"), "42501")
                denied(c, sa.text("DELETE FROM " + table), "42501")
                denied(c, sa.text("UPDATE knowledge.embedding_spaces SET dimension=1"), "42501")
                role(c, names, "readonly")
                denied(c, lambda: c.execute(insert, params), "42501")
                assert c.scalar(sa.text("SELECT count(*) FROM " + table)) == 1
                role(c, names, "owner")
                PHASE = "SPACE_RETENTION"
                denied(c, sa.text("UPDATE knowledge.embedding_spaces SET dimension=1"))
                denied(c, sa.text("DELETE FROM knowledge.embedding_spaces"))
                PHASE = "COLLISION_RETAINS_CATALOG"
                with c.begin_nested() as probe:
                    collision = uuid4()
                    c.exec_driver_sql("CREATE TABLE knowledge." + table_name(collision) + "(x int)")
                    try:
                        register_space(
                            c,
                            names,
                            collision,
                            replace(profile, model_revision="collision-fixture"),
                        )
                    except MigrationError as error:
                        assert error.code == "IDENTITY_CONFLICT"
                    else:
                        raise RuntimeError("COLLISION_NOT_REJECTED")
                    assert c.scalar(sa.text("SELECT count(*) FROM knowledge.embedding_spaces")) == 1
                    probe.rollback()
                PHASE = "NEW_SPACE_RETAINS_OLD"
                new_space = uuid5(names.tenant, "F05/rollback/space2")
                newer = replace(profile, model_revision="synthetic-alternative-revision")
                assert register_space(c, names, new_space, newer) == new_space
                assert c.scalar(sa.text("SELECT count(*) FROM " + table)) == 1
                assert (
                    c.scalar(sa.text("SELECT count(*) FROM knowledge." + table_name(new_space)))
                    == 0
                )
                assert c.scalar(sa.text("SELECT count(*) FROM knowledge.embedding_spaces")) == 2
                assert fingerprint(c, tables) == before
            finally:
                transaction.rollback()
            PHASE = "FINAL_ROLLBACK"
            assert (
                c.scalar(sa.text("SELECT version_num FROM public.alembic_version_tenant"))
                == old_head
            )
            assert not c.scalar(
                sa.text("SELECT to_regclass('knowledge.embedding_spaces') IS NOT NULL")
            )
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
            assert row.desired_version == row.observed_version == "f04_tenant_0003"
            assert row.host in ("postgres", "postgres2") and row.port == 5432
            names = Names(tenant, row.id)
            assert row.db_name == names.database
            prove(
                Target(row.host, row.port, CA),
                names,
                primary if row.host == "postgres" else secondary,
            )
            print(
                "PASS F05 SPACE "
                + fixture["name"]
                + ": typed/profile/FK/roles/HNSW; rollback intact."
            )
        with control.connect() as c:
            assert fingerprint(c, ctables) == before
        print("F05 SPACE: four fixtures/two instances; no persistent adoption or publication.")
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
            "F05-SPACE "
            + PHASE
            + " "
            + code
            + " "
            + type(error).__name__
            + "; rollback/resources retained."
        )
        raise SystemExit(1) from None
