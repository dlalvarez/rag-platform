"""Synthetic canary only."""

import sqlalchemy as sa
from alembic import op

revision = "fixture_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "f01_synthetic_migration_canary",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("value", sa.Integer(), nullable=False),
        schema="public",
    )
    op.execute("INSERT INTO public.f01_synthetic_migration_canary VALUES (1,41)")


def downgrade():
    raise RuntimeError("Fixture base is retained; no automatic deletion")
