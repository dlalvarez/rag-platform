"""Immutable F04 tenant schema evolution; original F03 values remain unchanged."""

from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from rag_platform.documents.schema_f03_0002 import build_metadata as f03_metadata

VERSION = "f04_tenant_0003"
STATES = (
    "RECEIVED",
    "VALIDATING",
    "EXTRACTING",
    "CHUNKING",
    "READY_FOR_EMBEDDING",
    "FAILED_RETRYABLE",
    "FAILED_TERMINAL",
    "NEEDS_OCR",
    "TOMBSTONED",
)
ERRORS = (
    "NONE",
    "DEPENDENCY_UNAVAILABLE",
    "PARSER_INVALID",
    "PARSER_LIMIT",
    "PARSER_ENCRYPTED",
    "PARSER_UNSUPPORTED",
    "NO_TEXT",
    "SANDBOX_UNAVAILABLE",
    "NEEDS_OCR",
    "AUTHORIZATION_CHANGED",
    "TOMBSTONED",
    "STOP_REQUESTED",
    "LEASE_EXHAUSTED",
    "PROCESSING_FAILED",
)
ACTIONS = (
    "REPOSITORY_CREATED",
    "REPOSITORY_UPDATED",
    "REPOSITORY_DELETED",
    "ACL_CHANGED",
    "DOCUMENT_RECEIVED",
    "DOCUMENT_DOWNLOADED",
    "ACCESS_DENIED",
    "INGESTION_REQUESTED",
    "INGESTION_STARTED",
    "INGESTION_READY",
    "INGESTION_FAILED",
    "DOCUMENT_TOMBSTONED",
)
BLOCK_KINDS = ("page", "blank_page", "paragraph", "heading", "table", "text", "markdown", "code")
VERSION_FIELDS = (
    "kind",
    "original_version_id",
    "original_kind",
    "processing_actor_id",
    "parser_id",
    "normalizer_id",
    "chunker_id",
    "config_hash",
    "chunk_size",
    "chunk_overlap",
    "normalized_hash",
    "character_count",
    "page_count",
    "block_count",
    "chunk_count",
    "completed_at",
    "error_code",
)
DOCUMENT_FIELDS = ("current_version_kind", "tombstoned_at", "tombstoned_by")


def version_columns():
    return [
        sa.Column("kind", sa.String(16), nullable=False, server_default="ORIGINAL"),
        sa.Column("original_version_id", sa.Uuid(), nullable=True),
        sa.Column("original_kind", sa.String(8), nullable=False, server_default="ORIGINAL"),
        sa.Column("processing_actor_id", sa.Uuid(), nullable=True),
        sa.Column("parser_id", sa.String(96), nullable=True),
        sa.Column("normalizer_id", sa.String(32), nullable=True),
        sa.Column("chunker_id", sa.String(64), nullable=True),
        sa.Column("config_hash", sa.String(64), nullable=True),
        sa.Column("chunk_size", sa.Integer(), nullable=True),
        sa.Column("chunk_overlap", sa.Integer(), nullable=True),
        sa.Column("normalized_hash", sa.String(64), nullable=True),
        sa.Column("character_count", sa.Integer(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("block_count", sa.Integer(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(32), nullable=False, server_default="NONE"),
    ]


def document_columns():
    return [
        sa.Column("current_version_kind", sa.String(16), nullable=False, server_default="ORIGINAL"),
        sa.Column("tombstoned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tombstoned_by", sa.Uuid(), nullable=True),
    ]


VERSION_CHECKS = {
    "version_state": "state IN " + repr(STATES),
    "f04_version_kind": "kind IN ('ORIGINAL','PROCESSED') AND original_kind='ORIGINAL'",
    "f04_version_error": "error_code IN " + repr(ERRORS),
    "f04_version_origin": (
        "(kind='ORIGINAL' AND original_version_id IS NULL AND blob_key IS NOT NULL "
        "AND processing_actor_id IS NULL AND state='RECEIVED') OR "
        "(kind='PROCESSED' AND original_version_id IS NOT NULL "
        "AND original_version_id<>id AND blob_key IS NULL AND processing_actor_id IS NOT NULL "
        "AND byte_size<=10485760)"
    ),
    "f04_version_configuration": (
        "(kind='ORIGINAL' AND parser_id IS NULL AND normalizer_id IS NULL AND chunker_id IS NULL "
        "AND config_hash IS NULL AND chunk_size IS NULL AND chunk_overlap IS NULL) OR "
        "(kind='PROCESSED' AND parser_id IS NOT NULL AND normalizer_id IS NOT NULL "
        "AND chunker_id IS NOT NULL AND config_hash IS NOT NULL "
        "AND parser_id ~ '^[A-Za-z0-9_.:+-]{1,96}$' "
        "AND normalizer_id ~ '^[A-Za-z0-9_.:+-]{1,32}$' "
        "AND chunker_id ~ '^[A-Za-z0-9_.:+-]{1,64}$' "
        "AND config_hash ~ '^[0-9a-f]{64}$' AND chunk_size IS NOT NULL "
        "AND chunk_overlap IS NOT NULL AND chunk_size BETWEEN 128 AND 8192 "
        "AND chunk_overlap BETWEEN 0 AND chunk_size/2)"
    ),
    "f04_version_complete": (
        "(state='READY_FOR_EMBEDDING' AND kind='PROCESSED' AND normalized_hash IS NOT NULL "
        "AND normalized_hash ~ '^[0-9a-f]{64}$' AND character_count IS NOT NULL "
        "AND character_count BETWEEN 1 AND 2000000 AND block_count IS NOT NULL "
        "AND block_count BETWEEN 1 AND 10000 AND chunk_count IS NOT NULL "
        "AND chunk_count BETWEEN 1 AND 10000 AND completed_at IS NOT NULL "
        "AND error_code='NONE' AND ((mime='application/pdf' AND page_count IS NOT NULL "
        "AND page_count BETWEEN 1 AND 200) OR (mime<>'application/pdf' AND page_count IS NULL))) "
        "OR (state<>'READY_FOR_EMBEDDING' AND normalized_hash IS NULL AND character_count IS NULL "
        "AND page_count IS NULL AND block_count IS NULL AND chunk_count IS NULL)"
    ),
    "f04_version_failure": (
        "(kind='ORIGINAL' AND completed_at IS NULL AND error_code='NONE') OR "
        "(kind='PROCESSED' AND ("
        "(state IN ('FAILED_TERMINAL','NEEDS_OCR','TOMBSTONED') "
        "AND completed_at IS NOT NULL AND error_code<>'NONE') OR "
        "(state='FAILED_RETRYABLE' AND completed_at IS NULL AND error_code<>'NONE') OR "
        "(state IN ('RECEIVED','VALIDATING','EXTRACTING','CHUNKING') "
        "AND completed_at IS NULL AND error_code='NONE') OR state='READY_FOR_EMBEDDING'))"
    ),
}
DOCUMENT_CHECKS = {
    "document_state": "state IN ('RECEIVED','TOMBSTONED')",
    "f04_document_kind": "current_version_kind='ORIGINAL'",
    "f04_document_tombstone": (
        "(state='RECEIVED' AND tombstoned_at IS NULL AND tombstoned_by IS NULL) OR "
        "(state='TOMBSTONED' AND tombstoned_at IS NOT NULL AND tombstoned_by IS NOT NULL)"
    ),
}
ORIGIN_COLUMNS = (
    "id",
    "document_id",
    "repository_id",
    "kind",
    "filename",
    "mime",
    "byte_size",
    "content_hash",
)
ORIGIN_REFERENCE = (
    "original_version_id",
    "document_id",
    "repository_id",
    "original_kind",
    "filename",
    "mime",
    "byte_size",
    "content_hash",
)


def _replace_check(table, name, sql):
    old = next((c for c in table.constraints if c.name == name), None)
    if old is not None:
        table.constraints.remove(old)
    table.append_constraint(sa.CheckConstraint(sql, name=name))


def build_metadata():
    metadata = f03_metadata()
    versions = metadata.tables["knowledge.document_versions"]
    documents = metadata.tables["knowledge.documents"]
    versions.c.state.type = sa.String(32)
    versions.c.blob_key.nullable = True
    for column in version_columns():
        versions.append_column(column)
    for column in document_columns():
        documents.append_column(column)
    for name, sql in VERSION_CHECKS.items():
        _replace_check(versions, name, sql)
    for name, sql in DOCUMENT_CHECKS.items():
        _replace_check(documents, name, sql)
    versions.append_constraint(
        sa.UniqueConstraint(
            "id", "document_id", "repository_id", "kind", name="f04_version_identity"
        )
    )
    versions.append_constraint(sa.UniqueConstraint(*ORIGIN_COLUMNS, name="f04_original_identity"))
    versions.append_constraint(
        sa.UniqueConstraint(
            "id",
            "document_id",
            "repository_id",
            "kind",
            "processing_actor_id",
            name="f04_processing_actor",
        )
    )
    versions.append_constraint(
        sa.ForeignKeyConstraint(
            ORIGIN_REFERENCE,
            ["knowledge.document_versions." + c for c in ORIGIN_COLUMNS],
            name="f04_version_original",
        )
    )
    documents.append_constraint(
        sa.ForeignKeyConstraint(
            ["current_version_id", "id", "repository_id", "current_version_kind"],
            [
                "knowledge.document_versions." + c
                for c in ("id", "document_id", "repository_id", "kind")
            ],
            name="f04_current_original",
            deferrable=True,
            initially="DEFERRED",
            use_alter=True,
        )
    )
    sa.Index(
        "f04_processed_configuration",
        versions.c.document_id,
        versions.c.original_version_id,
        versions.c.config_hash,
        unique=True,
        postgresql_where=versions.c.kind == "PROCESSED",
    )
    sa.Index("f04_version_page", versions.c.document_id, versions.c.id)
    _replace_check(
        metadata.tables["ops.audit_events"], "document_audit_action", "action IN " + repr(ACTIONS)
    )
    sa.Index(
        "f04_ready_audit_once",
        metadata.tables["ops.audit_events"].c.target_id,
        unique=True,
        postgresql_where=metadata.tables["ops.audit_events"].c.action == "INGESTION_READY",
    )

    def identifier():
        return sa.Column("id", sa.Uuid(), primary_key=True, default=uuid4)

    def stamp(name="created_at"):
        return sa.Column(
            name,
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        )

    def version_identity():
        return [
            sa.Column("version_id", sa.Uuid(), nullable=False),
            sa.Column("document_id", sa.Uuid(), nullable=False),
            sa.Column("repository_id", sa.Uuid(), nullable=False),
            sa.Column("version_kind", sa.String(16), nullable=False, server_default="PROCESSED"),
        ]

    blocks = sa.Table(
        "extracted_blocks",
        metadata,
        *version_identity(),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("section", JSONB, nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.PrimaryKeyConstraint("version_id", "ordinal"),
        sa.UniqueConstraint(
            "version_id",
            "ordinal",
            "document_id",
            "repository_id",
            "start_offset",
            "end_offset",
            name="f04_block_identity",
        ),
        sa.ForeignKeyConstraint(
            ["version_id", "document_id", "repository_id", "version_kind"],
            [
                "knowledge.document_versions." + c
                for c in ("id", "document_id", "repository_id", "kind")
            ],
            name="f04_block_version",
        ),
        sa.CheckConstraint("version_kind='PROCESSED'", name="f04_block_processed"),
        sa.CheckConstraint("ordinal BETWEEN 0 AND 9999", name="f04_block_ordinal"),
        sa.CheckConstraint(
            "start_offset>=0 AND end_offset BETWEEN start_offset AND 2000000 "
            "AND end_offset-start_offset=char_length(text)",
            name="f04_block_offsets",
        ),
        sa.CheckConstraint("text=normalize(text,NFC)", name="f04_block_nfc"),
        sa.CheckConstraint("kind IN " + repr(BLOCK_KINDS), name="f04_block_kind"),
        sa.CheckConstraint(
            "(kind='blank_page' AND text='') OR (kind<>'blank_page' AND char_length(text)>0)",
            name="f04_block_content",
        ),
        sa.CheckConstraint(
            "(kind IN ('page','blank_page') AND page BETWEEN 1 AND 200 AND page IS NOT NULL) "
            "OR (kind NOT IN ('page','blank_page') AND page IS NULL)",
            name="f04_block_page",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(section)='array' AND jsonb_array_length(section)<=9 "
            "AND char_length(section::text)<=8192",
            name="f04_block_section",
        ),
        schema="knowledge",
    )
    sa.Table(
        "chunks",
        metadata,
        identifier(),
        *version_identity(),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("block_ordinal", sa.Integer(), nullable=False),
        sa.Column("block_start", sa.Integer(), nullable=False),
        sa.Column("block_end", sa.Integer(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("section", JSONB, nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.UniqueConstraint("version_id", "ordinal", name="f04_chunk_ordinal"),
        sa.ForeignKeyConstraint(
            ["version_id", "document_id", "repository_id", "version_kind"],
            [
                "knowledge.document_versions." + c
                for c in ("id", "document_id", "repository_id", "kind")
            ],
            name="f04_chunk_version",
        ),
        sa.ForeignKeyConstraint(
            [
                "version_id",
                "block_ordinal",
                "document_id",
                "repository_id",
                "block_start",
                "block_end",
            ],
            [
                blocks.fullname + "." + c
                for c in (
                    "version_id",
                    "ordinal",
                    "document_id",
                    "repository_id",
                    "start_offset",
                    "end_offset",
                )
            ],
            name="f04_chunk_block",
        ),
        sa.CheckConstraint("version_kind='PROCESSED'", name="f04_chunk_processed"),
        sa.CheckConstraint("ordinal BETWEEN 0 AND 9999", name="f04_chunk_order"),
        sa.CheckConstraint(
            "start_offset>=block_start AND end_offset<=block_end "
            "AND end_offset>start_offset AND end_offset-start_offset=char_length(text) "
            "AND char_length(text)<=8192",
            name="f04_chunk_offsets",
        ),
        sa.CheckConstraint(
            "content_hash=encode(sha256(convert_to(text,'UTF8')),'hex')", name="f04_chunk_hash"
        ),
        schema="knowledge",
    )
    sa.Table(
        "ingestion_intents",
        metadata,
        identifier(),
        *version_identity(),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("dispatch_state", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("job_id", sa.Uuid(), nullable=True, unique=True),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attempt_token", sa.Uuid(), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        stamp(),
        stamp("updated_at"),
        sa.UniqueConstraint("version_id", name="f04_intent_version"),
        sa.ForeignKeyConstraint(
            ["version_id", "document_id", "repository_id", "version_kind", "actor_id"],
            [
                "knowledge.document_versions." + c
                for c in ("id", "document_id", "repository_id", "kind", "processing_actor_id")
            ],
            name="f04_intent_identity",
        ),
        sa.CheckConstraint("version_kind='PROCESSED'", name="f04_intent_processed"),
        sa.CheckConstraint(
            "(dispatch_state='PENDING' AND job_id IS NULL AND dispatched_at IS NULL) OR "
            "(dispatch_state='DISPATCHED' AND job_id IS NOT NULL AND dispatched_at IS NOT NULL)",
            name="f04_intent_dispatch",
        ),
        sa.CheckConstraint("attempt BETWEEN 0 AND 10", name="f04_intent_attempt"),
        sa.CheckConstraint(
            "(attempt_token IS NULL AND lease_until IS NULL) OR "
            "(attempt>0 AND attempt_token IS NOT NULL AND lease_until IS NOT NULL)",
            name="f04_intent_lease",
        ),
        schema="ops",
    )
    return metadata
