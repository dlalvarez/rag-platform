"""Intentional transactional failure; never canonical runtime migration."""

from alembic import op

revision = "fixture_0003_bad"
down_revision = "fixture_0002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE TABLE public.f01_synthetic_failed_migration(id integer)")
    op.execute("SELECT * FROM public.f01_intentionally_missing_migration_relation")


def downgrade():
    raise RuntimeError("Failed fixture must never be stamped")
