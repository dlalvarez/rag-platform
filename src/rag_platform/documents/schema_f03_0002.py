"""Immutable F03-0002 schema factory. Future revisions must not edit this definition."""

from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

VERSION = "f03_tenant_0002"


def build_metadata():
    metadata = sa.MetaData()

    def identifier(name="id"):
        return sa.Column(name, sa.Uuid(), primary_key=name == "id", nullable=False, default=uuid4)

    def timestamp(name="created_at"):
        return sa.Column(
            name,
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        )

    repositories = sa.Table(
        "repositories",
        metadata,
        identifier(),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column(
            "config",
            JSONB,
            nullable=False,
            server_default=sa.text("""'{"language":"auto"}'::jsonb"""),
        ),
        sa.Column("state", sa.String(16), nullable=False, server_default="ACTIVE"),
        timestamp(),
        timestamp("updated_at"),
        sa.CheckConstraint(
            "length(name) BETWEEN 1 AND 120 AND name=btrim(name) AND name !~ '[[:cntrl:]]'",
            name="repository_name",
        ),
        sa.CheckConstraint("state IN ('ACTIVE','DELETED')", name="repository_state"),
        sa.CheckConstraint(
            "jsonb_typeof(config)='object' AND config - 'language' = '{}'::jsonb "
            "AND config ? 'language' AND jsonb_typeof(config->'language')='string' "
            "AND length(config->>'language') BETWEEN 1 AND 35 "
            "AND (config->>'language') ~ '^(auto|[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*)$'",
            name="repository_config",
        ),
        schema="knowledge",
    )
    sa.Index(
        "repository_active_name",
        sa.func.lower(repositories.c.name),
        unique=True,
        postgresql_where=repositories.c.state == "ACTIVE",
    )

    sa.Table(
        "repository_acl",
        metadata,
        sa.Column(
            "repository_id", sa.Uuid(), sa.ForeignKey("knowledge.repositories.id"), primary_key=True
        ),
        sa.Column("principal_id", sa.Uuid(), primary_key=True),
        sa.Column("role", sa.String(16), nullable=False),
        timestamp(),
        timestamp("updated_at"),
        sa.CheckConstraint(
            "role IN ('owner','admin','editor','reader')", name="repository_acl_role"
        ),
        schema="security",
    )

    sa.Table(
        "sources",
        metadata,
        identifier(),
        sa.Column(
            "repository_id", sa.Uuid(), sa.ForeignKey("knowledge.repositories.id"), nullable=False
        ),
        sa.Column("provider", sa.String(16), nullable=False, server_default="UPLOAD"),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        timestamp(),
        sa.UniqueConstraint("id", "repository_id", name="source_repository_identity"),
        sa.CheckConstraint("provider='UPLOAD'", name="source_provider"),
        schema="knowledge",
    )

    documents = sa.Table(
        "documents",
        metadata,
        identifier(),
        sa.Column(
            "repository_id", sa.Uuid(), sa.ForeignKey("knowledge.repositories.id"), nullable=False
        ),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("current_version_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default="RECEIVED"),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        timestamp(),
        sa.UniqueConstraint("id", "repository_id", name="document_repository_identity"),
        sa.ForeignKeyConstraint(
            ["source_id", "repository_id"],
            ["knowledge.sources.id", "knowledge.sources.repository_id"],
            name="document_source_repository",
        ),
        sa.ForeignKeyConstraint(
            ["current_version_id", "id", "repository_id"],
            [
                "knowledge.document_versions.id",
                "knowledge.document_versions.document_id",
                "knowledge.document_versions.repository_id",
            ],
            name="document_current_version",
            deferrable=True,
            initially="DEFERRED",
            use_alter=True,
        ),
        sa.CheckConstraint("state='RECEIVED'", name="document_state"),
        schema="knowledge",
    )

    sa.Table(
        "document_versions",
        metadata,
        identifier(),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("mime", sa.String(100), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("blob_key", sa.String(100), nullable=False, unique=True),
        sa.Column("state", sa.String(16), nullable=False, server_default="RECEIVED"),
        timestamp(),
        sa.UniqueConstraint(
            "id", "document_id", "repository_id", name="version_document_repository"
        ),
        sa.ForeignKeyConstraint(
            ["document_id", "repository_id"],
            ["knowledge.documents.id", "knowledge.documents.repository_id"],
            name="version_document_identity",
        ),
        sa.CheckConstraint("state='RECEIVED'", name="version_state"),
        sa.CheckConstraint("byte_size BETWEEN 1 AND 1073741824", name="version_size_ceiling"),
        sa.CheckConstraint("content_hash ~ '^[0-9a-f]{64}$'", name="version_sha256"),
        sa.CheckConstraint(
            "length(filename) BETWEEN 1 AND 255 AND filename=btrim(filename) "
            "AND position('/' in filename)=0 AND position(chr(92) in filename)=0 "
            "AND filename !~ '[[:cntrl:]]'",
            name="version_filename",
        ),
        sa.CheckConstraint(
            "mime IN ('application/pdf','text/plain','text/markdown',"
            "'application/vnd.openxmlformats-officedocument.wordprocessingml.document')",
            name="version_mime",
        ),
        sa.CheckConstraint(
            "blob_key = 'f03/' || replace(repository_id::text,'-','') "
            "|| '/' || replace(id::text,'-','')",
            name="version_owned_key",
        ),
        schema="knowledge",
    )
    sa.Index("document_repository_page", documents.c.repository_id, documents.c.id)

    sa.Table(
        "document_receipts",
        metadata,
        identifier(),
        sa.Column(
            "repository_id", sa.Uuid(), sa.ForeignKey("knowledge.repositories.id"), nullable=False
        ),
        sa.Column("principal_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("candidate_document_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("version_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("committed_version_id", sa.Uuid(), nullable=True),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        timestamp(),
        timestamp("updated_at"),
        sa.UniqueConstraint(
            "repository_id", "principal_id", "idempotency_key", name="receipt_actor_repository_key"
        ),
        sa.CheckConstraint(
            "length(idempotency_key) BETWEEN 16 AND 128 AND idempotency_key !~ '[[:cntrl:]]'",
            name="receipt_key",
        ),
        sa.CheckConstraint("fingerprint ~ '^[0-9a-f]{64}$'", name="receipt_fingerprint"),
        sa.CheckConstraint("byte_size BETWEEN 1 AND 1073741824", name="receipt_size_ceiling"),
        sa.CheckConstraint(
            "state IN ('PENDING','OBJECT_STORED','COMMITTED','FAILED')", name="receipt_state"
        ),
        sa.ForeignKeyConstraint(
            ["committed_version_id", "candidate_document_id", "repository_id"],
            [
                "knowledge.document_versions.id",
                "knowledge.document_versions.document_id",
                "knowledge.document_versions.repository_id",
            ],
            name="receipt_committed_identity",
        ),
        sa.CheckConstraint(
            "(state='COMMITTED' AND committed_version_id IS NOT NULL "
            "AND committed_version_id=version_id AND lease_until IS NULL) OR "
            "(state<>'COMMITTED' AND committed_version_id IS NULL)",
            name="receipt_commit_identity",
        ),
        sa.CheckConstraint(
            "(state IN ('PENDING','OBJECT_STORED') AND lease_until IS NOT NULL) OR "
            "state IN ('COMMITTED','FAILED')",
            name="receipt_active_lease",
        ),
        schema="ops",
    )

    sa.Table(
        "audit_events",
        metadata,
        identifier(),
        sa.Column("principal_id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        timestamp(),
        sa.CheckConstraint(
            "action IN ('REPOSITORY_CREATED','REPOSITORY_UPDATED','REPOSITORY_DELETED',"
            "'ACL_CHANGED','DOCUMENT_RECEIVED','DOCUMENT_DOWNLOADED','ACCESS_DENIED')",
            name="document_audit_action",
        ),
        sa.CheckConstraint("outcome IN ('OK','DENIED','FAILED')", name="document_audit_outcome"),
        schema="ops",
    )
    return metadata
