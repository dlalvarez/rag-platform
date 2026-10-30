"""T002 offline guards; real SQL denial is proven separately by f01_sql_check."""

import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import IntegrityError

from rag_platform.control.migrations import upgrade_control
from rag_platform.providers.secrets import SecretErrorCode, SecretStoreError
from rag_platform.provisioning.credentials import credential_for
from rag_platform.provisioning.postgres import (
    Names,
    SqlProvisioningError,
    Target,
    inspect_resources,
)
from rag_platform.tenancy.contracts import SecretRef

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("value", ["slug", "a;drop database x", None, 1])
def test_names_require_internal_uuid(value):
    with pytest.raises(ValueError):
        Names(value)


def test_generated_identifiers_are_bounded_and_distinct():
    a, b = Names(uuid4()), Names(uuid4())
    assert a.database != b.database
    assert len({a.role(k) for k in ("owner", "migrator", "app", "readonly")}) == 4
    assert all(len(a.role(k)) <= 63 for k in ("owner", "migrator", "app", "readonly"))
    with pytest.raises(ValueError):
        a.role("root")


@pytest.mark.parametrize(
    "host,port",
    [("/tmp/socket", 5432), ("x user=admin", 5432), ("postgres", 0), ("postgres", True)],
)
def test_target_cannot_be_conninfo_or_socket(host, port):
    with pytest.raises(ValueError):
        Target(host, port, Path("/public/ca.crt"))


@pytest.mark.parametrize("code", list(SecretErrorCode))
def test_provider_failure_never_repairs_existing_resource(code):
    class FailingStore:
        def read(self, ref):
            raise SecretStoreError(code)

        def write(self, *args, **kwargs):
            raise AssertionError("Never regenerate credentials for an existing resource")

    with pytest.raises(SecretStoreError) as error:
        credential_for(FailingStore(), SecretRef(uuid4(), 1), "synthetic", resource_exists=True)
    assert error.value.code == code


def test_cas_creation_is_read_back_and_stable():
    class Store:
        value = None
        writes = 0

        def read(self, ref):
            if self.value is None:
                raise SecretStoreError(SecretErrorCode.NOT_FOUND)
            return self.value

        def write(self, ref_id, value, *, expected_version):
            assert expected_version == 0
            assert value.username == "synthetic"
            self.writes += 1
            self.value = value
            return SecretRef(ref_id, 1)

    store, ref = Store(), SecretRef(uuid4(), 1)
    first = credential_for(store, ref, "synthetic", resource_exists=False)
    assert credential_for(store, ref, "synthetic", resource_exists=True) == first
    assert store.writes == 1
    with pytest.raises(SecretStoreError):
        credential_for(store, ref, "different", resource_exists=True)


def test_collision_stops_before_any_mutation():
    class Result:
        def fetchone(self):
            return (False, False, False, False, False, False, "unowned")

    class Connection:
        calls = []

        def execute(self, statement, values):
            assert statement.startswith("SELECT ")
            self.calls.append(statement)
            return Result()

    connection = Connection()
    with pytest.raises(SqlProvisioningError, match="OWNERSHIP_CONFLICT"):
        inspect_resources(connection, Names(uuid4()))
    assert connection.calls and all(call.startswith("SELECT ") for call in connection.calls)


def test_upgrade_preserves_old_location_and_enforces_readonly_pair():
    from rag_platform.control.models import Base

    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        config = Config(str(ROOT / "alembic-control.ini"))
        config.attributes["connection"] = connection
        command.upgrade(config, "f01_control_0001")
        tenant, instance = uuid4(), uuid4()
        tables = Base.metadata.tables
        connection.execute(
            tables["tenants"]
            .insert()
            .values(
                id=tenant,
                state="PROVISIONING",
                migration_state="NEEDS_MIGRATION",
                desired_version="f01_tenant_0001",
            )
        )
        connection.execute(
            tables["instances"]
            .insert()
            .values(
                id=instance,
                host="postgres",
                port=5432,
                admin_secret_ref=uuid4(),
                admin_secret_version=1,
            )
        )
        # Use pre-T002 reflected table, so no readonly columns are referenced.
        old = sa.Table("db_locations", sa.MetaData(), autoload_with=connection)
        app, migrator = uuid4(), uuid4()
        connection.execute(
            old.insert().values(
                tenant_id=tenant.hex,
                instance_id=instance.hex,
                db_name=Names(tenant).database,
                app_secret_ref=app.hex,
                app_secret_version=1,
                migrator_secret_ref=migrator.hex,
                migrator_secret_version=1,
                ssl_mode="verify-full",
            )
        )
        upgrade_control(connection, ROOT)
        location = tables["db_locations"]
        row = connection.execute(sa.select(location)).one()
        assert row.readonly_secret_ref is None and row.app_secret_ref == app
        for change in (
            {"readonly_secret_ref": uuid4()},
            {"readonly_secret_version": 1},
            {"readonly_secret_ref": app, "readonly_secret_version": 1},
            {"readonly_secret_ref": uuid4(), "readonly_secret_version": 0},
        ):
            with pytest.raises(IntegrityError), connection.begin_nested():
                connection.execute(location.update().values(**change))
        connection.execute(
            location.update().values(readonly_secret_ref=uuid4(), readonly_secret_version=1)
        )
        upgrade_control(connection, ROOT)
    engine.dispose()


def test_sql_check_requires_own_terminal_before_any_secret_read(monkeypatch):
    import sys

    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(
        "f01_sql_check", ROOT / "scripts/f01_sql_check.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(module, "client", lambda: pytest.fail("Must not contact OpenBao"))
    with pytest.raises(SystemExit, match="START"):
        module.main()
