"""F01 administrative operations. Metadata projections never serialize credentials."""

import io
from uuid import UUID, uuid4

import sqlalchemy as sa
from minio.error import S3Error
from sqlalchemy.orm import Session

from rag_platform.control.models import (
    DbLocation,
    Instance,
    ProvisioningOperation,
    ProvisioningPending,
    ProvisioningStep,
    StorageLocation,
    Tenant,
)
from rag_platform.provisioning.live_saga import LiveBackend
from rag_platform.provisioning.migration_control import migrate_controlled
from rag_platform.provisioning.migrations import VERSION, migration_session
from rag_platform.provisioning.postgres import Names, Target
from rag_platform.provisioning.saga import STEPS, Saga, Snapshot, postgres_lock
from rag_platform.provisioning.storage import StorageNames
from rag_platform.tenancy.contracts import SecretRef
from rag_platform.tenancy.registry import ConnectionRegistry
from rag_platform.tenancy.resolver import AdministrativeTenant, CatalogResolver


class AdminError(RuntimeError):
    CODES = {
        "UNKNOWN_TENANT",
        "UNKNOWN_OPERATION",
        "CATALOG_CONFLICT",
        "NOT_READY",
        "CHECK_FAILED",
        "CONFIG_UNAVAILABLE",
    }

    def __init__(self, code):
        self.code = code if code in self.CODES else "CHECK_FAILED"
        super().__init__(self.code)


class Administration:
    def __init__(
        self,
        engine,
        actor,
        store,
        ca,
        storage,
        repository,
        *,
        storage_admin=None,
        backend_factory=None,
        locks=None,
    ):
        if not isinstance(actor, UUID):
            raise AdminError("CONFIG_UNAVAILABLE")
        self.engine, self.actor, self.store = engine, actor, store
        self.ca, self.storage, self.repository = ca, storage, repository
        self.storage_admin = storage_admin
        self.backend_factory = backend_factory or self._backend
        self.locks = locks
        self.saga = Saga(engine, lambda snap: self.backend_factory(snap), locks=locks)

    def _backend(self, snapshot):
        if self.storage_admin is None or self.store is None or self.storage is None:
            raise AdminError("CONFIG_UNAVAILABLE")
        return LiveBackend(
            snapshot, self.store, self.ca, self.storage, self.storage_admin, self.repository
        )

    def instances(self):
        with Session(self.engine) as session:
            return [
                {"instance": str(row.id), "host": row.host, "port": row.port}
                for row in session.scalars(sa.select(Instance).order_by(Instance.id))
            ]

    def show(self, tenant_id):
        with Session(self.engine) as session:
            tenant = session.get(Tenant, tenant_id)
            if tenant is None:
                raise AdminError("UNKNOWN_TENANT")
            operation = session.scalar(
                sa.select(ProvisioningOperation).where(ProvisioningOperation.tenant_id == tenant_id)
            )
            db = session.get(DbLocation, tenant_id)
            storage = session.get(StorageLocation, tenant_id)
            result = {
                "tenant": str(tenant.id),
                "state": tenant.state,
                "migration_state": tenant.migration_state,
                "desired_version": tenant.desired_version,
                "observed_version": tenant.observed_version,
            }
            if db:
                result["database"] = {
                    "instance": str(db.instance_id),
                    "name": db.db_name,
                    "tls": db.ssl_mode,
                }
            if storage:
                result["storage"] = {"endpoint": storage.endpoint, "bucket": storage.bucket}
            if operation:
                result["operation"] = {
                    "id": str(operation.id),
                    "key": str(operation.idempotency_key),
                    "state": operation.state,
                    "attempts": operation.attempts,
                    "error": operation.error_code,
                    "compensation": operation.compensation_state,
                }
                result["steps"] = [
                    {"step": s.step, "state": s.state, "error": s.error_code}
                    for s in session.scalars(
                        sa.select(ProvisioningStep)
                        .where(ProvisioningStep.operation_id == operation.id)
                        .order_by(ProvisioningStep.step)
                    )
                ]
                result["pending"] = [
                    {"resource": p.resource, "name": p.resource_name, "state": p.disposition}
                    for p in session.scalars(
                        sa.select(ProvisioningPending)
                        .where(ProvisioningPending.operation_id == operation.id)
                        .order_by(ProvisioningPending.resource)
                    )
                ]
            return result

    def snapshot(self, tenant_id):
        with Session(self.engine) as session:
            tenant = session.get(Tenant, tenant_id)
            if tenant is None:
                raise AdminError("UNKNOWN_TENANT")
            operation = session.scalar(
                sa.select(ProvisioningOperation).where(ProvisioningOperation.tenant_id == tenant_id)
            )
            if operation is None:
                raise AdminError("UNKNOWN_OPERATION")
            db = session.get(DbLocation, tenant_id)
            storage = session.get(StorageLocation, tenant_id)
            instance = session.get(Instance, db.instance_id) if db else None
            names = Names(tenant_id, operation.id)
            if (
                db is None
                or storage is None
                or instance is None
                or db.db_name != names.database
                or db.ssl_mode != "verify-full"
                or storage.bucket != StorageNames(tenant_id).bucket
                or storage.endpoint != self.storage.endpoint
            ):
                raise AdminError("CATALOG_CONFLICT")
            refs = tuple(
                SecretRef(getattr(db, k + "_secret_ref"), getattr(db, k + "_secret_version"))
                for k in ("migrator", "app", "readonly")
            )
            return Snapshot(
                operation.id,
                tenant_id,
                instance.id,
                instance.host,
                instance.port,
                SecretRef(instance.admin_secret_ref, instance.admin_secret_version),
                refs,
                storage.endpoint,
                SecretRef(storage.credential_ref, storage.credential_version),
            ), operation.idempotency_key

    def create(self, instance_id, key):
        if self.storage_admin is None and self.backend_factory == self._backend:
            raise AdminError("CONFIG_UNAVAILABLE")
        snap = self.saga.run(key, instance_id, self.storage.endpoint, self.actor)
        return self.show(snap.tenant)

    def retry(self, tenant_id):
        snap, key = self.snapshot(tenant_id)
        self.saga.run(key, snap.instance, snap.storage_endpoint, self.actor)
        return self.show(tenant_id)

    def migrate(self, tenant_id):
        migrate_controlled(self.engine, tenant_id, self.actor, self.store, self.ca, self.repository)
        return {"tenant": str(tenant_id), "migration": "PASS", "version": VERSION}

    def check(self, tenant_id):
        locks = self.locks or (lambda ns, id: postgres_lock(self.engine, ns, id))
        with locks("f01-saga-tenant:", tenant_id):
            status = self.show(tenant_id)
            operation = status.get("operation", {})
            if (
                status["state"] != "READY"
                or status["migration_state"] != "READY"
                or status["observed_version"] != VERSION
                or operation.get("state") != "SUCCEEDED"
                or operation.get("compensation") != "NONE"
                or {s["step"] for s in status.get("steps", [])} != set(STEPS)
                or any(s["state"] != "SUCCEEDED" for s in status.get("steps", []))
            ):
                raise AdminError("NOT_READY")
            snap, _ = self.snapshot(tenant_id)
            names = Names(tenant_id, snap.operation)
            migrator = self.store.read(snap.sql_refs[0])
            # Read actual identity/version under the canonical migration lock; no Alembic/DDL.
            with migration_session(
                Target(snap.host, snap.port, self.ca), names, migrator
            ) as connection:
                versions = connection.execute(
                    sa.text("SELECT version_num FROM public.alembic_version_tenant")
                ).all()
                identity = connection.execute(
                    sa.text("SELECT tenant_id FROM public.ops_identity")
                ).all()
                vector = connection.scalar(
                    sa.text("SELECT extversion FROM pg_extension WHERE extname='vector'")
                )
                if versions != [(VERSION,)] or identity != [(tenant_id,)] or vector != "0.8.7":
                    raise AdminError("CHECK_FAILED")
            registry = ConnectionRegistry(CatalogResolver(self.engine), self.store, self.ca)
            try:
                for role in ("app", "readonly"):
                    with registry.connection(AdministrativeTenant(tenant_id), role) as connection:
                        row = connection.execute(
                            sa.text(
                                "SELECT current_database(),current_user,ssl FROM pg_stat_ssl "
                                "WHERE pid=pg_backend_pid()"
                            )
                        ).one()
                        flags = connection.execute(
                            sa.text(
                                "SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,"
                                "rolbypassrls "
                                "FROM pg_roles WHERE rolname=current_user"
                            )
                        ).one()
                        if (
                            tuple(row) != (names.database, names.role(role), True)
                            or tuple(flags) != (False,) * 5
                        ):
                            raise AdminError("CHECK_FAILED")
            finally:
                registry.close()
            credential = self.store.read(snap.storage_ref)
            if credential.username != StorageNames(tenant_id).user:
                raise AdminError("CHECK_FAILED")
            s3 = self.storage.s3(credential)
            key = "_f01/admin-check/" + uuid4().hex
            payload = b"F01 administrative synthetic probe"
            written = False
            try:
                s3.put_object(
                    StorageNames(tenant_id).bucket, key, io.BytesIO(payload), len(payload)
                )
                written = True
                response = s3.get_object(StorageNames(tenant_id).bucket, key)
                try:
                    if response.read(1024) != payload:
                        raise AdminError("CHECK_FAILED")
                finally:
                    response.close()
                    response.release_conn()
                if key not in {
                    o.object_name
                    for o in s3.list_objects(StorageNames(tenant_id).bucket, prefix=key)
                }:
                    raise AdminError("CHECK_FAILED")
                try:
                    response = self.storage.s3().get_object(StorageNames(tenant_id).bucket, key)
                except S3Error as error:
                    if error.code != "AccessDenied":
                        raise AdminError("CHECK_FAILED") from None
                else:
                    response.close()
                    response.release_conn()
                    raise AdminError("CHECK_FAILED")
            finally:
                if written:
                    s3.remove_object(StorageNames(tenant_id).bucket, key)
            return {"tenant": str(tenant_id), "check": "PASS", "version": VERSION}
