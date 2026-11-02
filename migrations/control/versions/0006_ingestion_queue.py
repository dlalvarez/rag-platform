"""F04 additive durable identifier envelopes. No content or private payload."""

from alembic import op

from rag_platform.ingestion.queue_schema_f04_0006 import jobs

revision = "f04_control_0006"
down_revision = "f02_control_0005"
branch_labels = None
depends_on = None


def upgrade():
    jobs.create(op.get_bind(), checkfirst=False)
    op.execute("REVOKE ALL ON public.job_envelopes FROM PUBLIC")


def downgrade():
    raise RuntimeError("Job history is retained; destructive downgrade requires approval")
