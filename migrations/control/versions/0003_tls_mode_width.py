"""Allow the mandatory TLS mode verify-full (11 characters), preserving rows."""

import sqlalchemy as sa
from alembic import op

revision = "f01_control_0003"
down_revision = "f01_control_0002"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("db_locations") as batch:
        batch.alter_column(
            "ssl_mode",
            existing_type=sa.String(10),
            type_=sa.String(11),
            existing_nullable=False,
        )


def downgrade():
    raise RuntimeError("TLS mode narrowing requires a separately approved migration")
