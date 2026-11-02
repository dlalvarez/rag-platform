"""T005 journal/relay SQL probes: tenant writes rollback; QA control IDs retained."""

import logging
from dataclasses import replace
from uuid import uuid4

import f04_queue_check as queue_probe
import f04_schema_check as schema_probe
import sqlalchemy as sa

from rag_platform.ingestion import journal
from rag_platform.ingestion.extraction import ChunkConfig
from rag_platform.ingestion.queue import DurableQueue
from rag_platform.ingestion.queue_schema import jobs
from rag_platform.ingestion.schema import audit, documents, intents, versions

PHASE = "START"
QUEUE = None
TENANT = None


def rejected(operation, expected):
    try:
        operation()
    except journal.IngestionError as error:
        assert error.code == expected
    else:
        raise RuntimeError("UNEXPECTED_INTENT_SUCCESS")


def journal_probes(c, names):
    global PHASE
    PHASE = "JOURNAL"

    def request(f):
        trace = uuid4()
        first = journal.request(c, f["actor"], f["repo"], f["doc"], trace)
        for _ in range(3):
            assert journal.request(c, f["actor"], f["repo"], f["doc"], uuid4()) == first
        assert (
            c.scalar(
                sa.select(sa.func.count())
                .select_from(versions)
                .where(versions.c.document_id == f["doc"], versions.c.kind == "PROCESSED")
            )
            == 1
        )
        assert (
            c.scalar(
                sa.select(sa.func.count())
                .select_from(intents)
                .where(intents.c.document_id == f["doc"])
            )
            == 1
        )
        assert (
            c.scalar(
                sa.select(sa.func.count())
                .select_from(audit)
                .where(
                    audit.c.target_id == first.version_id, audit.c.action == "INGESTION_REQUESTED"
                )
            )
            == 1
        )
        assert journal.load(c, first.id) == first
        assert first in journal.pending(c, limit=100)
        second = journal.request(c, f["actor"], f["repo"], f["doc"], uuid4(), ChunkConfig(128, 32))
        assert second != first and second.version_id != first.version_id
        actor = uuid4()
        c.execute(
            sa.insert(journal.acl).values(
                repository_id=f["repo"], principal_id=actor, role="editor"
            )
        )
        rejected(
            lambda: journal.request(c, actor, f["repo"], f["doc"], uuid4()), "IDEMPOTENCY_CONFLICT"
        )
        c.execute(
            sa.update(documents)
            .where(documents.c.id == f["doc"])
            .values(
                state="TOMBSTONED",
                tombstoned_at=sa.func.clock_timestamp(),
                tombstoned_by=f["actor"],
            )
        )
        rejected(lambda: journal.request(c, f["actor"], f["repo"], f["doc"], uuid4()), "TOMBSTONED")

    schema_probe.frame(c, request)
    PHASE = "RELAY_ACK_LOST"

    def relay(f):
        first = journal.request(c, f["actor"], f["repo"], f["doc"], uuid4())
        with QUEUE.engine.begin() as control:
            control.execute(
                sa.text("INSERT INTO " + queue_probe.SCHEMA + ".users VALUES(:id)"),
                {"id": f["actor"]},
            )
        job = journal.enqueue(QUEUE, TENANT, first)
        # Real control commit, intentionally do not journal its first acknowledgement.
        assert journal.enqueue(QUEUE, TENANT, first) == job
        assert journal.dispatched(c, first, job) is True
        assert journal.dispatched(c, first, job) is False
        rejected(lambda: journal.dispatched(c, first, uuid4()), "IDEMPOTENCY_CONFLICT")
        rejected(
            lambda: journal.dispatched(c, replace(first, version_id=uuid4()), job),
            "IDEMPOTENCY_CONFLICT",
        )
        with QUEUE.engine.connect() as control:
            row = control.execute(sa.select(jobs).where(jobs.c.id == job)).mappings().one()
            assert row["idempotency_id"] == first.id and row["actor_id"] == f["actor"]
            assert row["document_id"] == first.document_id and row["version_id"] == first.version_id
            assert (
                control.scalar(
                    sa.select(sa.func.count())
                    .select_from(jobs)
                    .where(jobs.c.tenant_id == TENANT, jobs.c.idempotency_id == first.id)
                )
                == 1
            )
        claim = QUEUE.claim()
        assert claim.id == job and QUEUE.fail(claim, "STOP_REQUESTED")
        assert first not in journal.pending(c, limit=100)

    schema_probe.frame(c, relay)
    PHASE = "ATOMIC_ROLLBACK"
    count = c.scalar(sa.select(sa.func.count()).select_from(intents))

    def abandon(f):
        journal.request(c, f["actor"], f["repo"], f["doc"], uuid4())

    schema_probe.frame(c, abandon)
    assert c.scalar(sa.select(sa.func.count()).select_from(intents)) == count
    print("PASS T005 JOURNAL: versión/intención/auditoría atómicas; repetición y config distinta.")
    print("PASS T005 RELAY: ack perdido recupera un job; actor/baja/identidad protegidos.")


def run():
    global QUEUE, TENANT, PHASE
    queue_probe.SCHEMA = "f04_intent_probe_0001"
    queue_probe.MARKER = "rag-platform/F04/intent-probe/v1"
    PHASE = "QA_CONTROL"
    TENANT, _actor = queue_probe.prepare()
    e = queue_probe.probe_engine()
    QUEUE = DurableQueue(e, tenant_scope=(TENANT,))
    original = schema_probe.probes

    def combined(c, names):
        original(c, names)
        journal_probes(c, names)

    schema_probe.probes = combined
    try:
        schema_probe.run()
        assert QUEUE.claim() is None
        print(
            "T005: journal/relay probados en cuatro fixtures; sin worker ni activación persistente."
        )
    finally:
        schema_probe.probes = original
        e.dispose()


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    try:
        run()
    except Exception as error:
        state = getattr(getattr(error, "orig", None), "sqlstate", None)
        code = (
            "SQLSTATE_" + state
            if isinstance(state, str) and len(state) == 5 and state.isalnum()
            else "REFUSED"
        )
        print(
            "F04-T005 " + PHASE + "/" + schema_probe.PHASE + " " + type(error).__name__ + " " + code
        )
        raise SystemExit(1) from None
