"""Expand original anchor; F04 current pointer remains ORIGINAL until publication."""

import sqlalchemy as sa
from alembic import op

from rag_platform.embeddings.original_anchor_f05_0005 import ANCHOR_GUARD

revision = "f05_tenant_0005"
down_revision = "f05_tenant_0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("documents", sa.Column("original_version_id", sa.Uuid()), schema="knowledge")
    op.add_column(
        "documents",
        sa.Column(
            "original_version_kind", sa.String(16), nullable=False, server_default="ORIGINAL"
        ),
        schema="knowledge",
    )
    op.execute("UPDATE knowledge.documents SET original_version_id=current_version_id")
    op.alter_column("documents", "original_version_id", nullable=False, schema="knowledge")
    op.create_check_constraint(
        "f05_original_anchor_kind",
        "documents",
        "original_version_kind='ORIGINAL'",
        schema="knowledge",
    )
    op.create_foreign_key(
        "f05_original_anchor",
        "documents",
        "document_versions",
        ["original_version_id", "id", "repository_id", "original_version_kind"],
        ["id", "document_id", "repository_id", "kind"],
        source_schema="knowledge",
        referent_schema="knowledge",
        deferrable=True,
        initially="DEFERRED",
    )
    op.execute(ANCHOR_GUARD)
    op.execute("REVOKE ALL ON FUNCTION ops.f05_original_anchor_guard() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER f05_original_anchor BEFORE INSERT OR UPDATE ON knowledge.documents "
        "FOR EACH ROW EXECUTE FUNCTION ops.f05_original_anchor_guard()"
    )


def downgrade():
    raise RuntimeError("Original anchors and history retained; no destructive downgrade")
