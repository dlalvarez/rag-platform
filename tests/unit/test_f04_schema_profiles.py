"""F04 profile admission and publication: exact versions, no secret access on denial."""

import time
from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import dialect
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable

from rag_platform.control.identity import AccessError
from rag_platform.control.models import Base, DbLocation, Instance, ProvisioningOperation, Tenant
from rag_platform.documents.schema_f03_0002 import build_metadata as historical
from rag_platform.ingestion.schema_f04_0003 import VERSION, build_metadata
from rag_platform.providers.secrets import Credential
from rag_platform.provisioning import migration_control
from rag_platform.provisioning.migrations import MigrationError
from rag_platform.tenancy.authorization import AuthorizedTenantContext, TenantAuthorizer
from rag_platform.tenancy.contracts import SecretRef
from rag_platform.tenancy.resolver import AdministrativeTenant, CatalogResolver, TenantAccessError


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
                desired_version="f03_tenant_0002",
                observed_version="f03_tenant_0002",
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
                readonly_secret_ref=uuid4(),
                readonly_secret_version=1,
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
    yield engine, tenant
    engine.dispose()


class Store:
    def __init__(self, tenant):
        self.tenant, self.reads = tenant, 0

    def read(self, _ref):
        self.reads += 1
        return Credential("rag_t_" + self.tenant.hex + "_migrator", "synthetic-never-an-account")


def migrate(engine, tenant, store, runner):
    return migration_control.migrate_controlled(
        engine,
        tenant,
        uuid4(),
        store,
        Path("/ca"),
        Path("/repository"),
        profile="ingestion",
        runner=runner,
    )


def test_f03_to_f04_truthful_target_and_no_baseline_fallback(control):
    engine, tenant = control
    store = Store(tenant)

    def runner(*_):
        with Session(engine) as session:
            row = session.get(Tenant, tenant)
            assert (row.state, row.migration_state, row.desired_version, row.observed_version) == (
                "PROVISIONING",
                "MIGRATING",
                VERSION,
                None,
            )
        return VERSION

    assert migrate(engine, tenant, store, runner) == VERSION and store.reads == 1
    assert (
        CatalogResolver(engine, profile="ingestion").resolve(AdministrativeTenant(tenant)).tenant_id
        == tenant
    )
    for profile in ("identity", "documents"):
        with pytest.raises(TenantAccessError, match="SCHEMA_INCOMPATIBLE"):
            CatalogResolver(engine, profile=profile).resolve(AdministrativeTenant(tenant))


@pytest.mark.parametrize("prior", ["f01_tenant_0001", "future_head", "f04_tenant_9999"])
def test_wrong_source_stops_before_secret_and_runner(control, prior):
    engine, tenant = control
    with Session(engine) as session, session.begin():
        session.get(Tenant, tenant).desired_version = prior
    store = Store(tenant)
    with pytest.raises(MigrationError, match="IDENTITY_CONFLICT"):
        migrate(engine, tenant, store, lambda *_: pytest.fail("runner must not execute"))
    assert store.reads == 0


@pytest.mark.parametrize("result", ["f03_tenant_0002", "future_head", None])
def test_wrong_runner_never_publishes_f04(control, result):
    engine, tenant = control
    with pytest.raises(MigrationError):
        migrate(engine, tenant, Store(tenant), lambda *_: result)
    with Session(engine) as session:
        row = session.get(Tenant, tenant)
        assert (row.state, row.migration_state, row.desired_version, row.observed_version) == (
            "FAILED",
            "MIGRATION_FAILED",
            VERSION,
            None,
        )


@pytest.mark.parametrize("observed", ["f03_tenant_0002", "f05_tenant_0004", None])
def test_f04_resolver_requires_exact_observed_version(control, observed):
    engine, tenant = control
    with Session(engine) as session, session.begin():
        row = session.get(Tenant, tenant)
        row.desired_version, row.observed_version = VERSION, observed
    with pytest.raises(TenantAccessError, match="SCHEMA_INCOMPATIBLE"):
        CatalogResolver(engine, profile="ingestion").resolve(AdministrativeTenant(tenant))


def test_f03_context_proof_cannot_be_used_for_f04():
    trace = uuid4()
    old = TenantAuthorizer(None, b"k" * 32, profile="documents")
    current = TenantAuthorizer(None, b"k" * 32, profile="ingestion")
    context = AuthorizedTenantContext(
        uuid4(),
        uuid4(),
        ("editor",),
        SecretRef(uuid4(), 1),
        SecretRef(uuid4(), 1),
        trace,
        int(time.time()) + 30,
        "",
    )
    signed = replace(context, _proof=old._sign(context))
    with pytest.raises(AccessError, match="INPUT_INVALID"):
        current.validate(signed, trace)


def test_f04_factory_never_mutates_historical_f03_ddl():
    before = historical()
    expected = {
        t.fullname: str(CreateTable(t).compile(dialect=dialect())) for t in before.sorted_tables
    }
    current = build_metadata()
    assert current.tables["knowledge.document_versions"].c.blob_key.nullable
    after = historical()
    assert {
        t.fullname: str(CreateTable(t).compile(dialect=dialect())) for t in after.sorted_tables
    } == expected
    assert not after.tables["knowledge.document_versions"].c.blob_key.nullable
    assert "knowledge.chunks" not in after.tables


def test_no_cross_plane_foreign_keys():
    for table in build_metadata().tables.values():
        for foreign in table.foreign_keys:
            assert foreign.column.table.schema in {"knowledge", "security", "ops"}
