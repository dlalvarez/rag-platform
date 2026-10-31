"""P5/V03/V06 offline: real QueuePool capacity, rollback and safe draining."""

from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session
from sqlalchemy.pool import QueuePool

from rag_platform.control.models import Base, DbLocation, Instance, Tenant
from rag_platform.providers.secrets import Credential, SecretErrorCode, SecretStoreError
from rag_platform.tenancy.contracts import SecretRef
from rag_platform.tenancy.registry import ConnectionRegistry
from rag_platform.tenancy.resolver import (
    VERSION,
    AdministrativeTenant,
    CatalogResolver,
    ResolvedDatabase,
    TenantAccessError,
)


class Resolver:
    def __init__(self):
        self.destinations = {}
        self.denied = False

    def resolve(self, context, role):
        if self.denied:
            raise TenantAccessError("TENANT_UNAVAILABLE")
        return replace(self.destinations[context.tenant_id], role=role)


class Store:
    denied = False

    def __init__(self, resolver):
        self.resolver = resolver
        self.values = {}

    def read(self, ref):
        if self.denied:
            raise SecretStoreError(SecretErrorCode.DENIED)
        for d in self.resolver.destinations.values():
            if d.credential == ref:
                return self.values.get(ref, Credential(d.username, "offline-synthetic"))
        raise SecretStoreError(SecretErrorCode.NOT_FOUND)


@pytest.fixture
def pools():
    resolver = Resolver()
    contexts = []
    for _ in range(5):
        tenant = uuid4()
        contexts.append(AdministrativeTenant(tenant))
        resolver.destinations[tenant] = ResolvedDatabase(
            tenant, uuid4(), "postgres", 5432, "rag_t_" + tenant.hex, "app", SecretRef(uuid4(), 1)
        )
    created = []
    disposed = []
    store = Store(resolver)

    def factory(destination, *_):
        engine = sa.create_engine(
            "sqlite://",
            poolclass=QueuePool,
            pool_size=2,
            max_overflow=0,
            pool_timeout=0.03,
            pool_pre_ping=True,
            connect_args={"check_same_thread": False},
        )
        sa.event.listen(engine, "engine_disposed", lambda e: disposed.append(destination))
        created.append((destination, engine))
        return engine

    registry = ConnectionRegistry(resolver, store, Path("/public/ca.crt"), engine_factory=factory)
    yield registry, resolver, store, contexts, created, disposed
    registry.close()


def test_queue_pool_two_connections_and_timeout_release(pools):
    registry, _, _, contexts, created, _ = pools
    with registry.connection(contexts[0]), registry.connection(contexts[0]):
        with (
            pytest.raises(TenantAccessError, match="POOL_TIMEOUT"),
            registry.connection(contexts[0]),
        ):
            pass
        assert registry.stats()["leases"] == 2
        assert created[0][1].pool.checkedout() == 2
    assert registry.stats()["leases"] == 0


def test_global_capacity_counts_active_engines(pools):
    registry, _, _, contexts, _, _ = pools
    from contextlib import ExitStack

    with ExitStack() as stack:
        for context in contexts[:4]:
            stack.enter_context(registry.connection(context))
        with pytest.raises(TenantAccessError, match="CAPACITY"), registry.connection(contexts[4]):
            pass
        assert registry.stats() == {"engines": 4, "leases": 4, "draining": 0}


def test_idle_lru_eviction_and_no_cross_tenant_connection(pools):
    registry, _, _, contexts, created, disposed = pools
    for context in contexts[:4]:
        with registry.connection(context):
            pass
    with registry.connection(contexts[0]):
        pass
    with registry.connection(contexts[4]):
        pass
    assert disposed[0].tenant_id == contexts[1].tenant_id
    assert len(created) == 5 and registry.stats()["engines"] == 4
    assert len({d.credential.id for d, _ in created}) == 5


@pytest.mark.parametrize("change", ["version", "reference", "endpoint", "instance"])
def test_destination_change_drains_active_pool_without_revocation(pools, change):
    registry, resolver, _, contexts, created, disposed = pools
    context = contexts[0]
    old = resolver.destinations[context.tenant_id]
    changes = {
        "version": {"credential": SecretRef(old.credential.id, 2)},
        "reference": {"credential": SecretRef(uuid4(), 1)},
        "endpoint": {"host": "new-postgres"},
        "instance": {"instance_id": uuid4()},
    }
    with registry.connection(context) as previous:
        resolver.destinations[context.tenant_id] = replace(old, **changes[change])
        with registry.connection(context) as current:
            assert previous is not current
            assert previous.scalar(sa.text("SELECT 1")) == 1
            assert registry.stats() == {"engines": 2, "leases": 2, "draining": 1}
            assert old not in disposed
        assert old not in disposed
    assert old in disposed and len(created) == 2
    assert registry.stats()["engines"] == 1


def test_revoked_catalog_or_secret_never_uses_cached_pool(pools):
    registry, resolver, store, contexts, _, _ = pools
    with registry.connection(contexts[0]):
        pass
    store.denied = True
    with (
        pytest.raises(TenantAccessError, match="SECRET_UNAVAILABLE"),
        registry.connection(contexts[0]),
    ):
        pass
    assert registry.stats()["engines"] == 0
    store.denied = False
    with registry.connection(contexts[0]) as active:
        resolver.denied = True
        with (
            pytest.raises(TenantAccessError, match="TENANT_UNAVAILABLE"),
            registry.connection(contexts[0]),
        ):
            pass
        assert active.scalar(sa.text("SELECT 1")) == 1
        assert registry.stats()["draining"] == 1
    assert registry.stats()["engines"] == 0


def test_rollback_on_return_and_close_drains_checked_out(pools):
    registry, _, _, contexts, _, disposed = pools
    with registry.connection(contexts[0]) as connection:
        connection.execute(sa.text("CREATE TABLE probe(value INTEGER)"))
        connection.commit()
        connection.execute(sa.text("INSERT INTO probe VALUES (1)"))
    with registry.connection(contexts[0]) as connection:
        assert connection.scalar(sa.text("SELECT count(*) FROM probe")) == 0
        registry.close()
        assert connection.scalar(sa.text("SELECT 1")) == 1
        assert disposed == []
        with (
            pytest.raises(TenantAccessError, match="REGISTRY_CLOSED"),
            registry.connection(contexts[0]),
        ):
            pass
    assert len(disposed) == 1


def test_wrong_username_is_not_accepted(pools):
    registry, resolver, store, contexts, _, _ = pools
    ref = resolver.destinations[contexts[0].tenant_id].credential
    store.values[ref] = Credential("wrong_tenant_app", "do-not-echo-password")
    with pytest.raises(TenantAccessError, match="SECRET_UNAVAILABLE") as error:
        with registry.connection(contexts[0]):
            pass
    assert "do-not-echo" not in str(error.value)
    assert registry.stats()["engines"] == 0


def test_catalog_requires_ready_compatible_version_and_known_destination():
    engine = sa.create_engine("sqlite://")
    Base.metadata.create_all(engine)
    tenant, instance = uuid4(), uuid4()
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
                readonly_secret_ref=uuid4(),
                readonly_secret_version=1,
            )
        )
    resolver = CatalogResolver(engine)
    context = AdministrativeTenant(tenant)
    assert resolver.resolve(context).host == "postgres"
    assert resolver.resolve(context, "readonly").role == "readonly"
    for invalid in (tenant, str(tenant), {"tenant_id": tenant}):
        with pytest.raises(TenantAccessError, match="INVALID_CONTEXT"):
            resolver.resolve(invalid)
    with pytest.raises(TenantAccessError, match="INVALID_ROLE"):
        resolver.resolve(context, "migrator")
    with pytest.raises(TenantAccessError, match="TENANT_UNAVAILABLE"):
        resolver.resolve(AdministrativeTenant(uuid4()))
    for state in ("SUSPENDED", "FAILED", "PROVISIONING"):
        with Session(engine) as session, session.begin():
            session.get(Tenant, tenant).state = state
        with pytest.raises(TenantAccessError, match="TENANT_UNAVAILABLE"):
            resolver.resolve(context)
    with Session(engine) as session, session.begin():
        row = session.get(Tenant, tenant)
        row.state, row.observed_version = "READY", "incompatible"
    with pytest.raises(TenantAccessError, match="SCHEMA_INCOMPATIBLE"):
        resolver.resolve(context)
    engine.dispose()


def test_eight_concurrent_leases_stay_within_four_engines(pools):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    registry, _, _, contexts, _, _ = pools
    acquired, released = Barrier(9, timeout=5), Barrier(9, timeout=5)

    def worker(context):
        with registry.connection(context) as connection:
            assert connection.scalar(sa.text("SELECT 1")) == 1
            acquired.wait()
            released.wait()

    with ThreadPoolExecutor(max_workers=8) as executor:
        tasks = [executor.submit(worker, context) for context in contexts[:4] for _ in range(2)]
        acquired.wait()
        assert registry.stats() == {"engines": 4, "leases": 8, "draining": 0}
        released.wait()
        for task in tasks:
            task.result()
    assert registry.stats()["leases"] == 0


def test_second_registry_cannot_multiply_process_budget_while_draining(pools):
    registry, resolver, store, contexts, _, _ = pools
    with registry.connection(contexts[0]):
        registry.close()
        with pytest.raises(TenantAccessError, match="CAPACITY"):
            ConnectionRegistry(resolver, store, Path("/public/ca.crt"))
    replacement = ConnectionRegistry(resolver, store, Path("/public/ca.crt"))
    replacement.close()


def test_unexpected_secret_provider_error_is_sanitized(pools):
    registry, _, store, contexts, _, _ = pools

    def broken(ref):
        raise RuntimeError("private-provider-response-password")

    store.read = broken
    with pytest.raises(TenantAccessError, match="SECRET_UNAVAILABLE") as error:
        with registry.connection(contexts[0]):
            pass
    assert "private-provider" not in str(error.value)


def test_inherited_process_cannot_borrow_or_create_registry(pools, monkeypatch):
    import rag_platform.tenancy.registry as module

    registry, resolver, store, contexts, _, _ = pools
    original_pid = module.os.getpid()
    with monkeypatch.context() as patch:
        patch.setattr(module.os, "getpid", lambda: original_pid + 1)
        with pytest.raises(TenantAccessError, match="REGISTRY_CLOSED"):
            with registry.connection(contexts[0]):
                pass
        with pytest.raises(TenantAccessError, match="REGISTRY_CLOSED"):
            ConnectionRegistry(resolver, store, Path("/public/ca.crt"))
