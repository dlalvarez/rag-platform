"""F02 additive identity metadata; existing F01 tenants remain unclassified."""

import sqlalchemy as sa
from alembic import op

revision = "f02_control_0005"
down_revision = "f01_control_0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("issuer", sa.String(2048), nullable=False),
        sa.Column("oidc_subject", sa.String(255), nullable=False),
        sa.Column("state", sa.String(16), server_default="ACTIVE", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.UniqueConstraint("issuer", "oidc_subject", name="user_oidc_identity"),
        sa.CheckConstraint("state IN ('ACTIVE','SUSPENDED')", name="user_state"),
        sa.CheckConstraint("length(issuer) BETWEEN 1 AND 2048", name="user_issuer_length"),
        sa.CheckConstraint("length(oidc_subject) BETWEEN 1 AND 255", name="user_subject_length"),
    )
    op.create_table(
        "tenant_profiles",
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), primary_key=True),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.CheckConstraint("kind IN ('PERSONAL','ORG')", name="tenant_profile_kind"),
    )
    op.create_table(
        "memberships",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), primary_key=True),
        sa.Column("role", sa.String(8), nullable=False),
        sa.Column("state", sa.String(16), server_default="ACTIVE", nullable=False),
        sa.CheckConstraint("role IN ('owner','admin','editor','reader')", name="membership_role"),
        sa.CheckConstraint("state IN ('ACTIVE','SUSPENDED','REVOKED')", name="membership_state"),
    )
    op.create_table(
        "platform_roles",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("role", sa.String(24), primary_key=True),
        sa.Column("state", sa.String(16), server_default="ACTIVE", nullable=False),
        sa.CheckConstraint(
            "role IN ('platform_operator','platform_support')", name="platform_role"
        ),
        sa.CheckConstraint("state IN ('ACTIVE','REVOKED')", name="platform_role_state"),
    )
    op.create_table(
        "identity_audit",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("principal_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("target_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("event_code", sa.String(32), nullable=False),
        sa.Column("outcome", sa.String(8), nullable=False),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "event_code IN ('AUTHENTICATED','AUTH_DENIED','MEMBERSHIP_CHANGED',"
            "'PRINCIPAL_STATE_CHANGED','PLATFORM_ROLE_CHANGED','TENANT_CLASSIFIED','BOOTSTRAP')",
            name="identity_audit_event",
        ),
        sa.CheckConstraint("outcome IN ('OK','DENIED','FAILED')", name="identity_audit_outcome"),
        sa.CheckConstraint(
            "reason IN ('NONE','TOKEN_INVALID','DEPENDENCY_UNAVAILABLE','IDENTITY_SUSPENDED',"
            "'MEMBERSHIP_REQUIRED','TENANT_UNAVAILABLE','ROLE_DENIED','LAST_OWNER',"
            "'INPUT_INVALID','STATE_CONFLICT')",
            name="identity_audit_reason",
        ),
    )


def downgrade():
    raise RuntimeError("Identity data is preserved; destructive downgrade requires approval")
