"""Immutable F05 envelope evolution: identifiers/profile hash only, never content."""

import sqlalchemy as sa

from rag_platform.control.identity_models import User
from rag_platform.control.models import Tenant

VERSION = "f05_control_0007"
metadata = sa.MetaData()
STATES = ("PENDING", "RUNNING", "RETRY", "SUCCEEDED", "FAILED", "CANCELLED")
ERRORS = (
    "NONE",
    "DEPENDENCY_UNAVAILABLE",
    "PARSER_INVALID",
    "PARSER_LIMIT",
    "NEEDS_OCR",
    "AUTHORIZATION_CHANGED",
    "TOMBSTONED",
    "STOP_REQUESTED",
    "LEASE_EXHAUSTED",
    "PROCESSING_FAILED",
    "EMBEDDING_FAILED",
    "PROFILE_MISMATCH",
    "INPUT_TOO_LONG",
    "DIMENSION_MISMATCH",
    "INVALID_VECTOR",
    "QUOTA_EXCEEDED",
)
jobs = sa.Table(
    "job_envelopes",
    metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey(Tenant.__table__.c.id), nullable=False),
    sa.Column("actor_id", sa.Uuid(), sa.ForeignKey(User.__table__.c.id), nullable=False),
    sa.Column("document_id", sa.Uuid(), nullable=False),
    sa.Column("version_id", sa.Uuid(), nullable=False),
    sa.Column("idempotency_id", sa.Uuid(), nullable=False),
    sa.Column("kind", sa.String(8), nullable=False, server_default="INGEST"),
    sa.Column("space_id", sa.Uuid(), nullable=True),
    sa.Column("profile_fingerprint", sa.String(64), nullable=True),
    sa.Column("status", sa.String(12), nullable=False, server_default="PENDING"),
    sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("max_attempts", sa.Integer(), nullable=False),
    sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("lease_token", sa.Uuid(), nullable=True),
    sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
    sa.Column("error_code", sa.String(32), nullable=False, server_default="NONE"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    sa.UniqueConstraint("tenant_id", "idempotency_id", name="job_idempotency"),
    sa.CheckConstraint("kind IN ('INGEST','EMBED')", name="job_kind"),
    sa.CheckConstraint(
        "(kind='INGEST' AND space_id IS NULL AND profile_fingerprint IS NULL) OR "
        "(kind='EMBED' AND space_id IS NOT NULL AND profile_fingerprint IS NOT NULL "
        "AND length(profile_fingerprint)=64)",
        name="job_embedding_profile",
    ),
    sa.CheckConstraint(
        "kind<>'EMBED' OR (profile_fingerprint ~ '^[0-9a-f]{64}$' "
        "AND space_id<>'00000000-0000-0000-0000-000000000000'::uuid)",
        name="job_embedding_hash",
    ).ddl_if(dialect="postgresql"),
    sa.CheckConstraint("status IN " + repr(STATES), name="job_status"),
    sa.CheckConstraint("error_code IN " + repr(ERRORS), name="job_error"),
    sa.CheckConstraint(
        "max_attempts BETWEEN 1 AND 10 AND attempts BETWEEN 0 AND max_attempts",
        name="job_attempts",
    ),
    sa.CheckConstraint(
        "(status = 'RUNNING' AND lease_token IS NOT NULL AND lease_until IS NOT NULL "
        "AND attempts > 0) OR "
        "(status <> 'RUNNING' AND lease_token IS NULL AND lease_until IS NULL)",
        name="job_lease",
    ),
    sa.CheckConstraint(
        "(status IN ('SUCCEEDED','FAILED','CANCELLED') AND finished_at IS NOT NULL) OR "
        "(status NOT IN ('SUCCEEDED','FAILED','CANCELLED') AND finished_at IS NULL)",
        name="job_finished",
    ),
)
sa.Index("job_claim_ready", jobs.c.status, jobs.c.available_at, jobs.c.lease_until, jobs.c.id)


sa.Index(
    "job_ingest_version_kind",
    jobs.c.tenant_id,
    jobs.c.version_id,
    jobs.c.kind,
    unique=True,
    postgresql_where=jobs.c.kind == "INGEST",
    sqlite_where=jobs.c.kind == "INGEST",
)
sa.Index(
    "job_embed_version_space",
    jobs.c.tenant_id,
    jobs.c.version_id,
    jobs.c.space_id,
    unique=True,
    postgresql_where=jobs.c.kind == "EMBED",
    sqlite_where=jobs.c.kind == "EMBED",
)
sa.Index(
    "job_embed_claim_ready",
    jobs.c.status,
    jobs.c.available_at,
    jobs.c.lease_until,
    jobs.c.id,
    postgresql_where=jobs.c.kind == "EMBED",
    sqlite_where=jobs.c.kind == "EMBED",
)
