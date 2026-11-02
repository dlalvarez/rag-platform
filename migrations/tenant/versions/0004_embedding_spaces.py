"""F05 additive space foundation. F04 versions/chunks/guards remain unchanged."""

from alembic import op

from rag_platform.embeddings.space_ddl import build_metadata

revision = "f05_tenant_0004"
down_revision = "f04_tenant_0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint(
        "f05_chunk_identity",
        "chunks",
        ["id", "version_id", "document_id", "repository_id"],
        schema="knowledge",
    )
    build_metadata().tables["knowledge.embedding_spaces"].create(op.get_bind(), checkfirst=False)
    op.execute("REVOKE ALL ON knowledge.embedding_spaces FROM PUBLIC")
    op.execute("""
CREATE FUNCTION ops.f05_space_retention() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $f05$
BEGIN
    RAISE EXCEPTION 'space profile retained' USING ERRCODE='23514';
END
$f05$
""")
    op.execute("REVOKE ALL ON FUNCTION ops.f05_space_retention() FROM PUBLIC")
    op.execute("""
CREATE TRIGGER f05_space_retention BEFORE UPDATE OR DELETE
ON knowledge.embedding_spaces FOR EACH ROW
EXECUTE FUNCTION ops.f05_space_retention()
""")


def downgrade():
    raise RuntimeError("Embedding spaces and history retained; no destructive downgrade")
