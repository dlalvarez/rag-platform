"""Additive identifier-only EMBED envelopes; INGEST history and semantics retained."""

import sqlalchemy as sa
from alembic import op

from rag_platform.embeddings.queue_schema_f05_0007 import jobs

revision = "f05_control_0007"
down_revision = "f04_control_0006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("job_envelopes", sa.Column("space_id", sa.Uuid(), nullable=True))
    op.add_column("job_envelopes", sa.Column("profile_fingerprint", sa.String(64), nullable=True))
    op.drop_constraint("job_version_kind", "job_envelopes", type_="unique")
    for name in ("job_kind", "job_error"):
        op.drop_constraint(name, "job_envelopes", type_="check")
    for name in ("job_kind", "job_error", "job_embedding_profile", "job_embedding_hash"):
        constraint = next(item for item in jobs.constraints if item.name == name)
        op.create_check_constraint(name, "job_envelopes", str(constraint.sqltext))
    for index in jobs.indexes:
        if index.name != "job_claim_ready":
            index.create(op.get_bind(), checkfirst=False)
    op.execute("REVOKE ALL ON public.job_envelopes FROM PUBLIC")


def downgrade():
    raise RuntimeError("Job/profile history retained; no destructive downgrade")
