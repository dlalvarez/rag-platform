"""Administrative control reflection of a checked tenant migration; no false READY."""

from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session

from rag_platform.control.models import (
    AuditControl,
    DbLocation,
    Instance,
    ProvisioningOperation,
    Tenant,
)
from rag_platform.provisioning.migrations import MigrationError, migrate_initial
from rag_platform.provisioning.postgres import Names, Target
from rag_platform.provisioning.saga import postgres_lock
from rag_platform.tenancy.contracts import SecretRef
from rag_platform.tenancy.profiles import migration_sources, version_for


def migrate_controlled(
    engine,
    tenant_id: UUID,
    actor: UUID,
    store,
    ca,
    repository,
    *,
    runner=migrate_initial,
    profile="identity",
):
    expected = version_for(profile)
    allowed = migration_sources(profile)
    if not isinstance(tenant_id, UUID) or not isinstance(actor, UUID):
        raise MigrationError("IDENTITY_CONFLICT")
    with postgres_lock(engine, "f01-saga-tenant:", tenant_id):
        with Session(engine) as session, session.begin():
            tenant = session.get(Tenant, tenant_id)
            location = session.get(DbLocation, tenant_id)
            operation = session.scalar(
                sa.select(ProvisioningOperation).where(ProvisioningOperation.tenant_id == tenant_id)
            )
            if (
                tenant is None
                or location is None
                or operation is None
                or operation.state != "SUCCEEDED"
                or tenant.state == "SUSPENDED"
                or tenant.desired_version not in allowed
            ):
                raise MigrationError("IDENTITY_CONFLICT")
            instance = session.get(Instance, location.instance_id)
            if instance is None or location.ssl_mode != "verify-full":
                raise MigrationError("IDENTITY_CONFLICT")
            names = Names(tenant_id, operation.id)
            if location.db_name != names.database:
                raise MigrationError("IDENTITY_CONFLICT")
            target = Target(instance.host, instance.port, ca)
            ref = SecretRef(location.migrator_secret_ref, location.migrator_secret_version)
            # Preserve lifecycle until the lock/identity is checked, then deny new resolution.
            tenant.desired_version = expected
            tenant.state, tenant.migration_state = "PROVISIONING", "MIGRATING"
            tenant.observed_version = None
            session.add(
                AuditControl(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    operation_id=operation.id,
                    actor_id=actor,
                    event_code="MIGRATION_REQUESTED",
                    outcome="OK",
                )
            )
        try:
            result = runner(target, names, store.read(ref), repository)
            if result != expected:
                raise MigrationError("VERSION_MISMATCH")
        except Exception:
            with Session(engine) as session, session.begin():
                tenant = session.get(Tenant, tenant_id)
                tenant.state, tenant.migration_state = "FAILED", "MIGRATION_FAILED"
                tenant.observed_version = None
            raise MigrationError() from None
        # A lost final COMMIT response is reconciled on retry, never destructive compensation.
        with Session(engine) as session, session.begin():
            tenant = session.get(Tenant, tenant_id)
            tenant.observed_version = result
            tenant.migration_state, tenant.state = "READY", "READY"
        return result
