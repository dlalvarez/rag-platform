"""Tenant processing/usage and atomic publication; original anchors retained."""

from alembic import op

from rag_platform.embeddings.publication_guards_f05_0006 import FUNCTIONS
from rag_platform.embeddings.publication_schema_f05_0006 import build_metadata

revision = "f05_tenant_0006"
down_revision = "f05_tenant_0005"
branch_labels = None
depends_on = None


def upgrade():
    metadata = build_metadata()
    for table, names in (
        ("document_versions", ("version_state", "f04_version_complete", "f04_version_failure")),
        ("documents", ("f04_document_kind",)),
    ):
        definition = metadata.tables["knowledge." + table]
        for name in names:
            constraint = next(c for c in definition.constraints if c.name == name)
            op.drop_constraint(name, table, type_="check", schema="knowledge")
            op.create_check_constraint(name, table, str(constraint.sqltext), schema="knowledge")
    op.create_unique_constraint(
        "f05_space_profile_identity",
        "embedding_spaces",
        ["id", "profile_fingerprint"],
        schema="knowledge",
    )
    for name in (
        "ops.embedding_intents",
        "ops.embedding_batches",
        "knowledge.embedding_publications",
    ):
        metadata.tables[name].create(op.get_bind(), checkfirst=False)
        op.execute("REVOKE ALL ON " + name + " FROM PUBLIC")
    audit = metadata.tables["ops.audit_events"]
    old = str(next(c for c in audit.constraints if c.name == "document_audit_action").sqltext)
    op.drop_constraint("document_audit_action", "audit_events", type_="check", schema="ops")
    op.create_check_constraint(
        "document_audit_action",
        "audit_events",
        old,
        schema="ops",
    )
    for name, ddl in FUNCTIONS:
        op.execute(ddl)
        op.execute("REVOKE ALL ON FUNCTION ops." + name + "() FROM PUBLIC")
    op.execute("DROP TRIGGER f04_version_guard ON knowledge.document_versions")
    for trigger, table, events, function in (
        (
            "f05_version_guard",
            "knowledge.document_versions",
            "INSERT OR UPDATE OR DELETE",
            "f05_version_guard",
        ),
        (
            "f05_embedding_intent",
            "ops.embedding_intents",
            "INSERT OR UPDATE OR DELETE",
            "f05_embedding_intent_guard",
        ),
        (
            "f05_embedding_batch",
            "ops.embedding_batches",
            "INSERT OR UPDATE OR DELETE",
            "f05_embedding_batch_guard",
        ),
    ):
        op.execute(
            "CREATE TRIGGER "
            + trigger
            + " BEFORE "
            + events
            + " ON "
            + table
            + " FOR EACH ROW EXECUTE FUNCTION ops."
            + function
            + "()"
        )
    for trigger, table, events, function in (
        (
            "f05_publication_complete",
            "knowledge.embedding_publications",
            "INSERT OR UPDATE OR DELETE",
            "f05_embedding_publication_guard",
        ),
        (
            "f05_document_pointer",
            "knowledge.documents",
            "INSERT OR UPDATE",
            "f05_published_pointer_guard",
        ),
        (
            "f05_version_publication",
            "knowledge.document_versions",
            "UPDATE",
            "f05_published_pointer_guard",
        ),
    ):
        op.execute(
            "CREATE CONSTRAINT TRIGGER "
            + trigger
            + " AFTER "
            + events
            + " ON "
            + table
            + " DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION ops."
            + function
            + "()"
        )


def downgrade():
    raise RuntimeError("Published vectors, usage and history retained; no destructive downgrade")
