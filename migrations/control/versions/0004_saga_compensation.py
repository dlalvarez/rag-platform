"""T004 compensation state and explicit pending-resource metadata."""

import sqlalchemy as sa
from alembic import op

revision = "f01_control_0004"
down_revision = "f01_control_0003"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("provisioning_operations") as batch:
        batch.add_column(
            sa.Column("compensation_state", sa.String(16), server_default="NONE", nullable=False)
        )
        batch.create_check_constraint(
            "compensation_state", "compensation_state IN ('NONE','REVOKED','REVIEW')"
        )
    op.create_table(
        "provisioning_pending",
        sa.Column(
            "operation_id", sa.Uuid(), sa.ForeignKey("provisioning_operations.id"), primary_key=True
        ),
        sa.Column("resource", sa.String(24), primary_key=True),
        sa.Column("resource_name", sa.String(63), nullable=False),
        sa.Column("disposition", sa.String(24), nullable=False),
        sa.CheckConstraint(
            "resource IN ('SQL_DATABASE','SQL_ROLES','STORAGE_BUCKET','STORAGE_USER')",
            name="pending_resource",
        ),
        sa.CheckConstraint(
            "disposition IN ('ABSENT','PRESERVED','ACCESS_REVOKED','REVIEW','RESOLVED')",
            name="pending_disposition",
        ),
    )


def downgrade():
    raise RuntimeError("Destructive saga downgrade requires separate approval")
