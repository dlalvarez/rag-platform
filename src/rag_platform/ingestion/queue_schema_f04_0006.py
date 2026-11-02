"""Immutable F04 control envelope metadata: identifiers, leases and closed codes only."""

import sqlalchemy as sa

from rag_platform.control.identity_models import User
from rag_platform.control.models import Tenant

VERSION = "f04_control_0006"
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
    sa.UniqueConstraint("tenant_id", "version_id", "kind", name="job_version_kind"),
    sa.UniqueConstraint("tenant_id", "idempotency_id", name="job_idempotency"),
    sa.CheckConstraint("kind = 'INGEST'", name="job_kind"),
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
