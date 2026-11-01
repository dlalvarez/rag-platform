"""F02 metadata only: global identities, memberships and closed audit records."""

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from rag_platform.control.models import Tenant, code_check


class IdentityBase(DeclarativeBase):
    pass


class User(IdentityBase):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    issuer: Mapped[str] = mapped_column(sa.String(2048))
    oidc_subject: Mapped[str] = mapped_column(sa.String(255))
    state: Mapped[str] = mapped_column(sa.String(16), server_default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.current_timestamp()
    )
    __table_args__ = (
        sa.UniqueConstraint("issuer", "oidc_subject", name="user_oidc_identity"),
        code_check("state", ("ACTIVE", "SUSPENDED"), "user_state"),
        sa.CheckConstraint("length(issuer) BETWEEN 1 AND 2048", name="user_issuer_length"),
        sa.CheckConstraint("length(oidc_subject) BETWEEN 1 AND 255", name="user_subject_length"),
    )


class TenantProfile(IdentityBase):
    __tablename__ = "tenant_profiles"
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey(Tenant.__table__.c.id), primary_key=True
    )
    kind: Mapped[str] = mapped_column(sa.String(8))
    __table_args__ = (code_check("kind", ("PERSONAL", "ORG"), "tenant_profile_kind"),)


class Membership(IdentityBase):
    __tablename__ = "memberships"
    user_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("users.id"), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey(Tenant.__table__.c.id), primary_key=True
    )
    role: Mapped[str] = mapped_column(sa.String(8))
    state: Mapped[str] = mapped_column(sa.String(16), server_default="ACTIVE")
    __table_args__ = (
        code_check("role", ("owner", "admin", "editor", "reader"), "membership_role"),
        code_check("state", ("ACTIVE", "SUSPENDED", "REVOKED"), "membership_state"),
    )


class PlatformRole(IdentityBase):
    __tablename__ = "platform_roles"
    user_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("users.id"), primary_key=True)
    role: Mapped[str] = mapped_column(sa.String(24), primary_key=True)
    state: Mapped[str] = mapped_column(sa.String(16), server_default="ACTIVE")
    __table_args__ = (
        code_check("role", ("platform_operator", "platform_support"), "platform_role"),
        code_check("state", ("ACTIVE", "REVOKED"), "platform_role_state"),
    )


EVENTS = (
    "AUTHENTICATED",
    "AUTH_DENIED",
    "MEMBERSHIP_CHANGED",
    "PRINCIPAL_STATE_CHANGED",
    "PLATFORM_ROLE_CHANGED",
    "TENANT_CLASSIFIED",
    "BOOTSTRAP",
)
REASONS = (
    "NONE",
    "TOKEN_INVALID",
    "DEPENDENCY_UNAVAILABLE",
    "IDENTITY_SUSPENDED",
    "MEMBERSHIP_REQUIRED",
    "TENANT_UNAVAILABLE",
    "ROLE_DENIED",
    "LAST_OWNER",
    "INPUT_INVALID",
    "STATE_CONFLICT",
)


class IdentityAudit(IdentityBase):
    __tablename__ = "identity_audit"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID]
    principal_id: Mapped[uuid.UUID | None] = mapped_column(sa.ForeignKey("users.id"))
    target_user_id: Mapped[uuid.UUID | None] = mapped_column(sa.ForeignKey("users.id"))
    tenant_id: Mapped[uuid.UUID | None]
    event_code: Mapped[str] = mapped_column(sa.String(32))
    outcome: Mapped[str] = mapped_column(sa.String(8))
    reason: Mapped[str] = mapped_column(sa.String(32))
    recorded_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.current_timestamp()
    )
    __table_args__ = (
        code_check("event_code", EVENTS, "identity_audit_event"),
        code_check("outcome", ("OK", "DENIED", "FAILED"), "identity_audit_outcome"),
        code_check("reason", REASONS, "identity_audit_reason"),
    )
