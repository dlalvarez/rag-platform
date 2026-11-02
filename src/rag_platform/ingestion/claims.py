"""Short control fence spanning a tenant commit; no distributed-ACID claim."""

from contextlib import contextmanager
from dataclasses import dataclass, field

import sqlalchemy as sa

from rag_platform.ingestion.queue import Claim, DurableQueue, QueueError, _now


class ClaimExpired(RuntimeError):
    def __init__(self):
        super().__init__("CLAIM_EXPIRED")


@dataclass(repr=False)
class CommitGuard:
    queue: object = field(repr=False)
    claim: Claim
    connection: object = field(repr=False)
    intent_id: object = field(repr=False)
    max_attempts: int
    active: bool = True

    def __repr__(self):
        return "CommitGuard(<private>)"

    def check(self):
        if not self.active:
            raise ClaimExpired()
        now = _now(self.connection)
        deadline = self.connection.scalar(
            sa.select(self.queue._jobs.c.lease_until).where(self.queue._fence(self.claim, now))
        )
        if deadline is None:
            raise ClaimExpired()
        return deadline

    def complete(self):
        self.check()
        now = _now(self.connection)
        changed = self.connection.execute(
            sa.update(self.queue._jobs)
            .where(self.queue._fence(self.claim, now))
            .values(
                status="SUCCEEDED",
                error_code="NONE",
                lease_token=None,
                lease_until=None,
                finished_at=now,
                updated_at=now,
            )
        ).rowcount
        if changed != 1:
            raise ClaimExpired()


@contextmanager
def locked_claim(queue, claim):
    if not isinstance(queue, DurableQueue) or not isinstance(claim, Claim):
        raise QueueError("INPUT_INVALID")
    guard = None
    with queue.engine.begin() as c:
        if c.dialect.name == "postgresql":
            c.exec_driver_sql("SET LOCAL lock_timeout='5s'")
            c.exec_driver_sql("SET LOCAL statement_timeout='15s'")
        if not queue._locked(c, claim):
            raise ClaimExpired()
        intent_id = c.scalar(
            sa.select(queue._jobs.c.idempotency_id).where(queue._fence(claim, _now(c)))
        )
        if intent_id is None:
            raise ClaimExpired()
        max_attempts = c.scalar(
            sa.select(queue._jobs.c.max_attempts).where(queue._fence(claim, _now(c)))
        )
        if max_attempts is None:
            raise ClaimExpired()
        guard = CommitGuard(queue, claim, c, intent_id, max_attempts)
        try:
            guard.check()  # Recheck the database clock after acquiring the lock.
            yield guard
        finally:
            guard.active = False
