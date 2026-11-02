"""Real PostgreSQL commit-fence/processing probes; all tenant changes roll back."""

import logging
import multiprocessing as mp
import time
from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

import f04_intent_check as intent_probe
import f04_queue_check as queue_probe
import f04_schema_check as schema_probe
import sqlalchemy as sa

from rag_platform.control.identity_admin import IdentityAdministration
from rag_platform.ingestion import journal, processing
from rag_platform.ingestion.claims import ClaimExpired, locked_claim
from rag_platform.ingestion.extraction import ChunkConfig
from rag_platform.ingestion.queue import DurableQueue
from rag_platform.ingestion.queue_schema import jobs
from rag_platform.ingestion.schema import blocks, chunks, documents, versions
from rag_platform.ingestion.worker_policy import (
    StopRequested,
    administrative_locks,
    before_commit,
)
from rag_platform.provisioning.saga import SagaError, postgres_lock

PHASE = "START"


def failed(operation, error_type):
    try:
        operation()
    except error_type:
        return
    raise RuntimeError("UNEXPECTED_PROBE_SUCCESS")


def competitor(schema, tenant, event, output):
    logging.disable(logging.CRITICAL)
    queue_probe.SCHEMA = schema
    e = queue_probe.probe_engine()
    try:
        output.put(("READY", None))
        assert event.wait(20)
        q = DurableQueue(e, tenant_scope=(tenant,), lease_seconds=1)
        claim = q.claim()
        output.put(("RESULT", None if claim is None else claim.id))
    except Exception:
        output.put(("ERROR", None))
    finally:
        e.dispose()


def start_competitor():
    ctx = mp.get_context("spawn")
    event, output = ctx.Event(), ctx.Queue()
    p = ctx.Process(
        target=competitor, args=(queue_probe.SCHEMA, intent_probe.TENANT, event, output)
    )
    p.start()
    assert output.get(timeout=20)[0] == "READY"
    return p, event, output


def finish_competitor(item):
    p, _event, output = item
    try:
        tag, value = output.get(timeout=15)
        p.join(5)
        assert tag == "RESULT" and p.exitcode == 0
        return value
    finally:
        if p.is_alive():
            p.terminate()
            p.join(5)
        output.close()
        p.close()


def prepare(c, f, *, queue=None):
    q = intent_probe.QUEUE if queue is None else queue
    plan = journal.request(c, f["actor"], f["repo"], f["doc"], uuid4(), ChunkConfig(128, 32))
    with q.engine.begin() as control:
        control.execute(
            sa.text("INSERT INTO " + queue_probe.SCHEMA + ".users VALUES(:id)"), {"id": f["actor"]}
        )
    job = journal.enqueue(q, intent_probe.TENANT, plan)
    journal.dispatched(c, plan, job)
    claim = q.claim()
    assert claim.id == job
    return q, plan, claim


def empty(c, plan):
    for table in (blocks, chunks):
        assert (
            c.scalar(
                sa.select(sa.func.count())
                .select_from(table)
                .where(table.c.version_id == plan.version_id)
            )
            == 0
        )


def processing_probes(c, names):
    global PHASE

    q = intent_probe.QUEUE
    PHASE = "ADMINISTRATIVE_LOCK_PROTOCOL"
    with q.engine.begin() as control:
        administrative_locks(control, intent_probe.TENANT)
        admin = IdentityAdministration(q.engine, uuid4(), uuid4())
        for operation in (
            admin._global_lock,
            lambda other: admin._tenant_lock(other, intent_probe.TENANT),
        ):
            try:
                with q.engine.begin() as other:
                    other.exec_driver_sql("SET LOCAL lock_timeout='100ms'")
                    operation(other)
            except sa.exc.DBAPIError as error:
                assert getattr(error.orig, "sqlstate", None) == "55P03"
            else:
                raise RuntimeError("ADMIN_LOCK_NOT_SERIALIZED")
        try:
            with postgres_lock(q.engine, "f01-saga-tenant:", intent_probe.TENANT):
                raise RuntimeError("MIGRATION_NOT_SERIALIZED")
        except SagaError as error:
            assert error.code == "LOCK_BUSY"
    with postgres_lock(q.engine, "f01-saga-tenant:", intent_probe.TENANT):
        pass
    print(
        "PASS T005 POLICY: locks compartidos bloquean revocación/migración del protocolo vigente."
    )

    def atomic(f):
        q, plan, claim = prepare(c, f)
        with locked_claim(q, claim) as guard:
            processing.start(c, guard)
            bad = replace(schema_probe.parsed(), text="F04_SQL_PRIVATE_CANARY wrong hash")
            try:
                with c.begin_nested():
                    processing.complete(c, guard, bad)
            except sa.exc.DBAPIError as error:
                assert getattr(error.orig, "sqlstate", None) == "23514"
            else:
                raise RuntimeError("INCOMPLETE_RESULT_ACCEPTED")
            empty(c, plan)
            assert (
                c.scalar(sa.select(versions.c.state).where(versions.c.id == plan.version_id))
                == "EXTRACTING"
            )
            assert processing.complete(c, guard, schema_probe.parsed()) is True
            count = c.scalar(
                sa.select(sa.func.count())
                .select_from(chunks)
                .where(chunks.c.version_id == plan.version_id)
            )
            assert count > 0
            assert processing.complete(c, guard, schema_probe.parsed()) is False
            assert (
                c.scalar(
                    sa.select(sa.func.count())
                    .select_from(chunks)
                    .where(chunks.c.version_id == plan.version_id)
                )
                == count
            )
            guard.complete()
        failed(guard.check, ClaimExpired)

    PHASE = "ATOMIC"
    schema_probe.frame(c, atomic)

    def retry(f):
        q, plan, claim = prepare(c, f)
        with locked_claim(q, claim) as guard:
            processing.start(c, guard)
            assert (
                processing.failure(c, guard, "DEPENDENCY_UNAVAILABLE", retryable=True)
                == "FAILED_RETRYABLE"
            )
        empty(c, plan)
        assert q.fail(claim, "DEPENDENCY_UNAVAILABLE", retryable=True)
        with q.engine.begin() as control:
            control.execute(
                sa.update(jobs)
                .where(jobs.c.id == claim.id)
                .values(available_at=sa.func.clock_timestamp())
            )
        fresh = q.claim()
        assert fresh.attempt == 2 and fresh.token != claim.token
        failed(lambda: _old_guard(q, claim), ClaimExpired)
        with locked_claim(q, fresh) as guard:
            processing.start(c, guard)
            assert processing.complete(c, guard, schema_probe.parsed())
            guard.complete()

    PHASE = "RETRY"
    schema_probe.frame(c, retry)

    def stop(f):
        q, plan, claim = prepare(c, f)
        with locked_claim(q, claim) as guard:
            processing.start(c, guard)
            try:
                with c.begin_nested():
                    processing.complete(c, guard, schema_probe.parsed())
                    before_commit(guard, SimpleNamespace(expires_at=time.time() + 30), lambda: True)
            except StopRequested:
                pass
            else:
                raise RuntimeError("STOP_IGNORED")
            empty(c, plan)
        assert q.fail(claim, "STOP_REQUESTED")

    PHASE = "STOP"
    schema_probe.frame(c, stop)

    def expired(f):
        q = DurableQueue(
            intent_probe.QUEUE.engine, tenant_scope=(intent_probe.TENANT,), lease_seconds=1
        )
        item = start_competitor()  # Ready before starting the short lease.
        try:
            q, plan, claim = prepare(c, f, queue=q)
            with locked_claim(q, claim) as guard:
                processing.start(c, guard)
                queue_probe.wait_expired(q.engine, claim)
                failed(guard.check, ClaimExpired)
                item[1].set()
                assert finish_competitor(item) is None
                item = None
            fresh = q.claim()
            assert fresh.attempt == 2 and fresh.token != claim.token
            with locked_claim(q, fresh) as guard:
                processing.start(c, guard)
                assert processing.complete(c, guard, schema_probe.parsed())
                guard.complete()
        finally:
            if item is not None:
                item[1].set()
                finish_competitor(item)

    PHASE = "EXPIRED_LOCK_TWO_PROCESSES"
    schema_probe.frame(c, expired)

    def tombstone(f):
        q, plan, claim = prepare(c, f)
        with locked_claim(q, claim) as guard:
            processing.start(c, guard)
            c.execute(
                sa.update(documents)
                .where(documents.c.id == f["doc"])
                .values(
                    state="TOMBSTONED",
                    tombstoned_at=sa.func.clock_timestamp(),
                    tombstoned_by=f["actor"],
                )
            )
            intent_probe.rejected(
                lambda: processing.complete(c, guard, schema_probe.parsed()), "TOMBSTONED"
            )
            empty(c, plan)
        assert q.fail(claim, "TOMBSTONED")

    PHASE = "TOMBSTONE"
    schema_probe.frame(c, tombstone)

    def late_ack(f):
        q = intent_probe.QUEUE
        plan = journal.request(c, f["actor"], f["repo"], f["doc"], uuid4())
        with q.engine.begin() as control:
            control.execute(
                sa.text("INSERT INTO " + queue_probe.SCHEMA + ".users VALUES(:id)"),
                {"id": f["actor"]},
            )
        job = journal.enqueue(q, intent_probe.TENANT, plan)
        c.execute(
            sa.update(documents)
            .where(documents.c.id == f["doc"])
            .values(
                state="TOMBSTONED",
                tombstoned_at=sa.func.clock_timestamp(),
                tombstoned_by=f["actor"],
            )
        )
        c.execute(
            sa.delete(journal.acl).where(
                journal.acl.c.repository_id == f["repo"], journal.acl.c.principal_id == f["actor"]
            )
        )
        assert journal.dispatched(c, plan, job) is True
        assert journal.dispatched(c, plan, job) is False
        intent_probe.rejected(
            lambda: journal.request(c, f["actor"], f["repo"], f["doc"], uuid4()),
            "AUTHORIZATION_CHANGED",
        )
        claim = q.claim()
        assert claim.id == job and q.fail(claim, "AUTHORIZATION_CHANGED")

    PHASE = "LATE_DISPATCH_ACK"
    schema_probe.frame(c, late_ack)
    print("PASS T005 FENCE: dos procesos; lock impide takeover; lease vencido no confirma.")
    print("PASS T005 COMMIT: fallo revierte chunks; repetición sin duplicados; retry recupera.")
    print("PASS T005 STOP/BAJA: sin resultado tardío; ack de IDs no concede acceso.")


def _old_guard(q, claim):
    with locked_claim(q, claim):
        raise RuntimeError("OLD_CLAIM_ACCEPTED")


def run():
    original = intent_probe.journal_probes

    def combined(c, names):
        original(c, names)
        processing_probes(c, names)

    intent_probe.journal_probes = combined
    try:
        intent_probe.run()
        print(
            "T005: componentes SQL con rollback; sin worker S3/global/runtime acreditado todavía."
        )
    finally:
        intent_probe.journal_probes = original


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
            "F04-T005 FENCING/"
            + PHASE
            + "/"
            + schema_probe.PHASE
            + " "
            + type(error).__name__
            + " "
            + code
        )
        raise SystemExit(1) from None
