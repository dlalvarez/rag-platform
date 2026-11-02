"""Future EMBED metadata coexists with the unmodified INGEST consumer."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import dialect
from sqlalchemy.schema import CreateTable

from rag_platform.embeddings.queue_schema_f05_0007 import jobs
from rag_platform.ingestion.queue import DurableQueue
from rag_platform.ingestion.queue_schema_f04_0006 import jobs as historical


@pytest.fixture
def queue():
    engine = sa.create_engine("sqlite://")
    jobs.create(engine)
    result = DurableQueue(engine, tenant_scope=(UUID(int=1),))
    yield result
    engine.dispose()


def embed(queue, *, space=None, version=None, key=None, **changes):
    now = datetime.now(UTC)
    data = dict(
        id=uuid4(),
        tenant_id=UUID(int=1),
        actor_id=UUID(int=2),
        document_id=UUID(int=3),
        version_id=version or UUID(int=4),
        idempotency_id=key or uuid4(),
        kind="EMBED",
        space_id=space or uuid4(),
        profile_fingerprint="a" * 64,
        max_attempts=3,
        available_at=now,
        created_at=now,
        updated_at=now,
    )
    data.update(changes)
    with queue.engine.begin() as c:
        c.execute(jobs.insert().values(**data))
    return data


def test_embed_spaces_coexist_and_ingest_claim_cannot_take_them(queue):
    first = embed(queue)
    second = embed(queue)
    own = queue.enqueue(UUID(int=1), UUID(int=2), UUID(int=3), UUID(int=4), UUID(int=5))
    assert queue.enqueue(UUID(int=1), UUID(int=2), UUID(int=3), UUID(int=4), UUID(int=5)) == own
    claim = queue.claim()
    assert claim.id == own and queue.complete(claim)
    assert queue.claim() is None
    with queue.engine.connect() as c:
        rows = c.execute(
            sa.select(jobs.c.id, jobs.c.status).where(jobs.c.id.in_([first["id"], second["id"]]))
        ).all()
        assert len(rows) == 2 and all(row.status == "PENDING" for row in rows)


def test_same_version_space_and_idempotency_are_unique(queue):
    first = embed(queue)
    with pytest.raises(sa.exc.IntegrityError):
        embed(queue, space=first["space_id"])
    with pytest.raises(sa.exc.IntegrityError):
        embed(queue, key=first["idempotency_id"])
    with queue.engine.connect() as c:
        assert c.scalar(sa.select(sa.func.count()).select_from(jobs)) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"space_id": None},
        {"profile_fingerprint": None},
        {"profile_fingerprint": "short"},
        {"kind": "INGEST"},
        {"kind": "OTHER"},
    ],
)
def test_invalid_profile_binding_fails_without_partial_insert(queue, change):
    with pytest.raises(sa.exc.IntegrityError):
        embed(queue, **change)
    with queue.engine.connect() as c:
        assert c.scalar(sa.select(sa.func.count()).select_from(jobs)) == 0


def test_new_schema_does_not_mutate_frozen_historical_definition():
    assert "space_id" not in historical.c and "profile_fingerprint" not in historical.c
    assert any(c.name == "job_version_kind" for c in historical.constraints)
    old = str(CreateTable(historical).compile(dialect=dialect()))
    new = str(CreateTable(jobs).compile(dialect=dialect()))
    assert "kind = 'INGEST'" in old
    assert "job_embedding_profile" in new
    assert set(jobs.c.keys()) - set(historical.c.keys()) == {"space_id", "profile_fingerprint"}
    assert not {"text", "embedding", "vector", "secret", "prompt", "document_content"} & set(
        jobs.c.keys()
    )
