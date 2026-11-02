"""F05 control queue SQL proof. Entire transaction and synthetic envelopes are rolled back."""

import json
import logging
import re
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid4

import sqlalchemy as sa
from f02_common import engine
from f04_schema_check import denied, fingerprint

from rag_platform.control.identity_models import IdentityBase, User
from rag_platform.control.models import Base
from rag_platform.embeddings.control_migrations import upgrade_embedding_queue
from rag_platform.embeddings.queue import EmbeddingQueue
from rag_platform.embeddings.queue_schema_f05_0007 import VERSION, jobs
from rag_platform.ingestion.claims import locked_claim
from rag_platform.ingestion.queue import DurableQueue, QueueError
from rag_platform.ingestion.queue_schema_f04_0006 import jobs as historical

ROOT = Path(__file__).resolve().parents[1]
PHASE = "START"


class TransactionEngine:
    def __init__(self, connection):
        self.connection = connection

    @contextmanager
    def begin(self):
        with self.connection.begin_nested():
            yield self.connection


def prove(c):
    global PHASE
    table_snapshot = fingerprint(
        c, list(Base.metadata.tables.values()) + list(IdentityBase.metadata.tables.values())
    )
    old_jobs = fingerprint(c, [historical])
    prior = c.scalar(sa.text("SELECT version_num FROM public.alembic_version_control"))
    assert prior == "f04_control_0006"
    PHASE = "DDL_ROLLBACK"
    denied(c, lambda: (upgrade_embedding_queue(c, ROOT), c.exec_driver_sql("SELECT 1/0")), "22012")
    assert c.scalar(sa.text("SELECT version_num FROM public.alembic_version_control")) == prior
    assert "space_id" not in {x["name"] for x in sa.inspect(c).get_columns("job_envelopes")}
    PHASE = "UPGRADE_REPEAT"
    assert upgrade_embedding_queue(c, ROOT) == VERSION
    assert upgrade_embedding_queue(c, ROOT) == VERSION
    assert fingerprint(c, [historical]) == old_jobs
    scope = json.loads((ROOT / "ops/f03/application-scope.json").read_text())["fixtures"]
    tenant = UUID(scope[0]["tenant"])
    actor = c.scalar(sa.select(User.id).where(User.state == "ACTIVE").order_by(User.id).limit(1))
    assert actor is not None
    version, document = uuid4(), uuid4()
    ids = []

    class ScopedIngestQueue(DurableQueue):
        def _scope(self):
            return sa.and_(super()._scope(), historical.c.id.in_(ids))

    queue = ScopedIngestQueue(TransactionEngine(c), tenant_scope=(tenant,))
    original = queue.enqueue(tenant, actor, document, version, uuid4())
    ids.append(original)
    value = dict(
        id=uuid4(),
        tenant_id=tenant,
        actor_id=actor,
        document_id=document,
        version_id=version,
        idempotency_id=uuid4(),
        kind="EMBED",
        space_id=uuid4(),
        profile_fingerprint="a" * 64,
        max_attempts=3,
        available_at=sa.func.clock_timestamp(),
        created_at=sa.func.clock_timestamp(),
        updated_at=sa.func.clock_timestamp(),
    )
    PHASE = "PROFILE_NEGATIVES"
    for changes in (
        {"space_id": None},
        {"profile_fingerprint": None},
        {"profile_fingerprint": "g" * 64},
        {"space_id": UUID(int=0)},
        {"kind": "INGEST"},
        {"kind": "OTHER"},
    ):
        denied(c, lambda changes=changes: c.execute(jobs.insert().values(**(value | changes))))
    PHASE = "UNIQUE_BY_SPACE"
    c.execute(jobs.insert().values(**value))
    ids.append(value["id"])
    denied(
        c,
        lambda: c.execute(
            jobs.insert().values(**(value | {"id": uuid4(), "idempotency_id": uuid4()}))
        ),
        "23505",
    )
    second = value | {
        "id": uuid4(),
        "space_id": uuid4(),
        "idempotency_id": uuid4(),
        "profile_fingerprint": "b" * 64,
    }
    c.execute(jobs.insert().values(**second))
    ids.append(second["id"])
    PHASE = "INGEST_KIND_FENCE"
    claim = queue.claim()
    assert claim.id == original and queue.complete(claim)
    assert queue.claim() is None
    result = c.execute(
        sa.select(jobs.c.id, jobs.c.status).where(jobs.c.id.in_([value["id"], second["id"]]))
    ).all()
    assert len(result) == 2 and all(row.status == "PENDING" for row in result)
    PHASE = "EMBED_LEASE_FENCE"

    class ScopedEmbeddingQueue(EmbeddingQueue):
        def _scope(self):
            return sa.and_(super()._scope(), jobs.c.id.in_(ids))

    embedding = ScopedEmbeddingQueue(TransactionEngine(c), tenant_scope=(tenant,))
    embedded = embedding.claim()
    assert embedded is not None and embedded.id in ids
    assert embedding.heartbeat(embedded)
    assert not embedding.complete(replace(embedded, space_id=uuid4()))
    assert not embedding.complete(replace(embedded, profile_fingerprint="c" * 64))
    with locked_claim(embedding, embedded) as guard:
        guard.check()
        guard.complete()
    assert not embedding.complete(embedded)
    another = embedding.claim()
    assert another is not None and another.id != embedded.id
    assert embedding.fail(another, "DIMENSION_MISMATCH", retryable=True)
    assert embedding.claim() is None
    PHASE = "EMBED_REPLAY_RECLAIM"
    key, space = uuid4(), uuid4()
    envelope = embedding.enqueue(tenant, actor, document, version, key, space, "d" * 64)
    ids.append(envelope)
    assert embedding.enqueue(tenant, actor, document, version, key, space, "d" * 64) == envelope
    try:
        embedding.enqueue(tenant, actor, document, version, key, space, "e" * 64)
    except QueueError as error:
        assert error.code == "IDEMPOTENCY_CONFLICT"
    else:
        raise AssertionError("EXPECTED_IDEMPOTENCY_CONFLICT")
    old = embedding.claim()
    c.execute(
        jobs.update()
        .where(jobs.c.id == envelope)
        .values(lease_until=sa.func.clock_timestamp() - sa.text("interval '1 second'"))
    )
    fresh = embedding.claim()
    assert fresh.id == old.id and fresh.token != old.token and fresh.attempt == 2
    assert not embedding.heartbeat(old) and not embedding.complete(old)
    assert embedding.fail(fresh, "DEPENDENCY_UNAVAILABLE", retryable=True)
    assert embedding.claim() is None
    c.execute(
        jobs.update()
        .where(jobs.c.id == envelope)
        .values(available_at=sa.func.clock_timestamp() - sa.text("interval '1 second'"))
    )
    assert embedding.complete(embedding.claim())
    PHASE = "APP_GRANTS"
    for action in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"):
        granted = c.scalar(
            sa.text(
                "SELECT has_table_privilege('f02_identity_app','public.job_envelopes',:action)"
            ),
            {"action": action},
        )
        assert granted == (action in ("SELECT", "INSERT", "UPDATE"))
    assert not c.scalar(
        sa.text("SELECT has_schema_privilege('f02_identity_app','public','CREATE')")
    )
    return table_snapshot, old_jobs, prior


def run():
    global PHASE
    control = engine("migrator")
    try:
        with control.connect() as c:
            transaction = c.begin()
            try:
                snapshot, old_jobs, prior = prove(c)
            finally:
                transaction.rollback()
            PHASE = "FINAL_ROLLBACK"
            assert (
                c.scalar(sa.text("SELECT version_num FROM public.alembic_version_control")) == prior
            )
            assert "space_id" not in {x["name"] for x in sa.inspect(c).get_columns("job_envelopes")}
            assert fingerprint(c, [historical]) == old_jobs
            assert (
                fingerprint(
                    c,
                    list(Base.metadata.tables.values())
                    + list(IdentityBase.metadata.tables.values()),
                )
                == snapshot
            )
        print("PASS F05 CONTROL: DDL/repeat, uniqueness; INGEST/EMBED fences, leases and replay.")
        print(
            "PASS F05 CONTROL: catalog verifies app grants limited; "
            "rollback preserves all history/identity/catalog."
        )
        print("F05 CONTROL: no persistent queue upgrade, real jobs, tenants or content.")
    finally:
        control.dispose()


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    try:
        run()
    except Exception as error:
        state = getattr(getattr(error, "orig", error), "sqlstate", None)
        code = (
            "SQLSTATE_" + state
            if isinstance(state, str) and re.fullmatch("[A-Z0-9]{5}", state)
            else "REFUSED"
        )
        print(
            "F05-CONTROL "
            + PHASE
            + " "
            + type(error).__name__
            + " "
            + code
            + "; rollback/resources retained."
        )
        raise SystemExit(1) from None
