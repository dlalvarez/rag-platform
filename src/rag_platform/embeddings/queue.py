"""EMBED-only durable consumer; envelopes never authorize tenant content access."""

import re
from dataclasses import dataclass
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from rag_platform.embeddings.queue_schema_f05_0007 import ERRORS, jobs
from rag_platform.ingestion.queue import Claim, DurableQueue, QueueError, _ids, _now


def _profile(value):
    if not isinstance(value, str) or re.fullmatch("[0-9a-f]{64}", value) is None:
        raise QueueError("INPUT_INVALID")


@dataclass(frozen=True)
class EmbeddingClaim(Claim):
    space_id: UUID
    profile_fingerprint: str


class EmbeddingQueue(DurableQueue):
    _jobs = jobs
    _errors = ERRORS
    _kind = "EMBED"

    def enqueue(self, tenant, actor, document, version, idempotency, space, profile):
        _ids(tenant, actor, document, version, idempotency, space)
        _profile(profile)
        if self.scope is not None and tenant not in self.scope:
            raise QueueError("INPUT_INVALID")
        with self.engine.begin() as c:
            now = _now(c)
            insert = pg_insert if c.dialect.name == "postgresql" else sqlite_insert
            c.execute(
                insert(jobs)
                .values(
                    id=uuid4(),
                    tenant_id=tenant,
                    actor_id=actor,
                    document_id=document,
                    version_id=version,
                    idempotency_id=idempotency,
                    kind="EMBED",
                    space_id=space,
                    profile_fingerprint=profile,
                    max_attempts=self.max_attempts,
                    available_at=now,
                    created_at=now,
                    updated_at=now,
                )
                .on_conflict_do_nothing()
            )
            row = (
                c.execute(
                    sa.select(jobs).where(
                        jobs.c.tenant_id == tenant,
                        jobs.c.version_id == version,
                        jobs.c.kind == "EMBED",
                        jobs.c.space_id == space,
                    )
                )
                .mappings()
                .first()
            )
            if row is None or any(
                row[k] != v
                for k, v in {
                    "actor_id": actor,
                    "document_id": document,
                    "idempotency_id": idempotency,
                    "profile_fingerprint": profile,
                }.items()
            ):
                raise QueueError("IDEMPOTENCY_CONFLICT")
            return row["id"]

    def _claim(self, row, attempt, token):
        return EmbeddingClaim(
            row["id"],
            row["tenant_id"],
            row["actor_id"],
            row["document_id"],
            row["version_id"],
            attempt,
            token,
            row["space_id"],
            row["profile_fingerprint"],
        )

    def _fence(self, claim, now):
        if not isinstance(claim, EmbeddingClaim):
            raise QueueError("INPUT_INVALID")
        _ids(claim.space_id)
        _profile(claim.profile_fingerprint)
        return sa.and_(
            super()._fence(claim, now),
            jobs.c.space_id == claim.space_id,
            jobs.c.profile_fingerprint == claim.profile_fingerprint,
        )

    def fail(self, claim, code, *, retryable=False):
        if type(retryable) is not bool:
            raise QueueError("INPUT_INVALID")
        if code in {
            "PROFILE_MISMATCH",
            "INPUT_TOO_LONG",
            "DIMENSION_MISMATCH",
            "INVALID_VECTOR",
            "AUTHORIZATION_CHANGED",
            "TOMBSTONED",
        }:
            retryable = False
        return super().fail(claim, code, retryable=retryable)
