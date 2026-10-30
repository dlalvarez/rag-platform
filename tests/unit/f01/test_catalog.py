"""T001 / V01 partial: actual constraints and frozen control migrations, offline SQLite."""

import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from rag_platform.control.migrations import upgrade_control
from rag_platform.control.models import Base
from rag_platform.tenancy.contracts import SecretRef, TenantDatabase

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def database():
    engine = sa.create_engine("sqlite://", hide_parameters=True)
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        upgrade_control(connection, ROOT)
        yield connection
    engine.dispose()


def test_repeatable_frozen_migration(database):
    upgrade_control(database, ROOT)
    assert set(sa.inspect(database).get_table_names()) == set(Base.metadata.tables) | {
        "alembic_version_control"
    }
    assert (
        database.scalar(sa.text("SELECT version_num FROM alembic_version_control"))
        == "f01_control_0002"
    )
    assert not any(
        isinstance(c.type, (sa.JSON, sa.LargeBinary, sa.Text))
        for table in Base.metadata.tables.values()
        for c in table.columns
    )
    forbidden = {"password", "token", "secret_value", "content", "payload", "document", "prompt"}
    assert not forbidden & {
        c.name for table in Base.metadata.tables.values() for c in table.columns
    }


@pytest.mark.parametrize("state", ["READY_WITHOUT_PROBES", "private document", "token=value"])
def test_state_is_closed(database, state):
    table = Base.metadata.tables["tenants"]
    with pytest.raises(IntegrityError), database.begin_nested():
        database.execute(
            table.insert().values(id=uuid.uuid4(), desired_version="f01_tenant_0001", state=state)
        )


def test_idempotency_and_foreign_keys(database):
    tenant_id, operation_id, key = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    tenants = Base.metadata.tables["tenants"]
    operations = Base.metadata.tables["provisioning_operations"]
    database.execute(tenants.insert().values(id=tenant_id, desired_version="f01_tenant_0001"))
    database.execute(
        operations.insert().values(id=operation_id, tenant_id=tenant_id, idempotency_key=key)
    )
    with pytest.raises(IntegrityError), database.begin_nested():
        database.execute(
            operations.insert().values(
                id=uuid.uuid4(), tenant_id=tenant_id, idempotency_key=uuid.uuid4()
            )
        )
    with pytest.raises(IntegrityError), database.begin_nested():
        database.execute(
            operations.insert().values(id=uuid.uuid4(), tenant_id=uuid.uuid4(), idempotency_key=key)
        )


def test_db_location_requires_tls_and_separate_versioned_refs(database):
    tenant, instance = uuid.uuid4(), uuid.uuid4()
    database.execute(
        Base.metadata.tables["tenants"]
        .insert()
        .values(id=tenant, desired_version="f01_tenant_0001")
    )
    database.execute(
        Base.metadata.tables["instances"]
        .insert()
        .values(
            id=instance,
            host="postgres",
            port=5432,
            admin_secret_ref=uuid.uuid4(),
            admin_secret_version=1,
        )
    )
    values = dict(
        tenant_id=tenant,
        instance_id=instance,
        db_name=f"rag_t_{tenant.hex}",
        app_secret_ref=uuid.uuid4(),
        app_secret_version=1,
        migrator_secret_ref=uuid.uuid4(),
        migrator_secret_version=1,
    )
    for change in (
        {"ssl_mode": "disable"},
        {"app_secret_version": 0},
        {"migrator_secret_ref": values["app_secret_ref"]},
    ):
        with pytest.raises(IntegrityError), database.begin_nested():
            database.execute(Base.metadata.tables["db_locations"].insert().values(values | change))


def test_internal_contract_refuses_client_paths_and_shared_sql_secret():
    tenant, instance, ref = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    with pytest.raises(ValueError):
        SecretRef("https://unexpected/secret", 1)
    with pytest.raises(ValueError):
        SecretRef(ref, 0)
    with pytest.raises(ValueError):
        TenantDatabase(
            tenant,
            instance,
            "customer; DROP DATABASE other",
            SecretRef(ref, 1),
            SecretRef(uuid.uuid4(), 1),
        )
    with pytest.raises(ValueError):
        TenantDatabase(
            tenant, instance, f"rag_t_{tenant.hex}", SecretRef(ref, 1), SecretRef(ref, 2)
        )
