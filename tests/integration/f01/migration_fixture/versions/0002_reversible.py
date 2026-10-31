"""Reversible synthetic metadata column."""

import sqlalchemy as sa
from alembic import op

revision = "fixture_0002"
down_revision = "fixture_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "f01_synthetic_migration_canary",
        sa.Column("upgrade_value", sa.Integer(), nullable=False, server_default="42"),
        schema="public",
    )


def downgrade():
    op.drop_column("f01_synthetic_migration_canary", "upgrade_value", schema="public")
