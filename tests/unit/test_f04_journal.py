"""Intent boundary/relay invariants offline; tenant SQL is exercised on ragdev01."""

from dataclasses import replace
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa

from rag_platform.ingestion.journal import (
    IngestionError,
    Intent,
    enqueue,
    identifiers,
    pending,
    request,
)
from rag_platform.ingestion.queue import DurableQueue, QueueError
from rag_platform.ingestion.queue_schema import jobs


@pytest.fixture
def queue():
    engine = sa.create_engine("sqlite://")
    jobs.create(engine)
    yield DurableQueue(engine, tenant_scope=(UUID(int=1),))
    engine.dispose()


def plan():
    return Intent(*(uuid4() for _ in range(5)))


def test_lost_enqueue_ack_replays_same_envelope(queue):
    intent = plan()
    first = enqueue(queue, UUID(int=1), intent)
    # Caller crashed before persisting local dispatch; exact replay is safe.
    assert enqueue(queue, UUID(int=1), intent) == first
    with queue.engine.connect() as c:
        row = c.execute(sa.select(jobs)).mappings().one()
    assert row["idempotency_id"] == intent.id
    assert row["version_id"] == intent.version_id
    assert row["actor_id"] == intent.actor_id
    assert row["document_id"] == intent.document_id
    assert row["attempts"] == 0


@pytest.mark.parametrize("field", ["actor_id", "document_id", "id"])
def test_relay_cannot_adopt_other_actor_document_or_intent(queue, field):
    intent = plan()
    enqueue(queue, UUID(int=1), intent)
    with pytest.raises(QueueError, match="IDEMPOTENCY_CONFLICT"):
        enqueue(queue, UUID(int=1), replace(intent, **{field: uuid4()}))
    with queue.engine.connect() as c:
        assert c.scalar(sa.select(sa.func.count()).select_from(jobs)) == 1


@pytest.mark.parametrize("value", [None, "uuid", UUID(int=0), 1])
def test_ids_rejected_before_sql(value):
    with pytest.raises(IngestionError, match="INPUT_INVALID"):
        identifiers(value)


@pytest.mark.parametrize("limit", [0, 101, True, "25"])
def test_unbounded_batch_rejected_before_sql(limit):
    with pytest.raises(IngestionError, match="INPUT_INVALID"):
        pending(None, limit=limit)


def test_bad_configuration_rejected_before_sql():
    with pytest.raises(IngestionError, match="INPUT_INVALID"):
        request(None, uuid4(), uuid4(), uuid4(), uuid4(), {"size": 128})


def test_private_plan_repr_and_closed_errors():
    intent = plan()
    assert str(intent.actor_id) not in repr(intent)
    assert str(intent.version_id) not in repr(intent)
    assert str(IngestionError("private provider body")) == "DEPENDENCY_UNAVAILABLE"
    assert str(IngestionError({"private": "body"})) == "DEPENDENCY_UNAVAILABLE"
