"""Tenant-only processing ledger and complete publication bindings; no cross-DB FK."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

from rag_platform.embeddings.original_anchor_f05_0005 import build_metadata as previous

VERSION = "f05_tenant_0006"
PREVIOUS = "f05_tenant_0005"
IDENTITY = (
    "version_id",
    "space_id",
    "document_id",
    "repository_id",
    "actor_id",
    "profile_fingerprint",
)
ERRORS = (
    "NONE",
    "DEPENDENCY_UNAVAILABLE",
    "EMBEDDING_FAILED",
    "PROFILE_MISMATCH",
    "INPUT_TOO_LONG",
    "DIMENSION_MISMATCH",
    "INVALID_VECTOR",
    "QUOTA_EXCEEDED",
    "AUTHORIZATION_CHANGED",
    "TOMBSTONED",
    "STOP_REQUESTED",
    "LEASE_EXHAUSTED",
)


def _replace(table, name, sql):
    old = next(c for c in table.constraints if c.name == name)
    table.constraints.remove(old)
    table.append_constraint(sa.CheckConstraint(sql, name=name))


def _identity_columns():
    return [
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("space_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("profile_fingerprint", sa.String(64), nullable=False),
    ]


def _stamp(name):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


def build_metadata():
    metadata = previous()
    versions = metadata.tables["knowledge.document_versions"]
    # PUBLISHED preserves all F04 completed provenance; only its state may change.
    for name in ("version_state", "f04_version_complete", "f04_version_failure"):
        old = str(next(c for c in versions.constraints if c.name == name).sqltext)
        if name == "version_state":
            sql = old[:-1] + ", 'PUBLISHED')"
        else:
            sql = old.replace(
                "state='READY_FOR_EMBEDDING'", "state IN ('READY_FOR_EMBEDDING','PUBLISHED')"
            )
            sql = sql.replace(
                "state<>'READY_FOR_EMBEDDING'", "state NOT IN ('READY_FOR_EMBEDDING','PUBLISHED')"
            )
        _replace(versions, name, sql)
    audit = metadata.tables["ops.audit_events"]
    old_audit = str(next(c for c in audit.constraints if c.name == "document_audit_action").sqltext)
    _replace(audit, "document_audit_action", old_audit[:-1] + ", 'EMBEDDING_PUBLISHED')")
    documents = metadata.tables["knowledge.documents"]
    _replace(documents, "f04_document_kind", "current_version_kind IN ('ORIGINAL','PROCESSED')")
    intents = sa.Table(
        "embedding_intents",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        *_identity_columns(),
        sa.Column("version_kind", sa.String(16), nullable=False, server_default="PROCESSED"),
        sa.Column("dispatch_state", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("job_id", sa.Uuid(), nullable=True, unique=True),
        sa.Column("dispatched_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attempt_token", sa.Uuid()),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(32), nullable=False, server_default="NONE"),
        _stamp("created_at"),
        _stamp("updated_at"),
        sa.UniqueConstraint("version_id", "space_id", name="f05_embedding_intent_once"),
        sa.UniqueConstraint("id", *IDENTITY, name="f05_embedding_intent_identity"),
        sa.ForeignKeyConstraint(
            ["version_id", "document_id", "repository_id", "version_kind"],
            [
                "knowledge.document_versions." + c
                for c in ("id", "document_id", "repository_id", "kind")
            ],
            name="f05_embedding_version",
        ),
        sa.ForeignKeyConstraint(
            ["space_id", "profile_fingerprint"],
            ["knowledge.embedding_spaces.id", "knowledge.embedding_spaces.profile_fingerprint"],
            name="f05_embedding_space",
        ),
        sa.CheckConstraint("version_kind='PROCESSED'", name="f05_embedding_processed"),
        sa.CheckConstraint(
            "status IN ('PENDING','RUNNING','COMPLETE','FAILED')", name="f05_embedding_status"
        ),
        sa.CheckConstraint("error_code IN " + repr(ERRORS), name="f05_embedding_error"),
        sa.CheckConstraint(
            "(status IN ('PENDING','RUNNING','COMPLETE') AND error_code='NONE') OR "
            "(status='FAILED' AND error_code<>'NONE')",
            name="f05_embedding_outcome",
        ),
        sa.CheckConstraint("attempt BETWEEN 0 AND 10", name="f05_embedding_attempt"),
        sa.CheckConstraint(
            "(status<>'RUNNING' AND attempt_token IS NULL AND lease_until IS NULL) OR "
            "(status='RUNNING' AND attempt>0 AND attempt_token IS NOT NULL "
            "AND lease_until IS NOT NULL)",
            name="f05_embedding_lease",
        ),
        sa.CheckConstraint(
            "(dispatch_state='PENDING' AND job_id IS NULL AND dispatched_at IS NULL) OR "
            "(dispatch_state='DISPATCHED' AND job_id IS NOT NULL AND dispatched_at IS NOT NULL)",
            name="f05_embedding_dispatch",
        ),
        schema="ops",
    )
    spaces = metadata.tables["knowledge.embedding_spaces"]
    spaces.append_constraint(
        sa.UniqueConstraint("id", "profile_fingerprint", name="f05_space_profile_identity")
    )
    for name, schema in (("embedding_batches", "ops"), ("embedding_publications", "knowledge")):
        table = sa.Table(
            name,
            metadata,
            *_identity_columns(),
            sa.Column("intent_id", sa.Uuid(), nullable=False),
            sa.ForeignKeyConstraint(
                ["intent_id", *IDENTITY],
                [intents.fullname + "." + c for c in ("id", *IDENTITY)],
                name="f05_" + name + "_intent",
            ),
            schema=schema,
        )
        if name == "embedding_batches":
            table.append_column(sa.Column("ordinal", sa.Integer(), nullable=False))
            table.append_column(sa.Column("chunk_ids", ARRAY(sa.Uuid()), nullable=False))
            table.append_column(sa.Column("input_tokens", sa.Integer(), nullable=False))
            table.append_column(sa.Column("requests", sa.Integer(), nullable=False))
            table.append_column(sa.Column("elapsed_ms", sa.BigInteger(), nullable=False))
            table.append_column(_stamp("created_at"))
            table.append_constraint(sa.PrimaryKeyConstraint("intent_id", "ordinal"))
            table.append_constraint(
                sa.CheckConstraint(
                    "ordinal BETWEEN 0 AND 9999 AND cardinality(chunk_ids) BETWEEN 1 AND 32 "
                    "AND array_position(chunk_ids,NULL) IS NULL "
                    "AND input_tokens BETWEEN 1 AND 4194304 AND requests=1 "
                    "AND elapsed_ms BETWEEN 0 AND 86400000",
                    name="f05_embedding_batch_limits",
                )
            )
        else:
            table.append_column(sa.Column("chunk_count", sa.Integer(), nullable=False))
            table.append_column(_stamp("published_at"))
            table.append_constraint(sa.PrimaryKeyConstraint("version_id", "space_id"))
            table.append_constraint(
                sa.UniqueConstraint("intent_id", name="f05_publication_intent_once")
            )
            table.append_constraint(
                sa.CheckConstraint(
                    "chunk_count BETWEEN 1 AND 10000",
                    name="f05_publication_chunks",
                )
            )
    return metadata
