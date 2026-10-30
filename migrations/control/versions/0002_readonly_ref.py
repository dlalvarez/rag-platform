"""Versioned readonly credential reference; preserve existing locations."""

import sqlalchemy as sa
from alembic import op

revision = "f01_control_0002"
down_revision = "f01_control_0001"
branch_labels = None
depends_on = None


def upgrade():
    # Nullable pair preserves T001 rows; T002 requires both for new provisioning.
    with op.batch_alter_table("db_locations") as batch:
        batch.add_column(sa.Column("readonly_secret_ref", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("readonly_secret_version", sa.Integer(), nullable=True))
        batch.create_unique_constraint("unique_readonly_secret_ref", ["readonly_secret_ref"])
        batch.create_check_constraint(
            "readonly_secret_pair",
            "(readonly_secret_ref IS NULL AND readonly_secret_version IS NULL) OR "
            "(readonly_secret_ref IS NOT NULL AND readonly_secret_version IS NOT NULL "
            "AND readonly_secret_version > 0 AND readonly_secret_ref <> app_secret_ref "
            "AND readonly_secret_ref <> migrator_secret_ref)",
        )


def downgrade():
    raise RuntimeError("Destructive catalog downgrade requires a separately approved migration")
