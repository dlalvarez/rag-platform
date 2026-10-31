"""T006 offline: state publication, same-connection lock and fixture boundaries."""

import importlib.util
from contextlib import contextmanager, nullcontext
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
import yaml
from sqlalchemy.orm import Session

from rag_platform.control.models import Base, DbLocation, Instance, ProvisioningOperation, Tenant
from rag_platform.providers.secrets import Credential
from rag_platform.provisioning import migration_control, migrations
from rag_platform.provisioning.migrations import VERSION, MigrationError
from rag_platform.provisioning.postgres import Names, Target

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def control(monkeypatch):
    engine = sa.create_engine("sqlite://")
    Base.metadata.create_all(engine)
    tenant, instance, operation = uuid4(), uuid4(), uuid4()
    with Session(engine) as session, session.begin():
        session.add(
            Instance(
                id=instance,
                host="postgres",
                port=5432,
                admin_secret_ref=uuid4(),
                admin_secret_version=1,
            )
        )
        session.add(
            Tenant(
                id=tenant,
                state="READY",
                migration_state="READY",
                desired_version=VERSION,
                observed_version=VERSION,
            )
        )
        session.flush()
        session.add(
            DbLocation(
                tenant_id=tenant,
                instance_id=instance,
                db_name="rag_t_" + tenant.hex,
                app_secret_ref=uuid4(),
                app_secret_version=1,
                migrator_secret_ref=uuid4(),
                migrator_secret_version=1,
            )
        )
        session.add(
            ProvisioningOperation(
                id=operation, tenant_id=tenant, idempotency_key=uuid4(), state="SUCCEEDED"
            )
        )
    monkeypatch.setattr(migration_control, "postgres_lock", lambda *_: nullcontext())
    yield engine, tenant, operation
    engine.dispose()


class Store:
    def __init__(self, tenant):
        self.tenant = tenant

    def read(self, ref):
        return Credential("rag_t_" + self.tenant.hex + "_migrator", "offline-synthetic")


def test_failed_migration_blocks_resolution_and_retry_publishes_verified_version(control):
    engine, tenant, _ = control

    def failure(*args):
        with Session(engine) as session:
            row = session.get(Tenant, tenant)
            assert (row.state, row.migration_state, row.observed_version) == (
                "PROVISIONING",
                "MIGRATING",
                None,
            )
        raise RuntimeError("do-not-echo-provider-response")

    with pytest.raises(MigrationError, match="MIGRATION_FAILED") as error:
        migration_control.migrate_controlled(
            engine, tenant, uuid4(), Store(tenant), Path("/ca"), ROOT, runner=failure
        )
    assert "do-not-echo" not in str(error.value)
    with Session(engine) as session:
        row = session.get(Tenant, tenant)
        assert (row.state, row.migration_state, row.observed_version) == (
            "FAILED",
            "MIGRATION_FAILED",
            None,
        )
    assert (
        migration_control.migrate_controlled(
            engine, tenant, uuid4(), Store(tenant), Path("/ca"), ROOT, runner=lambda *_: VERSION
        )
        == VERSION
    )
    with Session(engine) as session:
        row = session.get(Tenant, tenant)
        assert (row.state, row.migration_state, row.observed_version) == ("READY", "READY", VERSION)


def test_wrong_version_is_not_published(control):
    engine, tenant, _ = control
    with pytest.raises(MigrationError):
        migration_control.migrate_controlled(
            engine,
            tenant,
            uuid4(),
            Store(tenant),
            Path("/ca"),
            ROOT,
            runner=lambda *_: "wrong-head",
        )
    with Session(engine) as session:
        assert session.get(Tenant, tenant).state == "FAILED"


def test_unsuccessful_provisioning_cannot_be_promoted_by_migration(control):
    engine, tenant, operation = control
    with Session(engine) as session, session.begin():
        session.get(ProvisioningOperation, operation).state = "FAILED"
    with pytest.raises(MigrationError, match="IDENTITY_CONFLICT"):
        migration_control.migrate_controlled(
            engine, tenant, uuid4(), Store(tenant), Path("/ca"), ROOT
        )


def test_same_connection_lock_precedes_ddl_and_uses_null_pool(monkeypatch):
    names = Names(uuid4(), uuid4())
    calls = []

    class Result:
        def one(self):
            return names.database, names.role("migrator"), names.role("owner"), names.marker

    class Connection:
        dialect = sa.create_engine("sqlite://").dialect

        def execute(self, statement, *args):
            calls.append(str(statement))
            return Result()

        def exec_driver_sql(self, statement):
            calls.append(statement)

    connection = Connection()

    class Engine:
        @contextmanager
        def begin(self):
            yield connection

        def dispose(self):
            calls.append("DISPOSE")

    def create(*args, **kwargs):
        assert kwargs["poolclass"].__name__ == "NullPool"
        return Engine()

    monkeypatch.setattr(migrations.sa, "create_engine", create)
    with migrations.migration_session(
        Target("postgres", 5432, Path("/ca")), names, Credential(names.role("migrator"), "offline")
    ) as actual:
        assert actual is connection
        calls.append("ALEMBIC_ON_SAME_CONNECTION")
    assert next(i for i, s in enumerate(calls) if "pg_advisory_xact_lock" in s) < calls.index(
        "ALEMBIC_ON_SAME_CONNECTION"
    )
    assert calls[-1] == "DISPOSE"


def test_second_instance_fits_budget_and_exposes_no_ports():
    config = yaml.safe_load((ROOT / "ops/f01/compose.yaml").read_text())
    services = config["services"]
    names = ("openbao", "postgres", "postgres2", "minio", "tools")
    assert sum(int(services[n]["mem_limit"][:-1]) for n in names) == 5120
    assert not services["postgres2"].get("ports")
    assert services["postgres2"]["profiles"] == ["t006"]
    assert services["postgres2"]["image"] == services["postgres"]["image"]
    assert services["postgres2"]["secrets"] == ["postgres2_password"]


def test_prepare_second_preserves_existing_and_writes_valid_extensions(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("f01_t006_host", ROOT / "scripts/f01_host.py")
    host = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(host)
    for name in ("tls", "secrets"):
        (tmp_path / name).mkdir()
    for name in ("ca.key", "ca.crt"):
        (tmp_path / "tls" / name).write_text("synthetic-ca")
    monkeypatch.setattr(host, "DATA", tmp_path)
    monkeypatch.setattr(host, "validate_host", lambda **_: None)

    def openssl(args, **kwargs):
        for flag in ("-keyout", "-out"):
            if flag in args:
                (kwargs["cwd"] / args[args.index(flag) + 1]).write_text("synthetic-output")

    monkeypatch.setattr(host.subprocess, "run", openssl)
    host.prepare_second()
    assert len((tmp_path / "tls/postgres2.ext").read_text().splitlines()) == 4
    before = (tmp_path / "secrets/postgres2_password").read_text()
    with pytest.raises(ValueError, match="overwritten"):
        host.prepare_second()
    assert (tmp_path / "secrets/postgres2_password").read_text() == before
