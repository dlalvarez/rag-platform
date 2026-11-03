"""Known F05 profile admission and future job-kind isolation; no service required."""

import os
import time
from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from rag_platform.control.identity import AccessError
from rag_platform.control.models import Base, DbLocation, Instance, ProvisioningOperation, Tenant
from rag_platform.ingestion.queue import Claim, DurableQueue
from rag_platform.ingestion.queue_schema import jobs
from rag_platform.provisioning import migration_control
from rag_platform.provisioning.migrations import MigrationError
from rag_platform.tenancy.authorization import AuthorizedTenantContext, TenantAuthorizer
from rag_platform.tenancy.contracts import SecretRef
from rag_platform.tenancy.profiles import EMBEDDINGS_VERSION, migration_sources, version_for
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
                desired_version="f04_tenant_0003",
                observed_version="f04_tenant_0003",
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
    def read(self, ref):
        pytest.fail("secret access was not allowed")


@pytest.mark.parametrize("source", ["f01_tenant_0001", "f03_tenant_0002", "f05_tenant_9999"])
def test_wrong_source_rejected_before_migration_secret(control, source):
    engine, tenant = control
    with Session(engine) as session, session.begin():
        session.get(Tenant, tenant).desired_version = source
    with pytest.raises(MigrationError, match="IDENTITY_CONFLICT"):
        migration_control.migrate_controlled(
            engine,
            tenant,
            uuid4(),
            Store(),
            Path("/ca"),
            Path("/repo"),
            profile="embeddings",
            runner=lambda *_: pytest.fail("wrong runner"),
        )


def test_f04_not_implicitly_resolved_as_f05(control):
    engine, tenant = control
    with pytest.raises(TenantAccessError, match="SCHEMA_INCOMPATIBLE"):
        CatalogResolver(engine, profile="embeddings").resolve(AdministrativeTenant(tenant))


def test_f05_exact_head_rejected_by_old_profiles(control):
    engine, tenant = control
    with Session(engine) as session, session.begin():
        row = session.get(Tenant, tenant)
        row.desired_version = row.observed_version = EMBEDDINGS_VERSION
    assert (
        CatalogResolver(engine, profile="embeddings")
        .resolve(AdministrativeTenant(tenant))
        .tenant_id
        == tenant
    )
    for profile in ("identity", "documents", "ingestion"):
        with pytest.raises(TenantAccessError, match="SCHEMA_INCOMPATIBLE"):
            CatalogResolver(engine, profile=profile).resolve(AdministrativeTenant(tenant))


@pytest.mark.parametrize("observed", [None, "f04_tenant_0003", "f05_tenant_9999"])
def test_f05_does_not_accept_stale_or_future_observed_head(control, observed):
    engine, tenant = control
    with Session(engine) as session, session.begin():
        row = session.get(Tenant, tenant)
        row.desired_version, row.observed_version = EMBEDDINGS_VERSION, observed
    with pytest.raises(TenantAccessError, match="SCHEMA_INCOMPATIBLE"):
        CatalogResolver(engine, profile="embeddings").resolve(AdministrativeTenant(tenant))


def test_f04_context_proof_not_valid_in_f05_before_database_access():
    old = TenantAuthorizer(None, b"k" * 32, profile="ingestion")
    current = TenantAuthorizer(None, b"k" * 32, profile="embeddings")
    trace = uuid4()
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
    with pytest.raises(AccessError, match="INPUT_INVALID"):
        current.validate(replace(context, _proof=old._sign(context)), trace)


def test_known_migration_sources_are_not_general_future_head_acceptance():
    assert migration_sources("embeddings") == {"f04_tenant_0003", EMBEDDINGS_VERSION}
    assert version_for("ingestion") == "f04_tenant_0003"
    with pytest.raises(ValueError):
        version_for("future_profile")


def test_ingest_consumer_neither_claims_nor_acknowledges_future_embed_job():
    engine = sa.create_engine("sqlite://")
    jobs.create(engine)
    queue = DurableQueue(engine, tenant_scope=(UUID(int=1),))
    ident = queue.enqueue(UUID(int=1), UUID(int=2), UUID(int=3), UUID(int=4), UUID(int=5))
    token = uuid4()
    with engine.begin() as c:
        # Simulate a future deployed envelope without mutating frozen F04 metadata.
        c.exec_driver_sql("PRAGMA ignore_check_constraints=ON")
        c.execute(sa.update(jobs).where(jobs.c.id == ident).values(kind="EMBED"))
        c.exec_driver_sql("PRAGMA ignore_check_constraints=OFF")
    assert queue.claim() is None
    with engine.begin() as c:
        c.exec_driver_sql("PRAGMA ignore_check_constraints=ON")
        now = c.scalar(sa.select(sa.func.current_timestamp()))
        from datetime import timedelta

        c.execute(
            sa.update(jobs)
            .where(jobs.c.id == ident)
            .values(
                status="RUNNING",
                attempts=1,
                lease_token=token,
                lease_until=now + timedelta(seconds=60),
            )
        )
        c.exec_driver_sql("PRAGMA ignore_check_constraints=OFF")
    forged = Claim(ident, UUID(int=1), UUID(int=2), UUID(int=3), UUID(int=4), 1, token)
    assert not queue.complete(forged) and not queue.heartbeat(forged)
    engine.dispose()


@pytest.mark.parametrize(
    "f03,f04,f05", [("1", "1", "yes"), ("1", "0", "1"), ("0", "1", "1"), ("0", "0", "1")]
)
def test_f05_flags_cannot_bypass_parent_profiles(monkeypatch, f03, f04, f05):
    from rag_platform import identity_api

    disposed = []
    monkeypatch.setattr(identity_api, "OIDCSettings", lambda **kwargs: object())
    monkeypatch.setattr(identity_api, "Target", lambda *args: object())
    monkeypatch.setattr(identity_api, "private_file", lambda *args: b"k" * 32)
    monkeypatch.setattr(
        identity_api,
        "control_engine",
        lambda *args: SimpleNamespace(dispose=lambda: disposed.append(True)),
    )
    for name, value in {
        "RAG_OIDC_ISSUER": "https://issuer.invalid",
        "RAG_OIDC_AUDIENCE": "api",
        "RAG_OIDC_JWKS": "https://issuer.invalid/keys",
        "RAG_F03_ENABLED": f03,
        "RAG_F04_ENABLED": f04,
        "RAG_F05_ENABLED": f05,
    }.items():
        monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match="Invalid private API configuration"):
        identity_api.create_configured_app()
    assert disposed == [True]


def _assert_configured_profile(monkeypatch, enabled, expected):
    from rag_platform import identity_api
    from rag_platform.documents import api as documents_api

    recorded = {}
    monkeypatch.setattr(identity_api, "OIDCSettings", lambda **kwargs: object())
    monkeypatch.setattr(identity_api, "Target", lambda *args: object())
    monkeypatch.setattr(identity_api, "private_file", lambda *args: b"k" * 32)
    monkeypatch.setattr(identity_api, "control_engine", lambda *args: object())
    monkeypatch.setattr(identity_api, "OIDCVerifier", lambda *args: object())

    def create(*args, **kwargs):
        recorded["profiles"] = kwargs["profiles"]
        return object()

    def configure(*args, **kwargs):
        recorded["profile"] = kwargs["profile"]
        recorded["search_socket"] = kwargs["search_socket"]

    monkeypatch.setattr(identity_api, "create_app", create)
    monkeypatch.setattr(documents_api, "configure", configure)
    for name, value in {
        "RAG_OIDC_ISSUER": "https://issuer.invalid",
        "RAG_OIDC_AUDIENCE": "api",
        "RAG_OIDC_JWKS": "https://issuer.invalid/keys",
        "RAG_F03_ENABLED": "1",
        "RAG_F04_ENABLED": "1",
        "RAG_F05_ENABLED": enabled,
    }.items():
        monkeypatch.setenv(name, value)
    identity_api.create_configured_app()
    assert recorded == {
        "profiles": ("identity", expected),
        "profile": expected,
        "search_socket": (
            Path("/run/f05-query/qwen.sock")
            if os.environ.get("RAG_F05_SEARCH_ENABLED") == "1"
            else None
        ),
    }


@pytest.mark.parametrize("observed", [EMBEDDINGS_VERSION, "f04_tenant_0003"])
def test_controlled_f05_target_is_truthful_and_wrong_runner_never_ready(control, observed):
    from rag_platform.providers.secrets import Credential

    engine, tenant = control
    store = SimpleNamespace(read=lambda ref: Credential("synthetic", "not-an-account"))

    def runner(*args):
        with Session(engine) as session:
            row = session.get(Tenant, tenant)
            assert row.desired_version == EMBEDDINGS_VERSION
            assert row.observed_version is None and row.migration_state == "MIGRATING"
        return observed

    if observed == EMBEDDINGS_VERSION:
        assert (
            migration_control.migrate_controlled(
                engine,
                tenant,
                uuid4(),
                store,
                Path("/ca"),
                Path("/repo"),
                profile="embeddings",
                runner=runner,
            )
            == EMBEDDINGS_VERSION
        )
    else:
        with pytest.raises(MigrationError):
            migration_control.migrate_controlled(
                engine,
                tenant,
                uuid4(),
                store,
                Path("/ca"),
                Path("/repo"),
                profile="embeddings",
                runner=runner,
            )
        with Session(engine) as session:
            row = session.get(Tenant, tenant)
            assert row.state == "FAILED" and row.observed_version is None


def test_invalid_worker_profile_stops_before_secret_access(monkeypatch):
    from rag_platform.ingestion import worker_main

    monkeypatch.setenv("RAG_F05_ENABLED", "unexpected")
    monkeypatch.setattr(worker_main.resource, "setrlimit", lambda *args: None)
    monkeypatch.setattr(worker_main, "private_file", lambda *args: pytest.fail("secret read"))
    with pytest.raises(ValueError, match="Invalid worker profile"):
        worker_main.main()


def test_publication_profile_requires_its_exact_head_and_rejects_older_profiles(control):
    engine, tenant = control
    with pytest.raises(TenantAccessError, match="SCHEMA_INCOMPATIBLE"):
        CatalogResolver(engine, profile="embedding_publication").resolve(
            AdministrativeTenant(tenant)
        )
    with Session(engine) as session, session.begin():
        row = session.get(Tenant, tenant)
        row.desired_version = row.observed_version = "f05_tenant_0006"
    assert (
        CatalogResolver(engine, profile="embedding_publication")
        .resolve(AdministrativeTenant(tenant))
        .tenant_id
        == tenant
    )
    for profile in ("identity", "documents", "ingestion", "embeddings"):
        with pytest.raises(TenantAccessError, match="SCHEMA_INCOMPATIBLE"):
            CatalogResolver(engine, profile=profile).resolve(AdministrativeTenant(tenant))


@pytest.mark.parametrize(
    "observed", [None, "f05_tenant_0004", "f05_tenant_0005", "f05_tenant_9999"]
)
def test_publication_profile_has_no_stale_or_future_head_fallback(control, observed):
    engine, tenant = control
    with Session(engine) as session, session.begin():
        row = session.get(Tenant, tenant)
        row.desired_version, row.observed_version = "f05_tenant_0006", observed
    with pytest.raises(TenantAccessError, match="SCHEMA_INCOMPATIBLE"):
        CatalogResolver(engine, profile="embedding_publication").resolve(
            AdministrativeTenant(tenant)
        )


@pytest.mark.parametrize("old_profile", ["documents", "ingestion", "embeddings"])
def test_publication_context_rejects_previous_profile_proofs_before_io(old_profile):
    old = TenantAuthorizer(None, b"k" * 32, profile=old_profile)
    current = TenantAuthorizer(None, b"k" * 32, profile="embedding_publication")
    trace = uuid4()
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
    with pytest.raises(AccessError, match="INPUT_INVALID"):
        current.validate(replace(context, _proof=old._sign(context)), trace)


def test_publication_migration_sources_are_explicit():
    assert version_for("embedding_publication") == "f05_tenant_0006"
    assert migration_sources("embedding_publication") == {
        "f05_tenant_0004",
        "f05_tenant_0005",
        "f05_tenant_0006",
    }
    assert version_for("embeddings") == "f05_tenant_0004"


@pytest.mark.parametrize("f05,publication", [("0", "1"), ("1", "yes")])
def test_publication_worker_flags_fail_before_secret_access(monkeypatch, f05, publication):
    from rag_platform.ingestion import worker_main

    monkeypatch.setenv("RAG_F05_ENABLED", f05)
    monkeypatch.setenv("RAG_F05_PUBLICATION_ENABLED", publication)
    monkeypatch.setattr(worker_main.resource, "setrlimit", lambda *args: None)
    monkeypatch.setattr(worker_main, "private_file", lambda *args: pytest.fail("secret read"))
    with pytest.raises(ValueError, match="Invalid worker profile"):
        worker_main.main()


@pytest.mark.parametrize("f05,publication", [("0", "1"), ("1", "yes")])
def test_publication_api_flag_requires_valid_foundation(monkeypatch, f05, publication):
    from rag_platform import identity_api

    disposed = []
    monkeypatch.setattr(identity_api, "OIDCSettings", lambda **kwargs: object())
    monkeypatch.setattr(identity_api, "Target", lambda *args: object())
    monkeypatch.setattr(identity_api, "private_file", lambda *args: b"k" * 32)
    monkeypatch.setattr(
        identity_api,
        "control_engine",
        lambda *args: SimpleNamespace(dispose=lambda: disposed.append(True)),
    )
    for name, value in {
        "RAG_OIDC_ISSUER": "https://issuer.invalid",
        "RAG_OIDC_AUDIENCE": "api",
        "RAG_OIDC_JWKS": "https://issuer.invalid/keys",
        "RAG_F03_ENABLED": "1",
        "RAG_F04_ENABLED": "1",
        "RAG_F05_ENABLED": f05,
        "RAG_F05_PUBLICATION_ENABLED": publication,
    }.items():
        monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match="Invalid private API configuration"):
        identity_api.create_configured_app()
    assert disposed == [True]


@pytest.mark.parametrize(
    "enabled,publication,expected",
    [
        ("0", "0", "ingestion"),
        ("1", "0", "embeddings"),
        ("1", "1", "embedding_publication"),
    ],
)
def test_configured_profile_is_explicit_and_keeps_previous_default(
    monkeypatch, enabled, publication, expected
):
    monkeypatch.setenv("RAG_F05_PUBLICATION_ENABLED", publication)
    _assert_configured_profile(monkeypatch, enabled, expected)


@pytest.mark.parametrize("observed", ["f05_tenant_0006", "f05_tenant_0004"])
def test_controlled_publication_target_never_marks_wrong_runner_ready(control, observed):
    from rag_platform.providers.secrets import Credential

    engine, tenant = control
    with Session(engine) as session, session.begin():
        row = session.get(Tenant, tenant)
        row.desired_version = row.observed_version = "f05_tenant_0004"
    store = SimpleNamespace(read=lambda ref: Credential("synthetic", "not-an-account"))

    def runner(*args):
        with Session(engine) as session:
            row = session.get(Tenant, tenant)
            assert row.desired_version == "f05_tenant_0006"
            assert row.observed_version is None and row.migration_state == "MIGRATING"
        return observed

    if observed == "f05_tenant_0006":
        assert (
            migration_control.migrate_controlled(
                engine,
                tenant,
                uuid4(),
                store,
                Path("/ca"),
                Path("/repo"),
                profile="embedding_publication",
                runner=runner,
            )
            == observed
        )
    else:
        with pytest.raises(MigrationError):
            migration_control.migrate_controlled(
                engine,
                tenant,
                uuid4(),
                store,
                Path("/ca"),
                Path("/repo"),
                profile="embedding_publication",
                runner=runner,
            )
        with Session(engine) as session:
            row = session.get(Tenant, tenant)
            assert row.state == "FAILED" and row.observed_version is None


@pytest.mark.parametrize("source", ["f04_tenant_0003", "f05_tenant_9999", "f01_tenant_0001"])
def test_publication_wrong_migration_source_denied_before_secret(control, source):
    engine, tenant = control
    with Session(engine) as session, session.begin():
        session.get(Tenant, tenant).desired_version = source
    with pytest.raises(MigrationError, match="IDENTITY_CONFLICT"):
        migration_control.migrate_controlled(
            engine,
            tenant,
            uuid4(),
            Store(),
            Path("/ca"),
            Path("/repo"),
            profile="embedding_publication",
            runner=lambda *_: pytest.fail("wrong runner"),
        )


@pytest.mark.parametrize("search,publication", [("1", "0"), ("bad", "1")])
def test_search_flag_requires_explicit_publication(monkeypatch, search, publication):
    monkeypatch.setenv("RAG_F05_SEARCH_ENABLED", search)
    test_publication_api_flag_requires_valid_foundation(monkeypatch, "1", publication)


@pytest.mark.parametrize("search", ["0", "1"])
def test_search_socket_is_only_configured_when_enabled(monkeypatch, search):
    monkeypatch.setenv("RAG_F05_SEARCH_ENABLED", search)
    monkeypatch.setenv("RAG_F05_PUBLICATION_ENABLED", "1")
    _assert_configured_profile(monkeypatch, "1", "embedding_publication")
