"""Bounded per-process pools. No database/role switching or credential fallback."""

import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import RLock

import sqlalchemy as sa
from sqlalchemy.exc import TimeoutError as PoolTimeout
from sqlalchemy.orm import Session
from sqlalchemy.pool import QueuePool

from rag_platform.providers.secrets import SecretStoreError
from rag_platform.provisioning.postgres import Target
from rag_platform.tenancy.resolver import AdministrativeTenant, TenantAccessError


@dataclass
class Entry:
    engine: object
    active: int = 0
    retired: bool = False
    touched: int = 0


def tenant_engine(destination, store, ca: Path):
    def connect():
        credential = store.read(destination.credential)
        if credential.username != destination.username:
            raise TenantAccessError("SECRET_UNAVAILABLE")
        return Target(destination.host, destination.port, ca).connect(
            destination.database, credential
        )

    return sa.create_engine(
        "postgresql+psycopg://",
        creator=connect,
        poolclass=QueuePool,
        pool_size=2,
        max_overflow=0,
        pool_timeout=5,
        pool_pre_ping=True,
        pool_reset_on_return="rollback",
        hide_parameters=True,
    )


class ConnectionRegistry:
    """At most four engines, two connections each, including draining engines.

    Only administrative contexts from the trusted CLI boundary are accepted.
    Re-resolves catalog and checks SecretStore on every acquisition (no value cache).
    Limits are per process; worker processes must use spawn and a fresh registry.
    """

    _budget_lock = RLock()
    _budget_pid = os.getpid()
    _owner = None

    def __init__(self, resolver, store, ca: Path, *, engine_factory=tenant_engine):
        self.resolver, self.store, self.ca = resolver, store, ca
        self.engine_factory = engine_factory
        self._entries = {}
        self._lock = RLock()
        self._clock = 0
        self._closed = False
        self._pid = os.getpid()
        cls = ConnectionRegistry
        if cls._budget_pid != self._pid:
            # Spawn starts a clean process. Forked children cannot reuse this module budget.
            raise TenantAccessError("REGISTRY_CLOSED")
        with cls._budget_lock:
            if cls._owner is not None:
                raise TenantAccessError("CAPACITY")
            cls._owner = self

    @contextmanager
    def _guard(self):
        if os.getpid() != self._pid:
            raise TenantAccessError("REGISTRY_CLOSED")
        if not self._lock.acquire(timeout=5):
            raise TenantAccessError("CAPACITY")
        try:
            yield
        finally:
            self._lock.release()

    def _retire(self, key):
        entry = self._entries[key]
        entry.retired = True
        if not entry.active:
            entry.engine.dispose()
            del self._entries[key]

    def _tenant_retire(self, tenant_id, role=None, keep=None):
        for key in list(self._entries):
            if key.tenant_id == tenant_id and (role is None or key.role == role) and key != keep:
                self._retire(key)

    def _lease(self, context, role):
        if not isinstance(context, AdministrativeTenant):
            raise TenantAccessError("INVALID_CONTEXT")
        with self._guard():
            if self._closed:
                raise TenantAccessError("REGISTRY_CLOSED")
            try:
                destination = self.resolver.resolve(context, role)
            except TenantAccessError:
                self._tenant_retire(context.tenant_id)
                raise
            # A changed endpoint, database, reference UUID or version retires old pools.
            self._tenant_retire(context.tenant_id, role, keep=destination)
            try:
                credential = self.store.read(destination.credential)
                if credential.username != destination.username:
                    raise TenantAccessError("SECRET_UNAVAILABLE")
                del credential
            except Exception:
                self._tenant_retire(context.tenant_id, role)
                raise TenantAccessError("SECRET_UNAVAILABLE") from None
            entry = self._entries.get(destination)
            if entry is not None and entry.retired:
                # Never resurrect a draining engine after an invalidation.
                raise TenantAccessError("CAPACITY")
            if entry is None:
                if len(self._entries) >= 4:
                    idle = [(key, item) for key, item in self._entries.items() if not item.active]
                    if not idle:
                        raise TenantAccessError("CAPACITY")
                    oldest = min(idle, key=lambda pair: pair[1].touched)[0]
                    self._retire(oldest)
                try:
                    entry = Entry(self.engine_factory(destination, self.store, self.ca))
                except Exception:
                    raise TenantAccessError("CONNECTION_FAILED") from None
                self._entries[destination] = entry
            self._clock += 1
            entry.touched = self._clock
            entry.active += 1
            return destination, entry

    def _release_budget(self):
        if self._closed and not self._entries:
            with ConnectionRegistry._budget_lock:
                if ConnectionRegistry._owner is self:
                    ConnectionRegistry._owner = None

    def _release(self, destination, entry):
        with self._lock:
            entry.active -= 1
            if entry.retired and not entry.active:
                entry.engine.dispose()
                del self._entries[destination]
            self._release_budget()

    @contextmanager
    def connection(self, context: AdministrativeTenant, role="app"):
        destination, entry = self._lease(context, role)
        connection = None
        try:
            try:
                connection = entry.engine.connect()
            except PoolTimeout:
                raise TenantAccessError("POOL_TIMEOUT") from None
            except SecretStoreError:
                raise TenantAccessError("SECRET_UNAVAILABLE") from None
            except TenantAccessError:
                raise
            except Exception:
                raise TenantAccessError("CONNECTION_FAILED") from None
            yield connection
        finally:
            try:
                if connection is not None:
                    connection.close()  # rollback on return; no cross-request transaction
            finally:
                self._release(destination, entry)

    @contextmanager
    def get_tenant_session(self, context: AdministrativeTenant, role="app"):
        with self.connection(context, role) as connection, Session(bind=connection) as session:
            with session.begin():
                yield session

    def close(self):
        with self._guard():
            self._closed = True
            for key in list(self._entries):
                self._retire(key)
            self._release_budget()

    def stats(self):
        with self._guard():
            return {
                "engines": len(self._entries),
                "leases": sum(e.active for e in self._entries.values()),
                "draining": sum(e.retired for e in self._entries.values()),
            }
