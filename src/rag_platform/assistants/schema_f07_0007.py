"""Frozen additive assistant schema. No conversation storage or control-plane content."""

import sqlalchemy as sa

from rag_platform.embeddings.publication_schema_f05_0006 import build_metadata as previous

VERSION = "f07_tenant_0007"
PREVIOUS = "f05_tenant_0006"
TABLES = ("assistant.assistants", "assistant.repository_links", "assistant.audit_events")


def _stamp(name):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


def build_metadata():
    metadata = previous()
    sa.Table(
        "assistants",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("purpose", sa.String(2000), nullable=False),
        sa.Column("space_id", sa.Uuid(), nullable=False),
        sa.Column("generation_fingerprint", sa.String(64), nullable=False),
        sa.Column("top_k", sa.SmallInteger(), nullable=False),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("state", sa.String(16), nullable=False, server_default="ACTIVE"),
        _stamp("created_at"),
        _stamp("updated_at"),
        sa.UniqueConstraint("id", "space_id", name="f07_assistant_space_identity"),
        sa.ForeignKeyConstraint(
            ["space_id"],
            ["knowledge.embedding_spaces.id"],
            name="f07_assistant_space",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 120 AND name=btrim(name)", name="f07_assistant_name"
        ),
        sa.CheckConstraint("char_length(purpose)<=2000", name="f07_assistant_purpose"),
        sa.CheckConstraint(
            "generation_fingerprint ~ '^[0-9a-f]{64}$'", name="f07_assistant_profile"
        ),
        sa.CheckConstraint("top_k BETWEEN 1 AND 8", name="f07_assistant_top_k"),
        sa.CheckConstraint("revision>=1", name="f07_assistant_revision"),
        sa.CheckConstraint("state IN ('ACTIVE','DELETED')", name="f07_assistant_state"),
        sa.CheckConstraint("updated_at>=created_at", name="f07_assistant_timestamps"),
        schema="assistant",
    )
    sa.Table(
        "repository_links",
        metadata,
        sa.Column("assistant_id", sa.Uuid(), primary_key=True),
        sa.Column("repository_id", sa.Uuid(), primary_key=True),
        sa.ForeignKeyConstraint(
            ["assistant_id"],
            ["assistant.assistants.id"],
            name="f07_link_assistant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["knowledge.repositories.id"],
            name="f07_link_repository",
            ondelete="RESTRICT",
        ),
        schema="assistant",
    )
    sa.Table(
        "audit_events",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("assistant_id", sa.Uuid(), nullable=False),
        sa.Column("principal_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        _stamp("created_at"),
        sa.ForeignKeyConstraint(
            ["assistant_id"],
            ["assistant.assistants.id"],
            name="f07_event_assistant",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "action IN ('ASSISTANT_CREATED','ASSISTANT_UPDATED','ASSISTANT_DELETED')",
            name="f07_assistant_audit_action",
        ),
        schema="assistant",
    )
    sa.Index(
        "f07_assistants_owner",
        metadata.tables["assistant.assistants"].c.owner_id,
        metadata.tables["assistant.assistants"].c.id,
    )
    return metadata
