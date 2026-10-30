"""Explicit control-plane metadata; no arbitrary payload or credential columns."""

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def code_check(column: str, codes: tuple[str, ...], name: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(f"{column} IN {codes!r}", name=name)


ERRORS = (
    "NONE",
    "SECRET_UNAVAILABLE",
    "SECRET_DENIED",
    "SECRET_CONFLICT",
    "SQL_FAILED",
    "STORAGE_FAILED",
    "MIGRATION_FAILED",
    "OWNERSHIP_CONFLICT",
)


class Instance(Base):
    __tablename__ = "instances"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    host: Mapped[str] = mapped_column(sa.String(253))
    port: Mapped[int] = mapped_column(default=5432)
    admin_secret_ref: Mapped[uuid.UUID]
    admin_secret_version: Mapped[int]
    __table_args__ = (
        sa.UniqueConstraint("host", "port"),
        sa.CheckConstraint("port BETWEEN 1 AND 65535", name="instance_port"),
        sa.CheckConstraint("admin_secret_version > 0", name="instance_secret_version"),
    )


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    state: Mapped[str] = mapped_column(sa.String(16), default="PROVISIONING")
    migration_state: Mapped[str] = mapped_column(sa.String(24), default="NEEDS_MIGRATION")
    desired_version: Mapped[str] = mapped_column(sa.String(32))
    observed_version: Mapped[str | None] = mapped_column(sa.String(32))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.current_timestamp()
    )
    __table_args__ = (
        code_check("state", ("PROVISIONING", "READY", "FAILED", "SUSPENDED"), "tenant_state"),
        code_check(
            "migration_state",
            ("NEEDS_MIGRATION", "MIGRATING", "READY", "MIGRATION_FAILED"),
            "tenant_migration_state",
        ),
    )


class DbLocation(Base):
    __tablename__ = "db_locations"
    tenant_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("tenants.id"), primary_key=True)
    instance_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("instances.id"))
    db_name: Mapped[str] = mapped_column(sa.String(63))
    app_secret_ref: Mapped[uuid.UUID] = mapped_column(unique=True)
    app_secret_version: Mapped[int]
    migrator_secret_ref: Mapped[uuid.UUID] = mapped_column(unique=True)
    migrator_secret_version: Mapped[int]
    ssl_mode: Mapped[str] = mapped_column(sa.String(10), default="verify-full")
    __table_args__ = (
        sa.UniqueConstraint("instance_id", "db_name"),
        sa.CheckConstraint("ssl_mode = 'verify-full'", name="db_tls"),
        sa.CheckConstraint(
            "app_secret_version > 0 AND migrator_secret_version > 0", name="db_secret_versions"
        ),
        sa.CheckConstraint("app_secret_ref <> migrator_secret_ref", name="separate_sql_refs"),
    )


class StorageLocation(Base):
    __tablename__ = "storage_locations"
    tenant_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("tenants.id"), primary_key=True)
    endpoint: Mapped[str] = mapped_column(sa.String(253))
    bucket: Mapped[str] = mapped_column(sa.String(63))
    credential_ref: Mapped[uuid.UUID] = mapped_column(unique=True)
    credential_version: Mapped[int]
    __table_args__ = (
        sa.UniqueConstraint("endpoint", "bucket"),
        sa.CheckConstraint("credential_version > 0", name="storage_secret_version"),
    )


class ProvisioningOperation(Base):
    __tablename__ = "provisioning_operations"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("tenants.id"), unique=True)
    idempotency_key: Mapped[uuid.UUID] = mapped_column(unique=True)
    state: Mapped[str] = mapped_column(sa.String(16), default="PENDING")
    attempts: Mapped[int] = mapped_column(default=0)
    error_code: Mapped[str] = mapped_column(sa.String(32), default="NONE")
    __table_args__ = (
        code_check("state", ("PENDING", "RUNNING", "FAILED", "SUCCEEDED"), "operation_state"),
        code_check("error_code", ERRORS, "operation_error"),
        sa.CheckConstraint("attempts >= 0", name="operation_attempts"),
    )


class ProvisioningStep(Base):
    __tablename__ = "provisioning_steps"
    operation_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("provisioning_operations.id"), primary_key=True
    )
    step: Mapped[str] = mapped_column(sa.String(16), primary_key=True)
    state: Mapped[str] = mapped_column(sa.String(16), default="PENDING")
    error_code: Mapped[str] = mapped_column(sa.String(32), default="NONE")
    __table_args__ = (
        code_check(
            "step", ("RESERVE", "SECRETS", "DATABASE", "MIGRATE", "STORAGE", "PROBES"), "step_name"
        ),
        code_check("state", ("PENDING", "RUNNING", "FAILED", "SUCCEEDED"), "step_state"),
        code_check("error_code", ERRORS, "step_error"),
    )


class AuditControl(Base):
    __tablename__ = "audit_control"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("tenants.id"))
    operation_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("provisioning_operations.id"))
    actor_id: Mapped[uuid.UUID]
    event_code: Mapped[str] = mapped_column(sa.String(24))
    outcome: Mapped[str] = mapped_column(sa.String(8))
    recorded_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.current_timestamp()
    )
    __table_args__ = (
        code_check(
            "event_code",
            ("PROVISION_REQUESTED", "STEP_COMPLETED", "STEP_FAILED", "MIGRATION_REQUESTED"),
            "audit_event",
        ),
        code_check("outcome", ("OK", "DENIED", "FAILED"), "audit_outcome"),
    )
