"""Trusted durable queue. Envelopes are not authorization to read tenant content."""

from dataclasses import dataclass
from datetime import UTC, timedelta
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from rag_platform.ingestion.queue_schema import ERRORS, jobs


class QueueError(RuntimeError):
    def __init__(self, code="QUEUE_UNAVAILABLE"):
        self.code = (
            code if code in {"INPUT_INVALID", "IDEMPOTENCY_CONFLICT"} else "QUEUE_UNAVAILABLE"
        )
        super().__init__(self.code)


@dataclass(frozen=True)
class Claim:
    id: UUID
    tenant_id: UUID
    actor_id: UUID
    document_id: UUID
    version_id: UUID
    attempt: int
    token: UUID


def _ids(*values):
    if not all(isinstance(v, UUID) and v.int != 0 for v in values):
        raise QueueError("INPUT_INVALID")


def _now(connection):
    expression = (
        sa.func.clock_timestamp()
        if connection.dialect.name == "postgresql"
        else sa.func.current_timestamp(type_=sa.DateTime())
    )
    value = connection.scalar(sa.select(expression))
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class DurableQueue:
    def __init__(self, engine, *, lease_seconds=60, max_attempts=5, tenant_scope=None):
        if type(lease_seconds) is not int or not 1 <= lease_seconds <= 300:
            raise QueueError("INPUT_INVALID")
        if type(max_attempts) is not int or not 1 <= max_attempts <= 10:
            raise QueueError("INPUT_INVALID")
        if tenant_scope is not None:
            tenant_scope = tuple(tenant_scope)
            _ids(*tenant_scope)
            if not tenant_scope:
                raise QueueError("INPUT_INVALID")
        self.engine, self.lease_seconds = engine, lease_seconds
        self.max_attempts, self.scope = max_attempts, tenant_scope

    def _scope(self):
        return jobs.c.tenant_id.in_(self.scope) if self.scope is not None else sa.true()

    def enqueue(self, tenant, actor, document, version, idempotency):
        _ids(tenant, actor, document, version, idempotency)
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
                    kind="INGEST",
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
                        jobs.c.kind == "INGEST",
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
                }.items()
            ):
                raise QueueError("IDEMPOTENCY_CONFLICT")
            return row["id"]

    def claim(self):
        # Bound terminal cleanup per poll and skip locks held by other consumers.
        with self.engine.begin() as c:
            now = _now(c)
            ready = sa.or_(
                sa.and_(jobs.c.status.in_(("PENDING", "RETRY")), jobs.c.available_at <= now),
                sa.and_(jobs.c.status == "RUNNING", jobs.c.lease_until <= now),
            )
            for _ in range(100):
                row = (
                    c.execute(
                        sa.select(jobs)
                        .where(self._scope(), ready)
                        .order_by(jobs.c.available_at, jobs.c.id)
                        .with_for_update(skip_locked=True)
                        .limit(1)
                    )
                    .mappings()
                    .first()
                )
                if row is None:
                    return None
                now = _now(c)
                if row["attempts"] >= row["max_attempts"]:
                    c.execute(
                        sa.update(jobs)
                        .where(jobs.c.id == row["id"])
                        .values(
                            status="FAILED",
                            error_code="LEASE_EXHAUSTED",
                            lease_token=None,
                            lease_until=None,
                            finished_at=now,
                            updated_at=now,
                        )
                    )
                    continue
                token, attempt = uuid4(), row["attempts"] + 1
                c.execute(
                    sa.update(jobs)
                    .where(jobs.c.id == row["id"])
                    .values(
                        status="RUNNING",
                        attempts=attempt,
                        lease_token=token,
                        lease_until=now + timedelta(seconds=self.lease_seconds),
                        updated_at=now,
                        error_code="NONE",
                    )
                )
                return Claim(
                    row["id"],
                    row["tenant_id"],
                    row["actor_id"],
                    row["document_id"],
                    row["version_id"],
                    attempt,
                    token,
                )
            return None

    def _fence(self, claim, now):
        if not isinstance(claim, Claim):
            raise QueueError("INPUT_INVALID")
        _ids(
            claim.id,
            claim.tenant_id,
            claim.actor_id,
            claim.document_id,
            claim.version_id,
            claim.token,
        )
        if type(claim.attempt) is not int or claim.attempt < 1:
            raise QueueError("INPUT_INVALID")
        return sa.and_(
            self._scope(),
            jobs.c.id == claim.id,
            jobs.c.tenant_id == claim.tenant_id,
            jobs.c.actor_id == claim.actor_id,
            jobs.c.document_id == claim.document_id,
            jobs.c.version_id == claim.version_id,
            jobs.c.status == "RUNNING",
            jobs.c.attempts == claim.attempt,
            jobs.c.lease_token == claim.token,
            jobs.c.lease_until > now,
        )

    def _locked(self, c, claim):
        # UPDATE may wait behind another transaction. Recheck database time after
        # taking the lock, never authorize completion using a pre-wait timestamp.
        now = _now(c)
        row = c.execute(
            sa.select(jobs.c.id).where(self._fence(claim, now)).with_for_update()
        ).first()
        return row is not None

    def heartbeat(self, claim):
        with self.engine.begin() as c:
            if not self._locked(c, claim):
                return False
            now = _now(c)
            return (
                c.execute(
                    sa.update(jobs)
                    .where(self._fence(claim, now))
                    .values(lease_until=now + timedelta(seconds=self.lease_seconds), updated_at=now)
                ).rowcount
                == 1
            )

    def complete(self, claim):
        with self.engine.begin() as c:
            if not self._locked(c, claim):
                return False
            now = _now(c)
            return (
                c.execute(
                    sa.update(jobs)
                    .where(self._fence(claim, now))
                    .values(
                        status="SUCCEEDED",
                        error_code="NONE",
                        lease_token=None,
                        lease_until=None,
                        finished_at=now,
                        updated_at=now,
                    )
                ).rowcount
                == 1
            )

    def fail(self, claim, code, *, retryable=False):
        if code not in ERRORS or code == "NONE" or type(retryable) is not bool:
            raise QueueError("INPUT_INVALID")
        with self.engine.begin() as c:
            now = _now(c)
            row = (
                c.execute(sa.select(jobs).where(self._fence(claim, now)).with_for_update())
                .mappings()
                .first()
            )
            if row is None:
                return False
            # Recheck the clock after waiting for a row lock. A lease cannot revive.
            now = _now(c)
            retry = retryable and row["attempts"] < row["max_attempts"]
            return (
                c.execute(
                    sa.update(jobs)
                    .where(self._fence(claim, now))
                    .values(
                        status="RETRY" if retry else "FAILED",
                        error_code=code,
                        available_at=now + timedelta(seconds=min(60, 2 ** (row["attempts"] - 1))),
                        lease_token=None,
                        lease_until=None,
                        updated_at=now,
                        finished_at=None if retry else now,
                    )
                ).rowcount
                == 1
            )
