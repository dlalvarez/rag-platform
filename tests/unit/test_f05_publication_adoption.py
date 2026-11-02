"""Publication adoption rejects catalog drift before using any credentials."""

import importlib
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from rag_platform.control.models import Base, DbLocation, Instance, ProvisioningOperation, Tenant
from rag_platform.provisioning.postgres import Names


@pytest.fixture
def catalog(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    module = importlib.import_module("f05_publication_adopt")
    engine = sa.create_engine("sqlite://")
    Base.metadata.create_all(engine)
    tenant, instance, operation = uuid4(), uuid4(), uuid4()
    names = Names(tenant, operation)
    with Session(engine) as c, c.begin():
        c.add(
            Instance(
                id=instance,
                host="postgres2",
                port=5432,
                admin_secret_ref=uuid4(),
                admin_secret_version=1,
            )
        )
        c.add(
            Tenant(
                id=tenant,
                state="READY",
                migration_state="READY",
                desired_version="f05_tenant_0004",
                observed_version="f05_tenant_0004",
            )
        )
        c.flush()
        c.add(
            DbLocation(
                tenant_id=tenant,
                instance_id=instance,
                db_name=names.database,
                app_secret_ref=uuid4(),
                app_secret_version=1,
                migrator_secret_ref=uuid4(),
                migrator_secret_version=1,
                readonly_secret_ref=uuid4(),
                readonly_secret_version=1,
            )
        )
        c.add(
            ProvisioningOperation(
                id=operation, tenant_id=tenant, idempotency_key=uuid4(), state="SUCCEEDED"
            )
        )
    yield module, engine, tenant, instance, operation
    engine.dispose()


@pytest.mark.parametrize("version", ["f05_tenant_0004", "f05_tenant_0005", "f05_tenant_0006"])
def test_known_heads_resolve_same_database_without_catalog_writes(catalog, version):
    module, engine, tenant, _, _ = catalog
    with Session(engine) as c, c.begin():
        c.get(Tenant, tenant).desired_version = version
    target, names, refs = module.target_data(engine, tenant)
    assert target.host == "postgres2" and target.port == 5432
    assert names.tenant == tenant and set(refs) == {"app", "migrator", "readonly"}
    with Session(engine) as c:
        assert c.get(Tenant, tenant).desired_version == version
        assert c.get(Tenant, tenant).state == "READY"


@pytest.mark.parametrize(
    "kind",
    [
        "unknown_head",
        "older_head",
        "suspended",
        "failed_operation",
        "host",
        "port",
        "database",
        "missing_tenant",
    ],
)
def test_catalog_drift_refused_without_mutating_tenant(catalog, kind):
    module, engine, tenant, instance, operation = catalog
    with Session(engine) as c, c.begin():
        if kind == "unknown_head":
            c.get(Tenant, tenant).desired_version = "unknown"
        elif kind == "older_head":
            c.get(Tenant, tenant).desired_version = "f04_tenant_0003"
        elif kind == "suspended":
            c.get(Tenant, tenant).state = "SUSPENDED"
        elif kind == "failed_operation":
            c.get(ProvisioningOperation, operation).state = "FAILED"
        elif kind == "host":
            c.get(Instance, instance).host = "unapproved-host"
        elif kind == "port":
            c.get(Instance, instance).port = 5433
        elif kind == "database":
            c.get(DbLocation, tenant).db_name = "another_tenant"
    with Session(engine) as c:
        before = (c.get(Tenant, tenant).state, c.get(Tenant, tenant).desired_version)
    with pytest.raises(RuntimeError, match="CATALOG_CONFLICT"):
        module.target_data(engine, uuid4() if kind == "missing_tenant" else tenant)
    with Session(engine) as c:
        assert (c.get(Tenant, tenant).state, c.get(Tenant, tenant).desired_version) == before
