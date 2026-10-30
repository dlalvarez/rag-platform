"""Minimal operational identity only. No business schemas or content."""

import sqlalchemy as sa
from alembic import op

revision = "f01_tenant_0001"
down_revision = None
branch_labels = ("tenant",)
depends_on = None


def upgrade():
    op.create_table(
        "ops_identity",
        sa.Column("singleton", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False, unique=True),
        sa.CheckConstraint("singleton = 1", name="single_identity"),
        schema="public",
    )


def downgrade():
    raise RuntimeError("Destructive tenant downgrade requires separate approval")
