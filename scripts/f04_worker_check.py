"""Limited real worker QA. Mounted script/manifest only; no daily/admin identity."""

import argparse
import hashlib
import json
import logging
import os
import signal
import time
from contextlib import contextmanager
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4, uuid5

import sqlalchemy as sa

from rag_platform.identity_api import private_file
from rag_platform.ingestion import journal
from rag_platform.ingestion.extraction import ChunkConfig
from rag_platform.ingestion.logging_setup import SETTINGS
from rag_platform.ingestion.queue import DurableQueue
from rag_platform.ingestion.queue_schema import jobs
from rag_platform.ingestion.runtime import Runtime
from rag_platform.ingestion.schema import blocks, chunks, documents, versions
from rag_platform.ingestion.worker import Worker
from rag_platform.providers.secrets import Credential
from rag_platform.provisioning.postgres import Target
from rag_platform.tenancy.resolver import AdministrativeTenant, control_engine

CA = Path("/run/f01-ca.crt")
PHASE = "START"
STOP, RELEASE = Event(), Event()


def configuration(item):
    return ChunkConfig(*item.get("configuration", (1024, 128)))


def version(item):
    return uuid5(
        UUID(item["original"]), "F04/processing/v1:" + configuration(item).fingerprint(item["mime"])
    )


@contextmanager
def tenant_connection(runtime, fixture, *, user="alice", action="read"):
    trace = uuid4()
    actor = UUID(MANIFEST["actors"][user])
    context = runtime.authority.authorize(actor, UUID(fixture["tenant"]), trace)
    runtime.repositories.require(context, trace, UUID(fixture["repository"]), action)
    with runtime.repositories.connections.connection(context, trace) as c:
        yield c


def job(queue, fixture, item):
    with queue.engine.connect() as c:
        return (
            c.execute(
                sa.select(jobs).where(
                    jobs.c.tenant_id == UUID(fixture["tenant"]),
                    jobs.c.version_id == version(item),
                    jobs.c.document_id == UUID(item["document"]),
                )
            )
            .mappings()
            .one_or_none()
        )


def local(runtime, fixture, item):
    with tenant_connection(runtime, fixture) as c:
        v = (
            c.execute(
                sa.select(versions).where(
                    versions.c.id == version(item),
                    versions.c.document_id == UUID(item["document"]),
                    versions.c.repository_id == UUID(fixture["repository"]),
                )
            )
            .mappings()
            .one()
        )
        count = c.scalar(
            sa.select(sa.func.count())
            .select_from(chunks)
            .where(chunks.c.version_id == version(item))
        )
        doc = c.execute(sa.select(documents).where(documents.c.id == UUID(item["document"]))).one()
        return dict(v), count, doc.state


def verify(runtime, queue, fixture, item, *, ready=True):
    row = job(queue, fixture, item)
    assert row is not None
    v, count, doc_state = local(runtime, fixture, item)
    assert v["original_version_id"] == UUID(item["original"])
    assert v["content_hash"] == item["sha256"] and v["byte_size"] == item["byte_size"]
    assert v["blob_key"] is None and v["kind"] == "PROCESSED"
    config = configuration(item)
    assert (v["chunk_size"], v["chunk_overlap"]) == (config.size, config.overlap)
    assert v["config_hash"] == config.fingerprint(item["mime"])
    if not ready:
        assert v["state"] != "READY_FOR_EMBEDDING" and count == 0
        return v, row, doc_state
    assert row["status"] == "SUCCEEDED" and v["state"] == "READY_FOR_EMBEDDING" and count > 0
    assert doc_state == "RECEIVED" and v["error_code"] == "NONE"
    with tenant_connection(runtime, fixture) as c:
        b = (
            c.execute(
                sa.select(blocks)
                .where(blocks.c.version_id == version(item))
                .order_by(blocks.c.ordinal)
            )
            .mappings()
            .all()
        )
        emitted = (
            c.execute(
                sa.select(chunks)
                .where(chunks.c.version_id == version(item))
                .order_by(chunks.c.ordinal)
            )
            .mappings()
            .all()
        )
        text = "\n".join(x["text"] for x in b)
        assert v["normalized_hash"] == hashlib.sha256(text.encode()).hexdigest()
        assert v["character_count"] == len(text) and v["block_count"] == len(b)
        assert v["chunk_count"] == len(emitted) == count
        for ordinal, piece in enumerate(emitted):
            assert (
                piece["ordinal"] == ordinal
                and piece["text"] == text[piece["start_offset"] : piece["end_offset"]]
            )
            assert piece["content_hash"] == hashlib.sha256(piece["text"].encode()).hexdigest()
            assert piece["document_id"] == UUID(item["document"])
            assert piece["repository_id"] == UUID(fixture["repository"])
            assert piece["page"] == b[piece["block_ordinal"]]["page"]
        if item["mime"] == "application/pdf":
            assert v["page_count"] == 2 and [x["page"] for x in b] == [1, 2]
            assert "SELECT valor FROM tabla;" in text
        else:
            assert v["page_count"] is None and all(x["page"] is None for x in emitted)
        if item["case"] == "positive-docx":
            assert any(x["kind"] == "table" for x in b) and "Operación RAG" in text
        if item["case"] == "positive-md":
            assert any(x["kind"] == "code" for x in b)
        if item["case"] == "positive-txt":
            assert "Café." in text
        destination = runtime.registry.resolver.resolve(
            AdministrativeTenant(UUID(fixture["tenant"])), "app"
        )
        actual = c.execute(
            sa.text(
                "SELECT current_database(),current_user,"
                "(SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid())"
            )
        ).one()
        assert tuple(actual) == (destination.database, destination.username, True)
    trace = uuid4()
    ctx = runtime.authority.authorize(
        UUID(MANIFEST["actors"]["alice"]), UUID(fixture["tenant"]), trace
    )
    original = runtime.documents.original(
        ctx, trace, UUID(fixture["repository"]), UUID(item["document"])
    )
    try:
        assert (
            original.file.content_hash == item["sha256"]
            and original.file.byte_size == item["byte_size"]
        )
    finally:
        original.close()
    return v, row, doc_state


def request(runtime, queue, fixture, item):
    trace = uuid4()
    actor = UUID(MANIFEST["actors"][item["actor"]])
    tenant, repo, doc = (
        UUID(fixture["tenant"]),
        UUID(fixture["repository"]),
        UUID(item["document"]),
    )
    ctx = runtime.authority.authorize(actor, tenant, trace)
    runtime.repositories.require(ctx, trace, repo, "upload")
    with runtime.repositories.connections.connection(ctx, trace) as c, c.begin():
        plan = journal.request(c, actor, repo, doc, trace, configuration(item))
        assert plan.version_id == version(item)
    identity = journal.enqueue(queue, tenant, plan)
    with runtime.repositories.connections.connection(ctx, trace) as c, c.begin():
        journal.dispatched(c, plan, identity)
    assert job(queue, fixture, item)["id"] == identity


class ProbeWorker(Worker):
    def __init__(self, *args, mode, target, **kwargs):
        super().__init__(*args, **kwargs)
        self.mode, self.target = mode, target

    def _stage(self, stage, claim):
        if claim.version_id != self.target:
            return
        if self.mode == "crash" and stage == "RESULT_COMMITTED":
            print("F04_STAGE RESULT_COMMITTED", flush=True)
            os._exit(85)
        if self.mode.startswith("pause-") and stage == "PARSED":
            print("F04_STAGE PARSED", flush=True)
            if not RELEASE.wait(45) and not STOP.is_set():
                raise RuntimeError("RELEASE_TIMEOUT")


def wait_terminal(worker, queue, fixture, item, *, seconds=180):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        row = job(queue, fixture, item)
        if row is not None and row["status"] in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return row
        if not worker.step():
            time.sleep(0.1)
    raise RuntimeError("WORKER_TIMEOUT")


def run():
    global PHASE, MANIFEST
    p = argparse.ArgumentParser()
    p.add_argument(
        "mode",
        choices=[
            "positive",
            "privacy",
            "sequence",
            "request",
            "process",
            "crash",
            "resume",
            "dependency",
            "pause-stop",
            "pause-tombstone",
            "pause-acl",
            "pause-membership",
            "verify",
        ],
    )
    p.add_argument("--fixture", choices=["same-a", "same-b", "two-a", "two-b"])
    p.add_argument("--case")
    p.add_argument("--chunk-size", type=int, default=1024)
    p.add_argument("--sequence-sizes", type=int, nargs=3, default=(384, 512, 768))
    args = p.parse_args()
    MANIFEST = json.loads(private_file("/checks/manifest.json", 512 * 1024))
    assert MANIFEST["version"] == 1
    credential = Credential(
        "f02_identity_app", private_file("/run/secrets/identity_app_password", 4096).decode()
    )
    key = private_file("/run/secrets/api_authority_key", 32)
    control = control_engine(Target("postgres", 5432, CA), credential)
    runtime = None
    try:
        runtime = Runtime(
            control,
            key,
            Path("/run/f04-worker"),
            "https://openbao:8200",
            CA,
            Path("/app/ops/f03/application-scope.json"),
        )
        runtime.preflight()
        assert tuple(UUID(f["tenant"]) for f in MANIFEST["fixtures"]) == runtime.scope
        queue = DurableQueue(
            control, tenant_scope=runtime.scope, lease_seconds=10 if args.mode == "crash" else 180
        )
        if args.mode == "sequence":
            for labels in (("same-a", "same-b", "same-a"), ("two-a", "two-b", "two-a")):
                selected = []
                for label, size in zip(labels, args.sequence_sizes, strict=True):
                    fixture = next(f for f in MANIFEST["fixtures"] if f["name"] == label)
                    original = next(i for i in fixture["documents"] if i["case"] == "positive-txt")
                    item = dict(original, configuration=(size, 64))
                    request(runtime, queue, fixture, item)
                    selected.append((fixture, item))

                class RecordedWorker(Worker):
                    def __init__(self, *args, **kwargs):
                        super().__init__(*args, **kwargs)
                        self.observed = []

                    def _stage(self, stage, claim):
                        if stage == "STARTED":
                            self.observed.append(claim.version_id)

                worker = RecordedWorker(runtime, queue, stop=STOP)
                for fixture, item in selected:
                    wait_terminal(worker, queue, fixture, item)
                    verify(runtime, queue, fixture, item)
                assert worker.observed == [version(item) for _, item in selected]
                print(
                    "PASS T005 A_B_A: mismo proceso; rol/TLS/destino propios; historial retenido.",
                    flush=True,
                )
            assert not worker.step() and runtime.registry.stats()["leases"] == 0
            return
        if args.mode == "positive":
            worker = Worker(runtime, queue, stop=STOP)
            worker.relay()
            for fixture in MANIFEST["fixtures"]:
                for item in fixture["documents"]:
                    if item["case"].startswith("positive-"):
                        PHASE = fixture["name"] + "/" + item["case"]
                        wait_terminal(worker, queue, fixture, item)
                        verify(runtime, queue, fixture, item)
                        request(
                            runtime, queue, fixture, item
                        )  # exact replay; no new envelope/version
                        verify(runtime, queue, fixture, item)
                print(
                    "PASS T005 WORKER "
                    + fixture["name"].upper()
                    + ": S3/PDF/DOCX/MD/TXT reales; hash/offsets/páginas/replay y TLS propios.",
                    flush=True,
                )
            assert not worker.step()
            stats = runtime.registry.stats()
            assert stats["engines"] <= 4 and stats["leases"] == 0
            print(
                "PASS T005 WORKER: runtime limitado, original conservado y pools liberados.",
                flush=True,
            )
            return
        fixture = next(f for f in MANIFEST["fixtures"] if f["name"] == args.fixture)
        item = next(i for i in fixture["documents"] if i["case"] == args.case)
        if args.chunk_size != 1024:
            item = dict(item, configuration=(args.chunk_size, 128))
        PHASE = args.mode + "/" + fixture["name"] + "/" + item["case"]
        if args.mode == "privacy":
            verify(runtime, queue, fixture, item)
            with tenant_connection(runtime, fixture) as c, c.begin():
                for setting, expected in SETTINGS.items():
                    assert (
                        c.scalar(sa.text("SELECT current_setting(:name)"), {"name": setting})
                        == expected
                    )
                piece = (
                    c.execute(
                        sa.select(chunks)
                        .where(chunks.c.version_id == version(item))
                        .order_by(chunks.c.ordinal)
                    )
                    .mappings()
                    .first()
                )
                assert "F04_WORKER_PRIVATE_CANARY" in piece["text"]
                c.execute(sa.text("DO $$ BEGIN RAISE LOG 'F04_WORKER_LOG_PROBE_ACTIVE_V1'; END $$"))
                rejected = False
                try:
                    with c.begin_nested():
                        values = dict(piece)
                        values["id"] = uuid4()
                        c.execute(chunks.insert().values(**values))
                except sa.exc.DBAPIError as error:
                    assert getattr(error.orig, "sqlstate", None) == "23514"
                    rejected = True
                assert rejected
            print(
                "PASS T005 PRIVACY: LOG positivo y error real; GUC privados; sin mutación.",
                flush=True,
            )
            return
        if args.mode == "request":
            request(runtime, queue, fixture, item)
            print(
                "PASS T005 REQUEST: versión/intención/envelope estables; actor original.",
                flush=True,
            )
            return
        worker = ProbeWorker(runtime, queue, stop=STOP, mode=args.mode, target=version(item))
        if args.mode == "resume":
            v, count, _ = local(runtime, fixture, item)
            assert v["state"] == "READY_FOR_EMBEDDING" and count > 0
            before = count
            until = time.monotonic() + 30
            while time.monotonic() < until:
                row = job(queue, fixture, item)
                with control.connect() as c:
                    expired = c.scalar(
                        sa.select(jobs.c.lease_until <= sa.func.clock_timestamp()).where(
                            jobs.c.id == row["id"]
                        )
                    )
                if expired:
                    break
                time.sleep(0.1)
            else:
                raise RuntimeError("LEASE_TIMEOUT")

            def no_reparse(*_args, **_kwargs):
                raise AssertionError("REPARSE_FORBIDDEN")

            worker.extractor = no_reparse
            wait_terminal(worker, queue, fixture, item)
            v, row, _ = verify(runtime, queue, fixture, item)
            assert row["attempts"] == 2 and v["chunk_count"] == before
            print(
                "PASS T005 CRASH: commit tenant persistente; ack sin reparse ni duplicados.",
                flush=True,
            )
            return
        if args.mode == "dependency":

            def unavailable(*_args, **_kwargs):
                raise OSError("synthetic unavailable provider")

            worker.extractor = unavailable
            assert worker.step()
            v, row, _ = verify(runtime, queue, fixture, item, ready=False)
            assert v["state"] == "FAILED_RETRYABLE" and row["status"] == "RETRY"
            worker = Worker(runtime, queue, stop=STOP)
            wait_terminal(worker, queue, fixture, item)
            v, row, _ = verify(runtime, queue, fixture, item)
            assert row["attempts"] == 2
            print(
                "PASS T005 RETRY: dependencia de etapa; misma versión/original/job recuperados.",
                flush=True,
            )
            return
        if args.mode == "verify":
            row = job(queue, fixture, item)
        else:
            assert worker.step()
            row = job(queue, fixture, item)
        if args.mode == "crash":
            raise RuntimeError("CRASH_BOUNDARY_NOT_REACHED")
        if args.mode == "pause-stop":
            v, row, _ = verify(runtime, queue, fixture, item, ready=False)
            assert row["status"] == "RETRY" and row["error_code"] == "STOP_REQUESTED"
            print("PASS T005 STOP: SIGTERM tras parseo; sin chunks; job recuperable.", flush=True)
        elif args.mode.startswith("pause-"):
            v, row, doc = verify(runtime, queue, fixture, item, ready=False)
            expected = "TOMBSTONED" if args.mode == "pause-tombstone" else "AUTHORIZATION_CHANGED"
            assert row["status"] == "FAILED" and row["error_code"] == expected
            if args.mode == "pause-tombstone":
                assert doc == "TOMBSTONED"
            print(
                "PASS T005 REVOCATION: cambio durante PARSED impide resultado tardío.", flush=True
            )
        elif item["case"] in {"scan", "malformed", "encrypted"}:
            v, row, _ = verify(runtime, queue, fixture, item, ready=False)
            expected = {
                "scan": ("NEEDS_OCR", "NEEDS_OCR"),
                "malformed": ("FAILED_TERMINAL", "PARSER_INVALID"),
                "encrypted": ("FAILED_TERMINAL", "PARSER_ENCRYPTED"),
            }[item["case"]]
            assert (v["state"], v["error_code"]) == expected and row["status"] == "FAILED"
            print(
                "PASS T005 PARSER: " + item["case"].upper() + " cerrado; sin chunks parciales.",
                flush=True,
            )
        else:
            verify(runtime, queue, fixture, item)
            print("PASS T005 WORKER RESULT: versión íntegra y original conservado.", flush=True)
    finally:
        if runtime is not None:
            runtime.close()
        control.dispose()


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)

    def stopping(_number, _frame):
        STOP.set()
        RELEASE.set()

    for value in (signal.SIGTERM, signal.SIGINT):
        signal.signal(value, stopping)
    signal.signal(signal.SIGUSR1, lambda _number, _frame: RELEASE.set())
    try:
        run()
    except Exception as error:
        state = getattr(getattr(error, "orig", None), "sqlstate", None)
        code = (
            "SQLSTATE_" + state
            if isinstance(state, str) and len(state) == 5 and state.isalnum()
            else "REFUSED"
        )
        print("F04-T005 WORKER/" + PHASE + " " + type(error).__name__ + " " + code, flush=True)
        raise SystemExit(1) from None
