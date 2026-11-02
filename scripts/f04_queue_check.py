"""Trusted ragdev01 PostgreSQL queue probes; no original documents are enqueued."""

import hashlib
import json
import logging
import multiprocessing as mp
import time
from pathlib import Path
from uuid import uuid4

import sqlalchemy as sa
from f02_common import engine
from sqlalchemy.exc import DBAPIError

from rag_platform.control.identity_models import IdentityBase
from rag_platform.control.migrations import upgrade_control, upgrade_identity, upgrade_ingestion
from rag_platform.control.models import Base
from rag_platform.ingestion.queue import DurableQueue, QueueError
from rag_platform.ingestion.queue_schema import VERSION, jobs

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "f04_queue_probe_0001"
MARKER = "rag-platform/F04/queue-probe/v1"
PHASE = "START"


def fingerprint(c):
    result = {}
    for metadata in (Base.metadata, IdentityBase.metadata):
        for name in metadata.tables:
            rows = c.execute(sa.text('SELECT to_jsonb(t) FROM "' + name + '" t')).scalars()
            result[name] = hashlib.sha256(
                "".join(sorted(json.dumps(r, sort_keys=True) for r in rows)).encode()
            ).hexdigest()
    return result


def probe_engine():
    return engine("migrator").execution_options(schema_translate_map={None: SCHEMA})


def migration():
    e = engine("migrator")
    try:
        with e.connect() as c:
            before = fingerprint(c)
            prior = c.scalar(sa.text("SELECT version_num FROM alembic_version_control"))
            existed = c.scalar(sa.text("SELECT to_regclass('public.job_envelopes') IS NOT NULL"))

        class RollbackProbe(Exception):
            pass

        try:
            with e.begin() as c:
                upgrade_ingestion(c, ROOT)
                upgrade_ingestion(c, ROOT)
                upgrade_identity(c, ROOT)
                upgrade_control(c, ROOT)
                assert (
                    c.scalar(sa.text("SELECT version_num FROM alembic_version_control")) == VERSION
                )
                assert fingerprint(c) == before
                assert c.scalar(
                    sa.text(
                        "SELECT count(*) FROM information_schema.columns "
                        "WHERE table_schema='public' AND table_name='job_envelopes'"
                    )
                ) == len(jobs.c)
                assert not c.scalar(
                    sa.text(
                        "SELECT EXISTS(SELECT FROM information_schema.role_table_grants "
                        "WHERE table_schema='public' AND table_name='job_envelopes' "
                        "AND grantee='PUBLIC')"
                    )
                )
                raise RollbackProbe()
        except RollbackProbe:
            pass
        with e.connect() as c:
            assert fingerprint(c) == before
            assert c.scalar(sa.text("SELECT version_num FROM alembic_version_control")) == prior
            assert (
                c.scalar(sa.text("SELECT to_regclass('public.job_envelopes') IS NOT NULL"))
                == existed
            )
    finally:
        e.dispose()


def prepare():
    global PHASE
    PHASE = "PROBE_SCHEMA"
    bootstrap = engine("bootstrap")
    try:
        with bootstrap.begin() as c:
            found = c.execute(
                sa.text(
                    "SELECT r.rolname,obj_description(n.oid,'pg_namespace') FROM pg_namespace n "
                    "JOIN pg_roles r ON r.oid=n.nspowner WHERE n.nspname=:name"
                ),
                {"name": SCHEMA},
            ).first()
            if found is None:
                c.exec_driver_sql("CREATE SCHEMA " + SCHEMA + " AUTHORIZATION f01_control_migrator")
                c.exec_driver_sql("COMMENT ON SCHEMA " + SCHEMA + " IS '" + MARKER + "'")
            elif tuple(found) != ("f01_control_migrator", MARKER):
                raise RuntimeError("OWNERSHIP")
            PHASE = "PROBE_SCHEMA_GRANT"
            c.exec_driver_sql("GRANT USAGE ON SCHEMA " + SCHEMA + " TO f02_identity_app")
    finally:
        bootstrap.dispose()
    e = probe_engine()
    with e.begin() as c:
        PHASE = "PROBE_TABLES"
        for name in ("tenants", "users"):
            c.exec_driver_sql(
                "CREATE TABLE IF NOT EXISTS " + SCHEMA + "." + name + "(id uuid PRIMARY KEY)"
            )
        PHASE = "PROBE_JOBS"
        jobs.create(c, checkfirst=True)
        PHASE = "PROBE_SEED"
        tenant, actor = uuid4(), uuid4()
        c.execute(sa.text("INSERT INTO " + SCHEMA + ".tenants VALUES (:id)"), {"id": tenant})
        c.execute(sa.text("INSERT INTO " + SCHEMA + ".users VALUES (:id)"), {"id": actor})
    e.dispose()
    return tenant, actor


def denied():
    e = engine()
    try:
        with e.begin() as c:
            try:
                with c.begin_nested():
                    c.exec_driver_sql("SELECT * FROM " + SCHEMA + ".job_envelopes")
            except DBAPIError as error:
                assert getattr(error.orig, "sqlstate", None) == "42501"
            else:
                raise RuntimeError("UNEXPECTED_GRANT")
    finally:
        e.dispose()


def child(tenant, event, output, inbox, action="claim"):
    logging.disable(logging.CRITICAL)
    e = probe_engine()
    try:
        with e.connect() as c:
            pid = c.scalar(sa.text("SELECT pg_backend_pid()"))
        output.put(("READY", pid))
        if not event.wait(30):
            raise RuntimeError("START_TIMEOUT")
        q = DurableQueue(e, tenant_scope=(tenant,), lease_seconds=10)
        claim = inbox.get(timeout=10) if action != "claim" else None
        value = (
            q.claim()
            if action == "claim"
            else (q.complete(claim) if action == "complete" else q.heartbeat(claim))
        )
        output.put(("RESULT", value))
    except Exception:
        output.put(("ERROR", None))
    finally:
        e.dispose()


def spawn(tenant, action="claim"):
    ctx = mp.get_context("spawn")
    event, output, inbox = ctx.Event(), ctx.Queue(), ctx.Queue()
    p = ctx.Process(target=child, args=(tenant, event, output, inbox, action))
    p.start()
    tag, pid = output.get(timeout=30)
    assert tag == "READY"
    return p, event, output, pid, inbox


def finish(item):
    p, _event, output, _pid, inbox = item
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
        inbox.close()
        p.close()


def wait_expired(e, claim):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        with e.connect() as c:
            if c.scalar(
                sa.select(jobs.c.lease_until <= sa.func.clock_timestamp()).where(
                    jobs.c.id == claim.id
                )
            ):
                return
        time.sleep(0.05)
    raise RuntimeError("EXPIRY_TIMEOUT")


def run():
    global PHASE
    PHASE = "MIGRATION"
    migration()
    print("PASS T002: migración control aditiva/repetible; F01/F02 y rollback DDL conservados.")
    PHASE = "PREPARE"
    tenant, actor = prepare()
    PHASE = "PROBE_DENIAL"
    denied()
    e = probe_engine()
    q = DurableQueue(e, tenant_scope=(tenant,), lease_seconds=10, max_attempts=2)

    def add():
        values = (tenant, actor, uuid4(), uuid4(), uuid4())
        first = q.enqueue(*values)
        assert q.enqueue(*values) == first
        try:
            q.enqueue(*values[:-1], uuid4())
        except QueueError as err:
            assert err.code == "IDEMPOTENCY_CONFLICT"
        else:
            raise RuntimeError("IDEMPOTENCY_NOT_ENFORCED")
        return first

    try:
        PHASE = "TWO_PROCESSES"
        first = add()
        children = [spawn(tenant), spawn(tenant)]
        for item in children:
            item[1].set()
        values = [finish(item) for item in children]
        claims = [value for value in values if value is not None]
        assert len(claims) == 1 and claims[0].id == first
        assert q.complete(claims[0])
        PHASE = "SKIP_LOCKED"
        first, second = add(), add()
        with e.begin() as c:
            c.execute(sa.select(jobs).where(jobs.c.id == first).with_for_update()).first()
            item = spawn(tenant)
            item[1].set()
            value = finish(item)
            assert value is not None and value.id == second
            assert q.complete(value)
        value = q.claim()
        assert value.id == first and q.complete(value)
        print(
            "PASS T002: dos procesos compiten sin duplicado; SKIP LOCKED evita bloquear otro job."
        )
        PHASE = "CRASH_EXPIRY"
        add()
        item = spawn(tenant)
        item[1].set()
        old = finish(item)  # Process exits without acknowledgement.
        wait_expired(e, old)
        fresh = q.claim()
        assert fresh.id == old.id and fresh.attempt == 2 and fresh.token != old.token
        assert not q.complete(old) and not q.heartbeat(old)
        assert not q.fail(old, "PROCESSING_FAILED", retryable=True)
        assert q.complete(fresh)
        PHASE = "BACKOFF"
        add()
        old = q.claim()
        assert q.fail(old, "STOP_REQUESTED", retryable=True)
        assert q.claim() is None
        time.sleep(1.1)
        fresh = q.claim()
        assert fresh.attempt == 2
        assert q.fail(fresh, "DEPENDENCY_UNAVAILABLE", retryable=True)
        assert q.claim() is None
        PHASE = "EXHAUSTION"
        short = DurableQueue(e, tenant_scope=(tenant,), lease_seconds=1, max_attempts=2)
        # enqueue carries this queue's bounded max_attempts into the row.
        short.enqueue(tenant, actor, uuid4(), uuid4(), uuid4())
        old = short.claim()
        wait_expired(e, old)
        fresh = short.claim()
        wait_expired(e, fresh)
        assert short.claim() is None
        assert not short.complete(old) and not short.complete(fresh)
        print("PASS T002: caída sin ack, caducidad real, fencing, backoff y agotamiento terminal.")
        PHASE = "LOCK_EXPIRY"
        for action in ("complete", "heartbeat"):
            add()
            item = spawn(tenant, action)
            value = DurableQueue(e, tenant_scope=(tenant,), lease_seconds=3).claim()
            item[4].put(value)
            with e.begin() as c:
                c.execute(sa.select(jobs).where(jobs.c.id == value.id).with_for_update()).first()
                item[1].set()
                deadline = time.monotonic() + 3
                blocked = False
                while time.monotonic() < deadline:
                    with e.connect() as observer:
                        blocked = observer.scalar(
                            sa.text(
                                "SELECT wait_event_type='Lock' FROM pg_stat_activity WHERE pid=:pid"
                            ),
                            {"pid": item[3]},
                        )
                    if blocked:
                        break
                    time.sleep(0.025)
                PHASE = "LOCK_" + action.upper() + "_WAIT"
                assert blocked
                wait_expired(e, value)
            PHASE = "LOCK_" + action.upper() + "_LATE"
            assert finish(item) is False
            fresh = q.claim()
            assert fresh.id == value.id and q.complete(fresh)
        assert q.claim() is None
        with e.connect() as c:
            assert (
                c.scalar(
                    sa.select(sa.func.count())
                    .select_from(jobs)
                    .where(
                        jobs.c.tenant_id == tenant,
                        jobs.c.status.not_in(("SUCCEEDED", "FAILED", "CANCELLED")),
                    )
                )
                == 0
            )
        print(
            "PASS T002: ack/heartbeat que esperan lock no reviven lease vencido; errores cerrados."
        )
        PHASE = "FINAL"
        migration()
        print("PASS T002: esquema de prueba solo IDs; app sin lectura; control público intacto.")
        print("T002: cola probada, sin worker ni ingesta activa; sin AC-F04 completo todavía.")
    finally:
        e.dispose()


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    try:
        run()
    except Exception as error:
        state = getattr(getattr(error, "orig", None), "sqlstate", None)
        if state is not None and len(state) == 5 and state.isalnum():
            print("F04-T002 DIAGNOSTIC SQLSTATE " + state)
        print("F04-T002 ERROR_CLASS " + type(error).__name__)
        print("F04-T002 " + PHASE + ": operación detenida; recursos conservados.")
        raise SystemExit(1) from None
