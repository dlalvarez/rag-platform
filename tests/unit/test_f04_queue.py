"""Queue invariants offline; PostgreSQL concurrency is verified separately on ragdev01."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from rag_platform.ingestion.queue import DurableQueue, QueueError
from rag_platform.ingestion.queue_schema import jobs


@pytest.fixture
def queue():
    engine = sa.create_engine("sqlite://")
    jobs.create(engine)
    result = DurableQueue(engine, tenant_scope=(UUID(int=1),), lease_seconds=10, max_attempts=2)
    yield result
    engine.dispose()


def enqueue(queue, **changes):
    values = dict(
        tenant=UUID(int=1),
        actor=UUID(int=2),
        document=UUID(int=3),
        version=UUID(int=4),
        idempotency=UUID(int=5),
    )
    values.update(changes)
    return queue.enqueue(**values)


def row(queue):
    with queue.engine.connect() as c:
        return c.execute(sa.select(jobs)).mappings().one()


def expire(queue):
    with queue.engine.begin() as c:
        c.execute(sa.update(jobs).values(lease_until=datetime.now(UTC) - timedelta(seconds=5)))


def test_replay_and_conflicts_preserve_identity(queue):
    first = enqueue(queue)
    assert enqueue(queue) == first
    for changes in (
        dict(actor=uuid4()),
        dict(document=uuid4()),
        dict(idempotency=uuid4()),
        dict(version=uuid4()),
    ):
        with pytest.raises(QueueError, match="IDEMPOTENCY_CONFLICT"):
            enqueue(queue, **changes)
    assert row(queue)["id"] == first
    assert row(queue)["attempts"] == 0


def test_claim_complete_and_no_duplicate(queue):
    enqueue(queue)
    claim = queue.claim()
    assert claim.attempt == 1 and queue.claim() is None
    assert queue.heartbeat(claim)
    assert queue.complete(claim)
    assert not queue.complete(claim) and not queue.heartbeat(claim)
    assert queue.claim() is None
    assert row(queue)["status"] == "SUCCEEDED"


def test_expired_lease_reclaimed_fences_old_worker(queue):
    enqueue(queue)
    old = queue.claim()
    expire(queue)
    assert not queue.heartbeat(old) and not queue.complete(old)
    fresh = queue.claim()
    assert fresh.id == old.id and fresh.attempt == 2 and fresh.token != old.token
    assert not queue.fail(old, "PROCESSING_FAILED", retryable=True)
    assert queue.complete(fresh)


def test_exhausted_crash_becomes_terminal(queue):
    enqueue(queue)
    first = queue.claim()
    expire(queue)
    second = queue.claim()
    expire(queue)
    assert queue.claim() is None
    assert row(queue)["status"] == "FAILED"
    assert row(queue)["error_code"] == "LEASE_EXHAUSTED"
    assert not queue.complete(first) and not queue.complete(second)


def test_backoff_and_terminal_error(queue):
    enqueue(queue)
    first = queue.claim()
    assert queue.fail(first, "DEPENDENCY_UNAVAILABLE", retryable=True)
    assert queue.claim() is None and row(queue)["status"] == "RETRY"
    with queue.engine.begin() as c:
        c.execute(sa.update(jobs).values(available_at=datetime.now(UTC) - timedelta(seconds=5)))
    last = queue.claim()
    assert queue.fail(last, "DEPENDENCY_UNAVAILABLE", retryable=True)
    assert row(queue)["status"] == "FAILED" and queue.claim() is None


def test_immediate_terminal_and_closed_error_codes(queue):
    enqueue(queue)
    claim = queue.claim()
    with pytest.raises(QueueError, match="INPUT_INVALID"):
        queue.fail(claim, "password=private provider message")
    assert queue.fail(claim, "NEEDS_OCR")
    assert row(queue)["error_code"] == "NEEDS_OCR"
    assert queue.claim() is None


@pytest.mark.parametrize(
    "change",
    [
        {"tenant_id": UUID(int=8)},
        {"actor_id": UUID(int=8)},
        {"document_id": UUID(int=8)},
        {"version_id": UUID(int=8)},
        {"token": UUID(int=8)},
        {"attempt": 2},
        {"id": UUID(int=8)},
    ],
)
def test_claim_every_identity_fenced(queue, change):
    enqueue(queue)
    claim = queue.claim()
    forged = replace(claim, **change)
    assert not queue.complete(forged) and not queue.heartbeat(forged)
    assert queue.complete(claim)


@pytest.mark.parametrize(
    "changes",
    [
        {"tenant": "client-input"},
        {"actor": UUID(int=0)},
        {"tenant": UUID(int=8)},
    ],
)
def test_input_and_scope_denied(queue, changes):
    with pytest.raises(QueueError, match="INPUT_INVALID"):
        enqueue(queue, **changes)
    with queue.engine.connect() as c:
        assert c.scalar(sa.select(sa.func.count()).select_from(jobs)) == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "RUNNING"},
        {"attempts": -1},
        {"max_attempts": 11},
        {"status": "SUCCEEDED"},
        {"error_code": "secret"},
    ],
)
def test_database_constraints(queue, changes):
    enqueue(queue)
    with pytest.raises(IntegrityError), queue.engine.begin() as c:
        c.execute(sa.update(jobs).values(**changes))


def test_content_and_secret_fields_absent():
    assert set(jobs.c.keys()) == {
        "id",
        "tenant_id",
        "actor_id",
        "document_id",
        "version_id",
        "idempotency_id",
        "kind",
        "status",
        "attempts",
        "max_attempts",
        "available_at",
        "lease_token",
        "lease_until",
        "error_code",
        "created_at",
        "updated_at",
        "finished_at",
    }
    assert not any(isinstance(c.type, (sa.JSON, sa.LargeBinary)) for c in jobs.c)
