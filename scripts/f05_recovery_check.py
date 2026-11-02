"""Real Qwen fault proof on four explicitly selected retained positive versions."""

import argparse
import json
import logging
import math
import os
import re
import stat
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid4

import f05_adopt
import sqlalchemy as sa
from f05_real_embedding_check import selection

from rag_platform.embeddings import processing
from rag_platform.embeddings.queue import EmbeddingClaim, EmbeddingQueue
from rag_platform.embeddings.queue_schema_f05_0007 import jobs
from rag_platform.embeddings.qwen import REVISION, LocalQwen, qwen_profile
from rag_platform.embeddings.runtime import Runtime
from rag_platform.embeddings.space_ddl import vector_table
from rag_platform.embeddings.worker import Worker
from rag_platform.identity_api import private_file
from rag_platform.ingestion.claims import ClaimExpired, locked_claim
from rag_platform.providers.secrets import Credential
from rag_platform.provisioning.postgres import Target
from rag_platform.tenancy.resolver import control_engine

OUT = Path("/run/f05-qa")
CA = Path("/run/f01-ca.crt")
PHASE = "START"
STAGES = {
    "same-a": "BATCH_COMMITTED",
    "same-b": "RESULT_COMMITTED",
    "two-a": "BATCH_COMMITTED",
    "two-b": "RESULT_COMMITTED",
}


def records():
    manifest = json.loads(private_file("/run/f04-qa/manifest.json", 512 * 1024))
    actors = {key: UUID(value) for key, value in manifest["actors"].items()}
    scope = json.loads(Path("/app/ops/f03/application-scope.json").read_text())["fixtures"]
    return actors["alice"], selection(manifest, actors, scope, case="positive")


@contextmanager
def connect(runtime, actor, record, *, write=False):
    trace = uuid4()
    context = runtime.authority.authorize(actor, UUID(record["tenant"]), trace)
    runtime.repositories.require(
        context, trace, UUID(record["repository"]), "upload" if write else "read"
    )
    with runtime.repositories.connections.connection(context, trace) as c, c.begin():
        c.exec_driver_sql("SET LOCAL lock_timeout='5s'")
        c.exec_driver_sql("SET LOCAL statement_timeout='15s'")
        yield c
        runtime.authority.validate(context, trace)


def snapshot(runtime, actor, record):
    intent, version, space, doc, raw = (
        UUID(record[key]) for key in ("intent", "version", "space", "document", "original")
    )
    with connect(runtime, actor, record) as c:
        batches = (
            c.execute(
                sa.select(processing.batches)
                .where(processing.batches.c.intent_id == intent)
                .order_by(processing.batches.c.ordinal)
            )
            .mappings()
            .all()
        )
        ledger = [
            dict(
                ordinal=r["ordinal"],
                chunks=[str(v) for v in r["chunk_ids"]],
                tokens=r["input_tokens"],
                requests=r["requests"],
                elapsed_ms=r["elapsed_ms"],
            )
            for r in batches
        ]
        plan = c.execute(
            sa.select(processing.intents.c.status, processing.intents.c.job_id).where(
                processing.intents.c.id == intent
            )
        ).one()
        pointer = c.execute(
            sa.select(
                processing.documents.c.original_version_id,
                processing.documents.c.current_version_id,
                processing.documents.c.current_version_kind,
            ).where(processing.documents.c.id == doc)
        ).one()
        original = c.execute(
            sa.select(processing.versions.c.content_hash, processing.versions.c.byte_size).where(
                processing.versions.c.id == raw
            )
        ).one()
        assert tuple(original) == (record["sha256"], record["byte_size"])
        assert pointer.original_version_id == raw
        vectors = vector_table(sa.MetaData(), space, qwen_profile())
        count = c.scalar(
            sa.select(sa.func.count()).select_from(vectors).where(vectors.c.version_id == version)
        )
        published = c.scalar(
            sa.select(sa.func.count())
            .select_from(processing.publications)
            .where(processing.publications.c.intent_id == intent)
        )
    with runtime.authority.engine.connect() as c:
        job = c.execute(
            sa.select(jobs.c.status, jobs.c.attempts).where(jobs.c.id == plan.job_id)
        ).one()
    return dict(
        ledger=ledger,
        vectors=count,
        published=published,
        status=plan.status,
        job_status=job.status,
        attempts=job.attempts,
        processed_pointer=pointer.current_version_id == version
        and pointer.current_version_kind == "PROCESSED",
        original_retained=True,
    )


class SelectedQueue(EmbeddingQueue):
    def __init__(self, engine, scope, record):
        self.record, self.pulses = record, 0
        super().__init__(
            engine,
            tenant_scope=scope,
            lease_seconds=15,
            max_attempts=3,
            profile_fingerprint=qwen_profile().fingerprint(),
        )

    def _scope(self):
        return sa.and_(
            super()._scope(),
            jobs.c.tenant_id == UUID(self.record["tenant"]),
            jobs.c.document_id == UUID(self.record["document"]),
            jobs.c.version_id == UUID(self.record["version"]),
        )

    def heartbeat(self, claim):
        renewed = super().heartbeat(claim)
        self.pulses += int(renewed)
        return renewed


class ObservedProvider:
    def __init__(self, provider, delay):
        self.base, self.profile, self.delay, self.calls = provider, provider.profile, delay, 0

    def count_tokens(self, text, kind):
        return self.base.count_tokens(text, kind)

    def embed(self, texts, kind):
        self.calls += 1
        if self.delay and self.calls == 1:
            # Delayed real response tests TTL/lease, not raw model performance.
            time.sleep(35)
        return self.base.embed(texts, kind)


class FaultWorker(Worker):
    def __init__(self, runtime, queue, provider, actor, record, crash):
        super().__init__(runtime, queue, provider, heartbeat_interval=5)
        self.actor, self.record, self.crash = actor, record, crash

    def _stage(self, stage, claim):
        if self.crash and stage == STAGES[self.record["name"]]:
            assert claim.version_id == UUID(self.record["version"])
            assert self.queue.pulses >= 7
            state = snapshot(self.runtime, self.actor, self.record)
            state["provider_calls"] = self.provider.calls
            state["successful_heartbeats"] = self.queue.pulses
            assert state["job_status"] == "RUNNING" and state["attempts"] == 1
            assert state["ledger"]
            if stage == "BATCH_COMMITTED":
                assert state["published"] == 0 and not state["processed_pointer"]
            else:
                assert state["published"] == 1 and state["processed_pointer"]
            f05_adopt.save(self.record["name"] + ".crash.json", state)
            print(
                "PASS F05 RECOVERY "
                + self.record["name"]
                + "/"
                + stage
                + ": durable checkpoint before hard exit86.",
                flush=True,
            )
            os._exit(86)


def prepare(runtime, provider, actor, selected):
    global PHASE
    budget = []
    for record in selected:
        PHASE = "PREPARE/" + record["name"] + "/TOKEN_GATE"
        with connect(runtime, actor, record) as c:
            rows = (
                c.execute(
                    sa.select(processing.chunks.c.text)
                    .where(processing.chunks.c.version_id == UUID(record["version"]))
                    .order_by(processing.chunks.c.ordinal)
                )
                .scalars()
                .all()
            )
            assert 1 <= len(rows) <= processing.MAX_JOB_CHUNKS
            counts = [provider.count_tokens(text, "passage") for text in rows]
            print(
                "F05 RECOVERY budget "
                + record["name"]
                + ": chunks="
                + str(len(rows))
                + " max_tokens="
                + str(max(counts))
                + " total_tokens="
                + str(sum(counts)),
                flush=True,
            )
            assert all(1 <= n <= provider.profile.max_tokens for n in counts)
            assert sum(counts) <= processing.MAX_JOB_TOKENS
            budget.append(
                dict(
                    name=record["name"],
                    chunks=len(rows),
                    tokens=sum(counts),
                    requests=math.ceil(len(rows) / 4),
                )
            )
    # Check all four budgets before creating any new intent.
    f05_adopt.save("selection.json", dict(records=selected, budget=budget))
    for record in selected:
        with connect(runtime, actor, record, write=True) as c:
            processing.request(
                c,
                actor,
                UUID(record["repository"]),
                UUID(record["document"]),
                UUID(record["version"]),
                qwen_profile(),
            )
    print("PASS F05 RECOVERY prepare: four explicit positive versions, token/chunk gates.")


def stale_refused(queue, claim):
    assert not queue.heartbeat(claim)
    assert not queue.fail(claim, "DEPENDENCY_UNAVAILABLE", retryable=True)
    try:
        with locked_claim(queue, claim):
            raise RuntimeError("STALE_FENCE_ACCEPTED")
    except ClaimExpired:
        return
    raise RuntimeError("STALE_FENCE_ACCEPTED")


def resume(runtime, queue, provider, worker, actor, record):
    previous = json.loads(private_file(OUT / (record["name"] + ".crash.json"), 512 * 1024))
    assert snapshot(runtime, actor, record)["ledger"] == previous["ledger"]
    with queue.engine.connect() as c:
        row = c.execute(sa.select(jobs).where(queue._scope())).mappings().one()
    assert row["status"] == "RUNNING" and row["attempts"] == 1
    old_claim = EmbeddingClaim(
        row["id"],
        row["tenant_id"],
        row["actor_id"],
        row["document_id"],
        row["version_id"],
        row["attempts"],
        row["lease_token"],
        row["space_id"],
        row["profile_fingerprint"],
    )
    deadline = time.monotonic() + 25
    while not worker.step():
        if time.monotonic() >= deadline:
            raise RuntimeError("LEASE_NOT_AVAILABLE")
        time.sleep(0.5)
    current = snapshot(runtime, actor, record)
    budget = json.loads(private_file(OUT / "selection.json", 512 * 1024))["budget"]
    expected = next(r for r in budget if r["name"] == record["name"])
    assert current["job_status"] == "SUCCEEDED" and current["attempts"] == 2
    assert current["status"] == "COMPLETE" and current["published"] == 1
    assert current["processed_pointer"] and current["vectors"] == expected["chunks"]
    assert current["ledger"][: len(previous["ledger"])] == previous["ledger"]
    assert len(current["ledger"]) == expected["requests"]
    assert sum(b["tokens"] for b in current["ledger"]) == expected["tokens"]
    assert sum(b["requests"] for b in current["ledger"]) == expected["requests"]
    assert provider.calls == expected["requests"] - previous["provider_calls"]
    # The previous process cannot renew, fail or commit using its obsolete fence.
    stale_refused(queue, old_claim)
    # A completed envelope cannot be claimed or inferred a third time.
    assert not worker.step()
    assert snapshot(runtime, actor, record) == current
    current["resume_provider_calls"] = provider.calls
    f05_adopt.save(record["name"] + ".resumed.json", current)
    print(
        "PASS F05 RECOVERY "
        + record["name"]
        + ": resumed/fenced/no duplicate committed usage; original anchor retained.",
        flush=True,
    )


def run(mode, name):
    global PHASE
    if mode not in ("prepare", "crash", "resume") or (
        (mode == "prepare" and name is not None) or (mode != "prepare" and name not in STAGES)
    ):
        raise ValueError("Explicit recovery mode and fixture required")
    info = OUT.lstat()
    assert stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
    assert stat.S_IMODE(info.st_mode) == 0o700 and OUT.resolve() == OUT
    actor, selected = records()
    engine = control_engine(
        Target("postgres", 5432, CA),
        Credential(
            "f02_identity_app", private_file("/run/secrets/identity_app_password", 4096).decode()
        ),
    )
    runtime = None
    try:
        runtime = Runtime(
            engine,
            private_file("/run/secrets/api_authority_key", 32),
            Path("/run/f05-worker"),
            "https://openbao:8200",
            CA,
            Path("/app/ops/f03/application-scope.json"),
        )
        runtime.preflight()
        PHASE = mode.upper() + "/" + str(name)
        provider = ObservedProvider(
            LocalQwen.load(Path("/models/qwen3-embedding-0.6b") / REVISION), mode == "crash"
        )
        if mode == "prepare":
            assert name is None
            prepare(runtime, provider, actor, selected)
            return
        saved = json.loads(private_file(OUT / "selection.json", 512 * 1024))
        assert saved["records"] == selected
        record = next(r for r in selected if r["name"] == name)
        if mode == "crash":
            assert not (OUT / (name + ".crash.json")).exists()
        queue = SelectedQueue(engine, runtime.scope, record)
        worker = FaultWorker(runtime, queue, provider, actor, record, mode == "crash")
        worker.preflight()
        if mode == "crash":
            with connect(runtime, actor, record, write=True) as c:
                plan = processing.request(
                    c,
                    actor,
                    UUID(record["repository"]),
                    UUID(record["document"]),
                    UUID(record["version"]),
                    qwen_profile(),
                )
            job = processing.enqueue(queue, UUID(record["tenant"]), plan)
            with connect(runtime, actor, record, write=True) as c:
                processing.dispatched(c, plan, job)
            assert worker.step()
            raise RuntimeError("EXPECTED_HARD_EXIT_MISSING")
        resume(runtime, queue, provider, worker, actor, record)
    finally:
        if runtime is not None:
            runtime.close()
        engine.dispose()


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "crash", "resume"))
    parser.add_argument("name", nargs="?", choices=tuple(STAGES))
    args = parser.parse_args()
    try:
        run(args.mode, args.name)
    except Exception as error:
        state = getattr(getattr(error, "orig", error), "sqlstate", None)
        code = state if isinstance(state, str) and re.fullmatch("[A-Z0-9]{5}", state) else "REFUSED"
        print("F05 RECOVERY " + PHASE + " " + code + "; resources retained.")
        raise SystemExit(1) from None
