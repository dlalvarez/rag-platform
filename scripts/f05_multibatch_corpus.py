"""Explicit four-document public corpus + selected INGEST only; no EMBED consumer."""

import argparse
import hashlib
import io
import json
import logging
import os
import stat
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid4

import sqlalchemy as sa
from f02_testing import Humans
from f03_http_check import API
from f04_api_check import candidate, item_of
from f05_sql_quality_check import corpus

from rag_platform.identity_api import private_file
from rag_platform.ingestion import journal
from rag_platform.ingestion.extraction import MAX_CHUNKS, ChunkConfig, chunks, from_wire
from rag_platform.ingestion.parsers import extract as parse
from rag_platform.ingestion.queue import DurableQueue
from rag_platform.ingestion.queue_schema import jobs
from rag_platform.ingestion.runtime import Runtime
from rag_platform.ingestion.schema import chunks as stored_chunks
from rag_platform.ingestion.schema import versions
from rag_platform.ingestion.worker import Worker
from rag_platform.providers.secrets import Credential
from rag_platform.provisioning.postgres import Target
from rag_platform.tenancy.resolver import control_engine

OUT = Path("/run/f04-qa")
PHASE = "START"
BODY_SHA = "1d9098227dfd23dbc3ca57b624fcb8831c5a6241249458543e96715fe16037ec"
BODY_BYTES = 11250


def save(name, value):
    encoded = json.dumps(value, sort_keys=True) + "\n"
    path = OUT / name
    if path.exists():
        if private_file(path, 512 * 1024).decode() != encoded:
            raise RuntimeError("CHECKPOINT_CONFLICT")
        return
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())


def body(path):
    data = corpus(path)
    text = (
        "F05_MULTIBATCH_PUBLIC_FIXTURE\n"
        + ("\n".join(item["text"] for item in data["documents"]) + "\n") * 6
    )
    raw = text.encode("utf-8")
    if hashlib.sha256(raw).hexdigest() != BODY_SHA or len(raw) != BODY_BYTES:
        raise ValueError("Frozen multibatch body mismatch")
    parsed = from_wire(parse(io.BytesIO(raw), "text/plain", len(raw)), "text/plain")
    count = len(chunks(parsed, ChunkConfig()))
    if not 4 < count <= min(64, MAX_CHUNKS) or len(raw) > 65536:
        raise ValueError("Explicit bounded multibatch corpus required")
    return raw, count


def scope_check(manifest, scope):
    fixtures = manifest["fixtures"]
    if len(fixtures) != 4 or [(r["name"], r["tenant"]) for r in fixtures] != [
        (r["name"], r["tenant"]) for r in scope
    ]:
        raise ValueError("Explicit four-fixture scope required")
    if "alice" not in manifest["actors"] or UUID(manifest["actors"]["alice"]).int == 0:
        raise ValueError("Retained actor required")
    for r in fixtures:
        if any(UUID(r[k]).int == 0 for k in ("tenant", "repository")):
            raise ValueError("Logical IDs required")
    if len({r["repository"] for r in fixtures}) != 4:
        raise ValueError("Independent repositories required")


def selected(manifest):
    result = []
    for record in manifest["fixtures"]:
        items = record["documents"]
        if len(items) != 1 or items[0]["case"] != "positive-txt" or items[0]["actor"] != "alice":
            raise ValueError("Only new explicit TXT fixture allowed")
        item = items[0]
        if item["sha256"] != BODY_SHA or item["byte_size"] != BODY_BYTES:
            raise ValueError("Frozen explicit corpus required")
        if UUID(item["document"]).int == 0 or UUID(item["original"]).int == 0:
            raise ValueError("Nonzero original/document required")
        result.append((UUID(record["tenant"]), UUID(item["document"]), candidate(item)))
    if len(result) != 4 or len(set(result)) != 4:
        raise ValueError("Four unique versions required")
    return tuple(result)


class SelectedQueue(DurableQueue):
    def __init__(self, engine, scope, targets):
        if len(targets) != 4 or any(t not in scope for t, _d, _v in targets):
            raise ValueError("Fixed scoped INGEST targets required")
        if len(set(targets)) != 4 or any(
            not isinstance(value, UUID) or value.int == 0 for row in targets for value in row
        ):
            raise ValueError("Four unique logical INGEST targets required")
        self.targets = tuple(targets)
        super().__init__(engine, lease_seconds=180, tenant_scope=scope)

    def _scope(self):
        return sa.and_(
            super()._scope(),
            sa.or_(
                *(
                    sa.and_(
                        jobs.c.tenant_id == tenant,
                        jobs.c.document_id == document,
                        jobs.c.version_id == version,
                    )
                    for tenant, document, version in self.targets
                )
            ),
        )


@contextmanager
def connection(runtime, actor, fixture):
    trace = uuid4()
    context = runtime.authority.authorize(actor, UUID(fixture["tenant"]), trace)
    runtime.repositories.require(context, trace, UUID(fixture["repository"]), "upload")
    with runtime.repositories.connections.connection(context, trace) as c, c.begin():
        c.exec_driver_sql("SET LOCAL lock_timeout='5s'")
        c.exec_driver_sql("SET LOCAL statement_timeout='15s'")
        yield c
        runtime.authority.validate(context, trace)


def ingest(runtime, control, manifest, expected_chunks):
    actor = UUID(manifest["actors"]["alice"])
    queue = SelectedQueue(control, runtime.scope, selected(manifest))
    # Explicit relay of these four exact intents. Never call Worker's general relay/run.
    for fixture in manifest["fixtures"]:
        item = fixture["documents"][0]
        trace = uuid4()
        with connection(runtime, actor, fixture) as c:
            plan = journal.request(
                c,
                actor,
                UUID(fixture["repository"]),
                UUID(item["document"]),
                trace,
                profile="embedding_publication",
            )
            assert plan.version_id == candidate(item)
        job = journal.enqueue(queue, UUID(fixture["tenant"]), plan)
        with connection(runtime, actor, fixture) as c:
            journal.dispatched(c, plan, job)
    worker = Worker(runtime, queue)
    deadline = time.monotonic() + 180
    while True:
        with control.connect() as c:
            states = list(c.scalars(sa.select(jobs.c.status).where(queue._scope())))
        assert len(states) == 4
        if all(state == "SUCCEEDED" for state in states):
            break
        if any(state == "FAILED" for state in states) or time.monotonic() >= deadline:
            raise RuntimeError("SELECTED_INGEST_FAILED")
        if not worker.step():
            time.sleep(0.2)
    result = []
    for fixture in manifest["fixtures"]:
        item = fixture["documents"][0]
        with connection(runtime, actor, fixture) as c:
            version = candidate(item)
            count = c.scalar(
                sa.select(sa.func.count())
                .select_from(stored_chunks)
                .where(stored_chunks.c.version_id == version)
            )
            state = c.scalar(sa.select(versions.c.state).where(versions.c.id == version))
            assert count == expected_chunks and count > 4
            assert state in ("READY_FOR_EMBEDDING", "PUBLISHED")
        result.append(dict(name=fixture["name"], chunks=count, ingest="SUCCEEDED"))
    return result


def originals(api, manifest, *, published=False):
    for fixture in manifest["fixtures"]:
        item = fixture["documents"][0]
        base = (
            f"/api/v1/tenants/{fixture['tenant']}/repositories/{fixture['repository']}"
            f"/documents/{item['document']}"
        )
        metadata = api.json("alice", "GET", base)["document"]
        assert metadata["version_id"] == item["original"]
        raw, _headers = api.call("alice", "GET", base + "/original")
        assert len(raw) == item["byte_size"] and hashlib.sha256(raw).hexdigest() == item["sha256"]
        if published:
            history = api.json(
                "alice",
                "GET",
                f"/api/v1/tenants/{fixture['tenant']}/documents/{item['document']}/versions",
            )
            assert any(
                v["version_id"] == str(candidate(item)) and v["state"] == "PUBLISHED"
                for v in history["items"]
            )


def run(mode):
    global PHASE
    info = OUT.lstat()
    assert stat.S_ISDIR(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o700
    assert info.st_uid == os.getuid() and OUT.resolve() == OUT
    scope = json.loads(Path("/app/ops/f03/application-scope.json").read_text())["fixtures"]
    humans, api, control, runtime = None, None, None, None
    try:
        humans = Humans()
        humans.ready()
        api = API(humans)
        if mode == "verify":
            manifest = json.loads(private_file(OUT / "manifest.json", 512 * 1024))
            scope_check(manifest, scope)
            selected(manifest)
            originals(api, manifest, published=True)
            save("verified.json", dict(originals_verified=4, published_versions=4))
            print("PASS F05 MULTIBATCH: four published originals HTTP/SHA retained.")
            return
        original = json.loads(private_file("/run/f04-base/manifest.json", 512 * 1024))
        scope_check(original, scope)
        actor = api.json("alice", "GET", "/api/v1/me")["principal_id"]
        assert actor == original["actors"]["alice"]
        raw, expected_chunks = body(Path("/app/tests/fixtures/f05/retrieval-es-en.json"))
        digest = hashlib.sha256(raw).hexdigest()
        checkpoint = OUT / "run.json"
        run_id = (
            UUID(json.loads(private_file(checkpoint, 4096))["id"])
            if checkpoint.exists()
            else uuid4()
        )
        save("run.json", dict(id=str(run_id), corpus_sha256=digest))
        ca = Path("/run/f01-ca.crt")
        control = control_engine(
            Target("postgres", 5432, ca),
            Credential(
                "f02_identity_app",
                private_file("/run/secrets/identity_app_password", 4096).decode(),
            ),
        )
        runtime = Runtime(
            control,
            private_file("/run/secrets/api_authority_key", 32),
            Path("/run/f04-worker"),
            "https://openbao:8200",
            ca,
            Path("/app/ops/f03/application-scope.json"),
            profile="embedding_publication",
        )
        runtime.preflight()
        records = []
        for fixture in original["fixtures"]:
            PHASE = "UPLOAD/" + fixture["name"]
            path = (
                f"/api/v1/tenants/{fixture['tenant']}/repositories/"
                f"{fixture['repository']}/documents?filename=f05-multibatch.txt"
            )
            headers = {
                "Content-Type": "text/plain",
                "Idempotency-Key": "f05-multibatch-" + run_id.hex + "-" + fixture["name"],
            }
            result, response_headers = api.call(
                "alice", "POST", path, body=raw, headers=headers, expected=(200, 201)
            )
            first = json.loads(result)
            assert first["request_id"] == response_headers["X-Request-ID"]
            repeated = api.json("alice", "POST", path, body=raw, headers=headers, expected=200)
            assert repeated["document"] == first["document"]
            item = item_of("positive-txt", first["document"], raw, "text/plain", "alice")
            save("document-" + fixture["name"] + ".json", item)
            records.append(
                dict(
                    name=fixture["name"],
                    tenant=fixture["tenant"],
                    repository=fixture["repository"],
                    documents=[item],
                )
            )
        manifest = dict(actors=original["actors"], fixtures=records)
        save("manifest.json", manifest)
        PHASE = "INGEST"
        result = ingest(runtime, control, manifest, expected_chunks)
        originals(api, manifest)
        save("prepared.json", dict(fixtures=result, originals_verified=4, sha256=digest))
        print(
            "PASS F05 MULTIBATCH: four explicit TXT/selected INGEST/original HTTP SHA.", flush=True
        )
    finally:
        if runtime is not None:
            runtime.close()
        if control is not None:
            control.dispose()
        if api is not None:
            api.close()
        if humans is not None:
            humans.close()


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "verify"))
    args = parser.parse_args()
    try:
        run(args.mode)
    except Exception:
        print("F05 MULTIBATCH " + PHASE + " REFUSED; resources retained.")
        raise SystemExit(1) from None
