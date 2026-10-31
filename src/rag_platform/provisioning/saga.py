"""T004 journal and per-tenant coordination. External I/O never holds a control transaction."""

import hashlib
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session

from rag_platform.control.models import (
    AuditControl,
    DbLocation,
    Instance,
    ProvisioningOperation,
    ProvisioningPending,
    ProvisioningStep,
    StorageLocation,
    Tenant,
)
from rag_platform.providers.secrets import SecretStoreError
from rag_platform.provisioning.postgres import SqlProvisioningError
from rag_platform.provisioning.storage import StorageError, StorageNames, StorageTarget
from rag_platform.tenancy.contracts import SecretRef

VERSION = "f01_tenant_0001"
STEPS = ("RESERVE", "SECRETS", "DATABASE", "MIGRATE", "STORAGE", "PROBES")
RESOURCES = ("SQL_DATABASE", "SQL_ROLES", "STORAGE_BUCKET", "STORAGE_USER")


class SagaError(RuntimeError):
    CODES = {
        "LOCK_BUSY",
        "REQUEST_CONFLICT",
        "SECRET_UNAVAILABLE",
        "SECRET_DENIED",
        "SECRET_CONFLICT",
        "SQL_FAILED",
        "STORAGE_FAILED",
        "MIGRATION_FAILED",
        "OWNERSHIP_CONFLICT",
    }

    def __init__(self, code):
        self.code = code if code in self.CODES else "SQL_FAILED"
        super().__init__(self.code)


@dataclass(frozen=True)
class Snapshot:
    operation: UUID
    tenant: UUID
    instance: UUID
    host: str
    port: int
    admin: SecretRef
    sql_refs: tuple[SecretRef, SecretRef, SecretRef]
    storage_endpoint: str
    storage_ref: SecretRef


@contextmanager
def postgres_lock(engine, namespace, identity):
    if engine.dialect.name != "postgresql":
        raise ValueError("Live saga requires PostgreSQL session locks")
    key = int.from_bytes(
        hashlib.sha256((namespace + str(identity)).encode()).digest()[:8], "big", signed=True
    )
    with engine.connect() as connection:
        acquired = connection.scalar(sa.text("SELECT pg_try_advisory_lock(:key)"), {"key": key})
        connection.commit()
        if not acquired:
            raise SagaError("LOCK_BUSY")
        try:
            yield
        finally:
            connection.rollback()
            connection.execute(sa.text("SELECT pg_advisory_unlock(:key)"), {"key": key})
            connection.commit()


def error_code(error, step):
    if isinstance(error, SagaError):
        return (
            error.code
            if error.code not in {"LOCK_BUSY", "REQUEST_CONFLICT"}
            else "OWNERSHIP_CONFLICT"
        )
    if isinstance(error, SecretStoreError):
        code = error.code.value
        return (
            code
            if code in {"SECRET_UNAVAILABLE", "SECRET_DENIED", "SECRET_CONFLICT"}
            else "SECRET_DENIED"
        )
    if (
        isinstance(error, (SqlProvisioningError, StorageError))
        and str(error) == "OWNERSHIP_CONFLICT"
    ):
        return "OWNERSHIP_CONFLICT"
    if step == "MIGRATE":
        return "MIGRATION_FAILED"
    return "STORAGE_FAILED" if step == "STORAGE" else "SQL_FAILED"


class Saga:
    def __init__(self, engine, backend_factory, *, locks=None):
        self.engine = engine
        self.factory = backend_factory
        self.locks = locks or (lambda ns, id: postgres_lock(engine, ns, id))

    def reserve(self, key: UUID, instance_id: UUID, endpoint: str, actor: UUID):
        if not all(isinstance(v, UUID) for v in (key, instance_id, actor)):
            raise ValueError("Trusted UUIDs required")
        # Parse/validate the trusted endpoint without opening a network connection.
        target = StorageTarget(endpoint, Path("/unused-public-ca"))
        endpoint = target.endpoint
        target.close()
        with self.locks("f01-saga-key:", key), Session(self.engine) as session, session.begin():
            instance = session.get(Instance, instance_id)
            if instance is None:
                raise SagaError("REQUEST_CONFLICT")
            operation = session.scalar(
                sa.select(ProvisioningOperation).where(ProvisioningOperation.idempotency_key == key)
            )
            if operation is None:
                tenant_id, operation_id = uuid4(), uuid4()
                session.add(Tenant(id=tenant_id, desired_version=VERSION))
                session.flush()
                operation = ProvisioningOperation(
                    id=operation_id, tenant_id=tenant_id, idempotency_key=key
                )
                session.add(operation)
                session.flush()
                session.add(
                    DbLocation(
                        tenant_id=tenant_id,
                        instance_id=instance_id,
                        db_name="rag_t_" + tenant_id.hex,
                        app_secret_ref=uuid4(),
                        app_secret_version=1,
                        migrator_secret_ref=uuid4(),
                        migrator_secret_version=1,
                        readonly_secret_ref=uuid4(),
                        readonly_secret_version=1,
                    )
                )
                session.add(
                    StorageLocation(
                        tenant_id=tenant_id,
                        endpoint=endpoint,
                        bucket=StorageNames(tenant_id).bucket,
                        credential_ref=uuid4(),
                        credential_version=1,
                    )
                )
                for step in STEPS:
                    session.add(
                        ProvisioningStep(
                            operation_id=operation_id,
                            step=step,
                            state="SUCCEEDED" if step == "RESERVE" else "PENDING",
                        )
                    )
                session.add(
                    AuditControl(
                        id=uuid4(),
                        tenant_id=tenant_id,
                        operation_id=operation_id,
                        actor_id=actor,
                        event_code="PROVISION_REQUESTED",
                        outcome="OK",
                    )
                )
                session.flush()
            location = session.get(DbLocation, operation.tenant_id)
            storage = session.get(StorageLocation, operation.tenant_id)
            tenant = session.get(Tenant, operation.tenant_id)
            if (
                location is None
                or storage is None
                or tenant is None
                or location.instance_id != instance_id
                or storage.endpoint != endpoint
                or tenant.desired_version != VERSION
                or location.db_name != "rag_t_" + tenant.id.hex
                or storage.bucket != StorageNames(tenant.id).bucket
            ):
                raise SagaError("REQUEST_CONFLICT")
            refs = tuple(
                SecretRef(
                    getattr(location, kind + "_secret_ref"),
                    getattr(location, kind + "_secret_version"),
                )
                for kind in ("migrator", "app", "readonly")
            )
            return Snapshot(
                operation.id,
                tenant.id,
                instance.id,
                instance.host,
                instance.port,
                SecretRef(instance.admin_secret_ref, instance.admin_secret_version),
                refs,
                storage.endpoint,
                SecretRef(storage.credential_ref, storage.credential_version),
            )

    def _step(self, snap, step, state, actor, code="NONE"):
        with Session(self.engine) as session, session.begin():
            entry = session.get(ProvisioningStep, (snap.operation, step))
            entry.state, entry.error_code = state, code
            if state == "RUNNING" and step == "MIGRATE":
                session.get(Tenant, snap.tenant).migration_state = "MIGRATING"
            if state == "SUCCEEDED":
                if step == "MIGRATE":
                    tenant = session.get(Tenant, snap.tenant)
                    tenant.migration_state, tenant.observed_version = "READY", VERSION
                session.add(
                    AuditControl(
                        id=uuid4(),
                        tenant_id=snap.tenant,
                        operation_id=snap.operation,
                        actor_id=actor,
                        event_code="STEP_COMPLETED",
                        outcome="OK",
                    )
                )

    def run(self, key, instance_id, endpoint, actor, *, hook=None):
        snap = self.reserve(key, instance_id, endpoint, actor)
        with self.locks("f01-saga-tenant:", snap.tenant):
            with Session(self.engine) as session, session.begin():
                operation = session.get(ProvisioningOperation, snap.operation)
                tenant = session.get(Tenant, snap.tenant)
                if operation.state == "SUCCEEDED":
                    states = session.scalars(
                        sa.select(ProvisioningStep.state).where(
                            ProvisioningStep.operation_id == snap.operation
                        )
                    ).all()
                    if (
                        tenant.state != "READY"
                        or tenant.migration_state != "READY"
                        or tenant.observed_version != VERSION
                        or len(states) != len(STEPS)
                        or any(value != "SUCCEEDED" for value in states)
                    ):
                        raise SagaError("REQUEST_CONFLICT")
                    return snap
                if tenant.state == "SUSPENDED":
                    raise SagaError("REQUEST_CONFLICT")
                operation.state, operation.error_code = "RUNNING", "NONE"
                operation.attempts += 1
                tenant.state = "PROVISIONING"
            backend = None
            step = "SECRETS"
            try:
                backend = self.factory(snap)
                for step in STEPS[1:]:
                    self._step(snap, step, "RUNNING", actor)
                    if hook:
                        hook(step, "before", snap)
                    result = getattr(backend, step.lower())()
                    if step == "MIGRATE" and result != VERSION:
                        raise SagaError("MIGRATION_FAILED")
                    if hook:
                        hook(step, "after", snap)
                    self._step(snap, step, "SUCCEEDED", actor)
            except Exception as error:
                code = error_code(error, step)
                try:
                    dispositions = backend.compensate() if backend else {}
                except Exception:
                    dispositions = {}
                with Session(self.engine) as session, session.begin():
                    operation = session.get(ProvisioningOperation, snap.operation)
                    tenant = session.get(Tenant, snap.tenant)
                    operation.state, operation.error_code = "FAILED", code
                    tenant.state = "FAILED"
                    if step == "MIGRATE":
                        tenant.migration_state, tenant.observed_version = "MIGRATION_FAILED", None
                    entry = session.get(ProvisioningStep, (snap.operation, step))
                    entry.state, entry.error_code = "FAILED", code
                    names = {
                        "SQL_DATABASE": "rag_t_" + snap.tenant.hex,
                        "SQL_ROLES": "rag_t_" + snap.tenant.hex,
                        "STORAGE_BUCKET": StorageNames(snap.tenant).bucket,
                        "STORAGE_USER": StorageNames(snap.tenant).user,
                    }
                    for resource in RESOURCES:
                        status = dispositions.get(resource, "REVIEW")
                        if status not in {"ABSENT", "PRESERVED", "ACCESS_REVOKED", "REVIEW"}:
                            status = "REVIEW"
                        pending = session.get(ProvisioningPending, (snap.operation, resource))
                        if pending is None:
                            pending = ProvisioningPending(
                                operation_id=snap.operation,
                                resource=resource,
                                resource_name=names[resource],
                            )
                            session.add(pending)
                        pending.disposition = status
                        dispositions[resource] = status
                    operation.compensation_state = (
                        "REVIEW"
                        if any(dispositions.get(k, "REVIEW") == "REVIEW" for k in RESOURCES)
                        else "REVOKED"
                    )
                    session.add(
                        AuditControl(
                            id=uuid4(),
                            tenant_id=snap.tenant,
                            operation_id=snap.operation,
                            actor_id=actor,
                            event_code="STEP_FAILED",
                            outcome="FAILED",
                        )
                    )
                raise SagaError(code) from None
            else:
                # A lost final COMMIT response is reconciled on retry. Do not revoke
                # external access after a possibly committed READY transition.
                with Session(self.engine) as session, session.begin():
                    tenant = session.get(Tenant, snap.tenant)
                    if tenant.migration_state != "READY" or tenant.observed_version != VERSION:
                        raise SagaError("MIGRATION_FAILED")
                    operation = session.get(ProvisioningOperation, snap.operation)
                    tenant.state, operation.state = "READY", "SUCCEEDED"
                    operation.compensation_state = "NONE"
                    for item in session.scalars(
                        sa.select(ProvisioningPending).where(
                            ProvisioningPending.operation_id == snap.operation
                        )
                    ):
                        item.disposition = "RESOLVED"
                return snap
