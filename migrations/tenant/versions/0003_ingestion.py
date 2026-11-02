"""F04 additive tenant evolution. Historical F03 schema remains frozen."""

import sqlalchemy as sa
from alembic import op

from rag_platform.ingestion.guards_f04_0003 import FUNCTIONS, READY_AUDIT_TRIGGER, TRIGGERS
from rag_platform.ingestion.schema_f04_0003 import (
    ACTIONS,
    DOCUMENT_CHECKS,
    ORIGIN_COLUMNS,
    ORIGIN_REFERENCE,
    VERSION_CHECKS,
    build_metadata,
    document_columns,
    version_columns,
)

revision = "f04_tenant_0003"
down_revision = "f03_tenant_0002"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "document_versions",
        "state",
        schema="knowledge",
        existing_type=sa.String(16),
        type_=sa.String(32),
        existing_nullable=False,
    )
    op.alter_column(
        "document_versions",
        "blob_key",
        schema="knowledge",
        existing_type=sa.String(100),
        nullable=True,
    )
    for column in version_columns():
        op.add_column("document_versions", column, schema="knowledge")
    for column in document_columns():
        op.add_column("documents", column, schema="knowledge")
    for table, old in (("document_versions", "version_state"), ("documents", "document_state")):
        op.drop_constraint(old, table, schema="knowledge", type_="check")
    for name, condition in VERSION_CHECKS.items():
        op.create_check_constraint(name, "document_versions", condition, schema="knowledge")
    for name, condition in DOCUMENT_CHECKS.items():
        op.create_check_constraint(name, "documents", condition, schema="knowledge")
    op.create_unique_constraint(
        "f04_version_identity",
        "document_versions",
        ["id", "document_id", "repository_id", "kind"],
        schema="knowledge",
    )
    op.create_unique_constraint(
        "f04_original_identity", "document_versions", list(ORIGIN_COLUMNS), schema="knowledge"
    )
    op.create_unique_constraint(
        "f04_processing_actor",
        "document_versions",
        ["id", "document_id", "repository_id", "kind", "processing_actor_id"],
        schema="knowledge",
    )
    op.create_foreign_key(
        "f04_version_original",
        "document_versions",
        "document_versions",
        list(ORIGIN_REFERENCE),
        list(ORIGIN_COLUMNS),
        source_schema="knowledge",
        referent_schema="knowledge",
    )
    op.create_foreign_key(
        "f04_current_original",
        "documents",
        "document_versions",
        ["current_version_id", "id", "repository_id", "current_version_kind"],
        ["id", "document_id", "repository_id", "kind"],
        source_schema="knowledge",
        referent_schema="knowledge",
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_index(
        "f04_processed_configuration",
        "document_versions",
        ["document_id", "original_version_id", "config_hash"],
        unique=True,
        schema="knowledge",
        postgresql_where=sa.text("kind='PROCESSED'"),
    )
    op.create_index(
        "f04_version_page", "document_versions", ["document_id", "id"], schema="knowledge"
    )
    op.drop_constraint("document_audit_action", "audit_events", schema="ops", type_="check")
    op.create_check_constraint(
        "document_audit_action", "audit_events", "action IN " + repr(ACTIONS), schema="ops"
    )
    op.create_index(
        "f04_ready_audit_once",
        "audit_events",
        ["target_id"],
        unique=True,
        schema="ops",
        postgresql_where=sa.text("action='INGESTION_READY'"),
    )
    metadata = build_metadata()
    for table in ("knowledge.extracted_blocks", "knowledge.chunks", "ops.ingestion_intents"):
        metadata.tables[table].create(op.get_bind(), checkfirst=False)
    for name, ddl in FUNCTIONS:
        op.execute(ddl)
        op.execute("REVOKE ALL ON FUNCTION ops." + name + "() FROM PUBLIC")
    for name, table, events, function in TRIGGERS:
        op.execute(
            "CREATE TRIGGER "
            + name
            + " BEFORE "
            + events
            + " ON "
            + table
            + " FOR EACH ROW EXECUTE FUNCTION ops."
            + function
            + "()"
        )
    op.execute(READY_AUDIT_TRIGGER)


def downgrade():
    raise RuntimeError("Originals and processed history are retained; no destructive downgrade")
