"""EMBED queue identities, retries and stale leases; no inference or network."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa

from rag_platform.embeddings.queue import EmbeddingQueue
from rag_platform.embeddings.queue_schema_f05_0007 import jobs
from rag_platform.ingestion.claims import locked_claim
from rag_platform.ingestion.queue import DurableQueue, QueueError


@pytest.fixture
def queue():
    engine = sa.create_engine("sqlite://")
    jobs.create(engine)
    yield EmbeddingQueue(engine, tenant_scope=(UUID(int=1),), max_attempts=2)
    engine.dispose()


def enqueue(queue, **changes):
    values = dict(
        tenant=UUID(int=1),
        actor=UUID(int=2),
        document=UUID(int=3),
        version=UUID(int=4),
        idempotency=UUID(int=5),
        space=UUID(int=6),
        profile="a" * 64,
    )
    values.update(changes)
    return queue.enqueue(**values)


def update(queue, **values):
    with queue.engine.begin() as c:
        c.execute(sa.update(jobs).where(jobs.c.kind == "EMBED").values(**values))


def past():
    return datetime.now(UTC) - timedelta(seconds=5)


def test_replay_spaces_and_consumers_are_separate(queue):
    first = enqueue(queue)
    assert enqueue(queue) == first
    second = enqueue(queue, space=uuid4(), idempotency=uuid4(), profile="b" * 64)
    ingest = DurableQueue(queue.engine, tenant_scope=queue.scope)
    own = ingest.enqueue(UUID(int=1), UUID(int=2), UUID(int=3), UUID(int=4), uuid4())
    assert ingest.claim().id == own
    claims = [queue.claim(), queue.claim()]
    assert {c.id for c in claims} == {first, second}
    assert queue.claim() is None
    for claim in claims:
        assert queue.heartbeat(claim)
        with locked_claim(queue, claim) as guard:
            assert guard.check()
            guard.complete()
        assert not queue.complete(claim)


@pytest.mark.parametrize(
    "change",
    [
        {"actor": uuid4()},
        {"document": uuid4()},
        {"idempotency": uuid4()},
        {"profile": "b" * 64},
        {"version": uuid4()},
        {"space": uuid4()},
    ],
)
def test_conflicting_identity_is_not_reused(queue, change):
    enqueue(queue)
    with pytest.raises(QueueError, match="IDEMPOTENCY_CONFLICT"):
        enqueue(queue, **change)


@pytest.mark.parametrize(
    "field,value",
    [
        ("tenant_id", UUID(int=9)),
        ("actor_id", UUID(int=9)),
        ("document_id", UUID(int=9)),
        ("version_id", UUID(int=9)),
        ("space_id", UUID(int=9)),
        ("profile_fingerprint", "b" * 64),
        ("token", UUID(int=9)),
        ("attempt", 2),
        ("id", UUID(int=9)),
    ],
)
def test_every_identity_is_fenced(queue, field, value):
    enqueue(queue)
    claim = queue.claim()
    forged = replace(claim, **{field: value})
    assert not queue.heartbeat(forged)
    assert not queue.complete(forged)
    assert not queue.fail(forged, "EMBEDDING_FAILED")
    assert queue.complete(claim)


def test_stale_lease_backoff_exhaustion(queue):
    enqueue(queue)
    old = queue.claim()
    update(queue, lease_until=past())
    fresh = queue.claim()
    assert fresh.attempt == 2 and fresh.token != old.token
    assert not queue.complete(old) and not queue.heartbeat(old)
    assert queue.fail(fresh, "DEPENDENCY_UNAVAILABLE", retryable=True)
    assert queue.claim() is None
    with queue.engine.connect() as c:
        row = c.execute(sa.select(jobs)).mappings().one()
        assert row["status"] == "FAILED" and row["attempts"] == 2


def test_dependency_retry_and_unknown_error_redaction(queue):
    enqueue(queue)
    claim = queue.claim()
    with pytest.raises(QueueError, match="INPUT_INVALID"):
        queue.fail(claim, "private provider text")
    assert queue.fail(claim, "DEPENDENCY_UNAVAILABLE", retryable=True)
    assert queue.claim() is None
    update(queue, available_at=past())
    assert queue.complete(queue.claim())


@pytest.mark.parametrize(
    "code",
    [
        "PROFILE_MISMATCH",
        "INPUT_TOO_LONG",
        "DIMENSION_MISMATCH",
        "INVALID_VECTOR",
        "AUTHORIZATION_CHANGED",
        "TOMBSTONED",
    ],
)
def test_invalid_result_and_revocation_are_terminal(queue, code):
    enqueue(queue)
    assert queue.fail(queue.claim(), code, retryable=True)
    with queue.engine.connect() as c:
        assert c.scalar(sa.select(jobs.c.status)) == "FAILED"


@pytest.mark.parametrize(
    "change",
    [
        {"tenant": UUID(int=8)},
        {"space": UUID(int=0)},
        {"profile": "g" * 64},
        {"profile": "a" * 63},
        {"profile": None},
    ],
)
def test_invalid_inputs_cannot_enqueue(queue, change):
    with pytest.raises(QueueError, match="INPUT_INVALID"):
        enqueue(queue, **change)
    with queue.engine.connect() as c:
        assert c.scalar(sa.select(sa.func.count()).select_from(jobs)) == 0


def test_ingest_worker_rejects_embedding_consumer_before_io(queue):
    from types import SimpleNamespace

    from rag_platform.ingestion.worker import Worker

    runtime = SimpleNamespace(
        authority=SimpleNamespace(profile="embeddings", engine=queue.engine),
        scope=queue.scope,
    )
    with pytest.raises(ValueError, match="Explicit ingestion runtime"):
        Worker(runtime, queue)
