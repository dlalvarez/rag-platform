"""F03 version gates: legacy defaults, fail-closed mismatches and truthful publication."""

from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from rag_platform.control.identity import AccessError
from rag_platform.control.models import Base, DbLocation, Instance, ProvisioningOperation, Tenant
from rag_platform.documents.schema import VERSION
from rag_platform.providers.secrets import Credential
from rag_platform.provisioning import migration_control
from rag_platform.provisioning.migrations import MigrationError
from rag_platform.tenancy.authorization import AuthorizedTenantContext, TenantAuthorizer
from rag_platform.tenancy.contracts import SecretRef
from rag_platform.tenancy.profiles import IDENTITY_VERSION
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
                desired_version=IDENTITY_VERSION,
                observed_version=IDENTITY_VERSION,
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

    def read(self, _):
        self.reads += 1
        return Credential("rag_t_" + self.tenant.hex + "_migrator", "synthetic-never-print")


def test_document_publication_occurs_only_after_matching_runner_version(control):
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

    migration_control.migrate_controlled(
        engine,
        tenant,
        uuid4(),
        store,
        Path("/ca"),
        Path("/repository"),
        profile="documents",
        runner=runner,
    )
    assert (
        CatalogResolver(engine, profile="documents").resolve(AdministrativeTenant(tenant)).tenant_id
        == tenant
    )
    with pytest.raises(TenantAccessError, match="SCHEMA_INCOMPATIBLE"):
        CatalogResolver(engine).resolve(AdministrativeTenant(tenant))
    with Session(engine) as session:
        row = session.get(Tenant, tenant)
        assert (row.state, row.migration_state, row.observed_version) == ("READY", "READY", VERSION)


@pytest.mark.parametrize("returned", [IDENTITY_VERSION, "future_head", None])
def test_wrong_runner_result_never_sets_false_ready(control, returned):
    engine, tenant = control
    with pytest.raises(MigrationError):
        migration_control.migrate_controlled(
            engine,
            tenant,
            uuid4(),
            Store(tenant),
            Path("/ca"),
            Path("/repository"),
            profile="documents",
            runner=lambda *_: returned,
        )
    with Session(engine) as session:
        row = session.get(Tenant, tenant)
        assert (row.state, row.migration_state, row.desired_version, row.observed_version) == (
            "FAILED",
            "MIGRATION_FAILED",
            VERSION,
            None,
        )


def test_unknown_desired_version_stops_before_secret_read_or_runner(control):
    engine, tenant = control
    with Session(engine) as session, session.begin():
        session.get(Tenant, tenant).desired_version = "future_head"
    store = Store(tenant)
    with pytest.raises(MigrationError, match="IDENTITY_CONFLICT"):
        migration_control.migrate_controlled(
            engine,
            tenant,
            uuid4(),
            store,
            Path("/ca"),
            Path("/repository"),
            profile="documents",
            runner=lambda *_: pytest.fail("unexpected runner"),
        )
    assert store.reads == 0


@pytest.mark.parametrize("profile", ["head", "f03_tenant_0002", "*", "", None, ["documents"]])
def test_unknown_profile_never_queries_catalog_or_reads_secret(profile):
    with pytest.raises(ValueError):
        CatalogResolver(None, profile=profile)
    with pytest.raises(ValueError):
        TenantAuthorizer(None, b"x" * 32, profile=profile)


@pytest.mark.parametrize(
    "desired,observed,state",
    [
        (VERSION, IDENTITY_VERSION, "READY"),
        (VERSION, "future_head", "READY"),
        ("future_head", VERSION, "READY"),
        (VERSION, VERSION, "MIGRATING"),
    ],
)
def test_document_resolver_requires_exact_version_and_ready(control, desired, observed, state):
    engine, tenant = control
    with Session(engine) as session, session.begin():
        row = session.get(Tenant, tenant)
        row.desired_version, row.observed_version, row.migration_state = desired, observed, state
    with pytest.raises(TenantAccessError, match="SCHEMA_INCOMPATIBLE"):
        CatalogResolver(engine, profile="documents").resolve(AdministrativeTenant(tenant))


def test_context_signature_cannot_cross_schema_profiles():
    import time

    key, trace = b"k" * 32, uuid4()
    identity = TenantAuthorizer(None, key)
    document = TenantAuthorizer(None, key, profile="documents")
    context = AuthorizedTenantContext(
        uuid4(),
        uuid4(),
        ("reader",),
        SecretRef(uuid4(), 1),
        SecretRef(uuid4(), 1),
        trace,
        int(time.time()) + 30,
        "",
    )
    context = replace(context, _proof=document._sign(context))
    with pytest.raises(AccessError, match="INPUT_INVALID"):
        identity.validate(context, trace)


def test_historical_ddl_factory_is_not_mutated_by_runtime_tables():
    from rag_platform.documents.schema_f03_0002 import build_metadata

    first, replay = build_metadata(), build_metadata()
    sa.Table("future_phase_probe", first, sa.Column("id", sa.Integer()), schema="knowledge")
    assert "knowledge.future_phase_probe" not in replay.tables
    assert first.tables["knowledge.documents"] is not replay.tables["knowledge.documents"]
