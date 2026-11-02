"""Real opt-in F04 HTTP/SQL acceptance with scoped fixtures and application-only access."""

import argparse
import hashlib
import json
import logging
import os
import stat
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid4, uuid5

import sqlalchemy as sa
from f02_testing import Humans
from f03_http_check import API
from f03_testing import real_actors
from f04_corpus import pdf
from f04_seed import save

from rag_platform.documents.errors import DocumentError
from rag_platform.documents.schema import document_receipts
from rag_platform.documents.validation import UploadSpool
from rag_platform.identity_api import private_file
from rag_platform.ingestion.extraction import ChunkConfig
from rag_platform.ingestion.queue_schema import jobs
from rag_platform.ingestion.receipt import IngestionReceiptService
from rag_platform.ingestion.runtime import Runtime
from rag_platform.ingestion.schema import audit, chunks, documents, intents, versions
from rag_platform.providers.secrets import Credential
from rag_platform.provisioning.postgres import Target
from rag_platform.tenancy.resolver import control_engine

OUT = Path("/run/f04-qa")
CA = Path("/run/f01-ca.crt")
ROOT = Path(__file__).resolve().parents[1]
PHASE = "START"


def candidate(item):
    return uuid5(
        UUID(item["original"]), "F04/processing/v1:" + ChunkConfig().fingerprint(item["mime"])
    )


@contextmanager
def local(runtime, actors, fixture):
    trace = uuid4()
    ctx = runtime.authority.authorize(actors["alice"], UUID(fixture["tenant"]), trace)
    with runtime.repositories.connections.connection(ctx, trace) as c:
        yield c


def item_of(case, doc, body, mime, actor):
    return dict(
        case=case,
        document=doc["document_id"],
        original=doc["version_id"],
        sha256=hashlib.sha256(body).hexdigest(),
        byte_size=len(body),
        mime=mime,
        actor=actor,
    )


def atomic(runtime, actors, fixture, run):
    tenant, repo = UUID(fixture["tenant"]), UUID(fixture["repository"])
    key = "f04-api-atomic-" + run.hex + "-" + fixture["name"]
    body = b"F04_API_PRIVATE_CANARY atomic receipt forward recovery.\n"

    class FailAfterIntent(IngestionReceiptService):
        def _accepted(self, c, checked, trace, plan):
            super()._accepted(c, checked, trace, plan)
            raise RuntimeError("synthetic failure after durable intent statements")

    with UploadSpool("f04-atomic.txt", "text/plain") as spool:
        spool.accept(body)
        file = spool.finish()
        trace = uuid4()
        ctx = runtime.authority.authorize(actors["alice"], tenant, trace)
        failed = FailAfterIntent(runtime.repositories, runtime.gateway, lease_seconds=4)
        try:
            failed.receive(ctx, trace, repo, key, file)
        except DocumentError as error:
            assert error.code == "DEPENDENCY_UNAVAILABLE"
        else:
            raise AssertionError("ROLLBACK_REQUIRED")
        with local(runtime, actors, fixture) as c:
            receipt = (
                c.execute(
                    sa.select(document_receipts).where(
                        document_receipts.c.repository_id == repo,
                        document_receipts.c.principal_id == actors["alice"],
                        document_receipts.c.idempotency_key == key,
                    )
                )
                .mappings()
                .one()
            )
            assert receipt["state"] == "OBJECT_STORED"
            assert (
                c.scalar(
                    sa.select(sa.func.count())
                    .select_from(documents)
                    .where(documents.c.id == receipt["candidate_document_id"])
                )
                == 0
            )
            assert (
                c.scalar(
                    sa.select(sa.func.count())
                    .select_from(versions)
                    .where(versions.c.document_id == receipt["candidate_document_id"])
                )
                == 0
            )
            assert (
                c.scalar(
                    sa.select(sa.func.count())
                    .select_from(intents)
                    .where(intents.c.document_id == receipt["candidate_document_id"])
                )
                == 0
            )
        time.sleep(4.2)  # actual receipt lease expiry, no forced metadata edits
        trace = uuid4()
        ctx = runtime.authority.authorize(actors["alice"], tenant, trace)
        accepted = IngestionReceiptService(runtime.repositories, runtime.gateway, lease_seconds=4)
        first = accepted.receive(ctx, trace, repo, key, file)
        assert first.created
        trace = uuid4()
        ctx = runtime.authority.authorize(actors["alice"], tenant, trace)
        second = accepted.receive(ctx, trace, repo, key, file)
        assert not second.created and second.document == first.document
        assert first.document["version_id"] == str(receipt["version_id"])
        item = item_of("atomic", first.document, body, "text/plain", "alice")
        with local(runtime, actors, fixture) as c:
            assert (
                c.scalar(
                    sa.select(sa.func.count())
                    .select_from(versions)
                    .where(versions.c.document_id == UUID(item["document"]))
                )
                == 2
            )
            assert (
                c.scalar(
                    sa.select(sa.func.count())
                    .select_from(intents)
                    .where(intents.c.document_id == UUID(item["document"]))
                )
                == 1
            )
        return item


def list_versions(api, user, fixture, item, *, expected=200, query=""):
    path = f"/api/v1/tenants/{fixture['tenant']}/documents/{item['document']}/versions"
    return api.json(user, "GET", path + query, expected=expected)


def metadata_only(value):
    encoded = json.dumps(value)
    assert "F04_API_PRIVATE_CANARY" not in encoded
    assert not any(
        key in encoded
        for key in (
            '"blob_key"',
            '"lease_token"',
            '"filename"',
            '"secret_ref"',
            '"processing_actor_id"',
            '"text"',
            '"actor_id"',
        )
    )


def seed(api, runtime, actors, fixtures, run):
    result = dict(
        version=1, run_id=str(run), actors={k: str(v) for k, v in actors.items()}, fixtures=[]
    )
    for scope in fixtures:
        global PHASE
        PHASE = scope["name"] + "/SEED"
        root = f"/api/v1/tenants/{scope['tenant']}/repositories"
        repo = api.json(
            "alice",
            "POST",
            root,
            value={"name": "f04-api-" + scope["name"] + "-" + run.hex[:12]},
            expected=201,
        )["repository"]["repository_id"]
        record = dict(name=scope["name"], tenant=scope["tenant"], repository=repo, documents=[])
        save("repository-" + scope["name"] + ".json", record)
        for user, role in (("bob", "editor"), ("carol", "reader")):
            api.json(
                "alice",
                "PUT",
                root + "/" + repo + "/acl/" + str(actors[user]),
                value={"role": role},
            )
        for case, actor in (
            ("positive", "alice"),
            ("bob", "bob"),
            ("scan", "alice"),
            ("tombstone", "alice"),
        ):
            PHASE = scope["name"] + "/" + case
            mime = "application/pdf" if case == "scan" else "text/plain"
            body = (
                pdf(("scan",), scanned=True)
                if case == "scan"
                else (
                    "F04_API_PRIVATE_CANARY " + case + " Café. SELECT valor FROM tabla;\n"
                ).encode()
            )
            endpoint = (
                root
                + "/"
                + repo
                + "/documents?filename=f04-api."
                + ("pdf" if case == "scan" else "txt")
            )
            headers = {
                "Content-Type": mime,
                "Idempotency-Key": "f04-api-" + run.hex + "-" + scope["name"] + "-" + case,
            }
            first = api.json(actor, "POST", endpoint, body=body, headers=headers, expected=201)[
                "document"
            ]
            assert (
                api.json(actor, "POST", endpoint, body=body, headers=headers)["document"] == first
            )
            item = item_of(case, first, body, mime, actor)
            record["documents"].append(item)
            save("document-" + scope["name"] + "-" + case + ".json", item)
            for user in ("alice", "bob", "carol"):
                page = list_versions(api, user, record, item)
                metadata_only(page)
                assert len(page["items"]) == 2 and all(v["job_id"] is None for v in page["items"])
                assert {v["kind"] for v in page["items"]} == {"ORIGINAL", "PROCESSED"}
            list_versions(api, "dave", record, item, expected=403)
            list_versions(api, None, record, item, expected=401)
            if case == "tombstone":
                path = f"/api/v1/tenants/{scope['tenant']}/documents/{item['document']}"
                api.json("bob", "DELETE", path, expected=403)
                api.json("carol", "DELETE", path, expected=403)
                one = api.json("alice", "DELETE", path)["document"]
                assert api.json("alice", "DELETE", path)["document"] == one
                list_versions(api, "alice", record, item, expected=404)
                api.json(
                    "alice",
                    "GET",
                    root + "/" + repo + "/documents/" + item["document"] + "/original",
                    expected=404,
                )
            else:
                raw, _ = api.call(
                    "carol",
                    "GET",
                    root + "/" + repo + "/documents/" + item["document"] + "/original",
                )
                assert raw == body
        item = atomic(runtime, actors, record, run)
        record["documents"].append(item)
        save("document-" + scope["name"] + "-atomic.json", item)
        result["fixtures"].append(record)
        print(
            "PASS T006 SEED "
            + scope["name"].upper()
            + ": HTTP/replay/read-only/ACL; receipt+intent rollback and recovery.",
            flush=True,
        )
    save("manifest.json", result)


def verify(api, runtime, actors, manifest):
    for fixture in manifest["fixtures"]:
        global PHASE
        PHASE = fixture["name"] + "/VERIFY"
        prefix = f"/api/v1/tenants/{fixture['tenant']}"
        checkpoint = OUT / ("predelete-" + fixture["name"] + ".json")
        if (OUT / ("verified-" + fixture["name"] + ".json")).exists():
            continue
        if not checkpoint.exists():
            for item in fixture["documents"]:
                with local(runtime, actors, fixture) as c:
                    v = (
                        c.execute(sa.select(versions).where(versions.c.id == candidate(item)))
                        .mappings()
                        .one()
                    )
                    n = c.scalar(
                        sa.select(sa.func.count())
                        .select_from(chunks)
                        .where(chunks.c.version_id == candidate(item))
                    )
                    intent = (
                        c.execute(sa.select(intents).where(intents.c.version_id == candidate(item)))
                        .mappings()
                        .one()
                    )
                    assert (
                        c.scalar(
                            sa.select(sa.func.count())
                            .select_from(versions)
                            .where(versions.c.document_id == UUID(item["document"]))
                        )
                        == 2
                    )
                    assert (
                        v["content_hash"] == item["sha256"] and v["byte_size"] == item["byte_size"]
                    )
                    job_id = str(intent["job_id"])
                    assert UUID(job_id).int
                    assert c.scalar(
                        sa.select(documents.c.current_version_id).where(
                            documents.c.id == UUID(item["document"])
                        )
                    ) == UUID(item["original"])
                job_path = prefix + "/jobs/" + job_id
                if item["case"] == "tombstone":
                    list_versions(api, "alice", fixture, item, expected=404)
                    api.json("alice", "GET", job_path, expected=404)
                    assert n == 0
                    with runtime.repositories.control.connect() as control:
                        terminal = control.execute(
                            sa.select(jobs.c.status, jobs.c.error_code).where(
                                jobs.c.id == UUID(job_id),
                                jobs.c.tenant_id == UUID(fixture["tenant"]),
                            )
                        ).one()
                        assert tuple(terminal) == ("FAILED", "TOMBSTONED")
                    with local(runtime, actors, fixture) as c:
                        assert (
                            c.scalar(
                                sa.select(sa.func.count())
                                .select_from(audit)
                                .where(
                                    audit.c.target_id == UUID(item["document"]),
                                    audit.c.action == "DOCUMENT_TOMBSTONED",
                                )
                            )
                            == 1
                        )
                    continue
                status = "FAILED" if item["case"] == "scan" else "SUCCEEDED"
                expected = "NEEDS_OCR" if item["case"] == "scan" else "READY_FOR_EMBEDDING"
                assert v["state"] == expected and (n == 0 if status == "FAILED" else n > 0)
                for user in ("alice", "bob", "carol"):
                    page = list_versions(api, user, fixture, item)
                    metadata_only(page)
                    processed = next(x for x in page["items"] if x["kind"] == "PROCESSED")
                    assert processed["version_id"] == str(candidate(item))
                    assert processed["state"] == expected and processed["job_id"] == job_id
                    progress = api.json(user, "GET", job_path)
                    metadata_only(progress)
                    assert progress["job"]["status"] == status
                    assert progress["job"]["version_state"] == expected
                api.json("dave", "GET", job_path, expected=403)
                api.json(None, "GET", job_path, expected=401)
                api.json("alice", "GET", job_path + "?lease_token=untrusted", expected=422)
            positive = next(i for i in fixture["documents"] if i["case"] == "positive")
            page = list_versions(api, "alice", fixture, positive, query="?limit=1")
            assert len(page["items"]) == 1 and page["next_cursor"]
            cursor = page["next_cursor"]
            tail = list_versions(api, "alice", fixture, positive, query="?limit=1&cursor=" + cursor)
            assert len(tail["items"]) == 1 and not tail["next_cursor"]
            assert tail["items"][0]["version_id"] != page["items"][0]["version_id"]
            for user in ("bob", "carol"):
                list_versions(api, user, fixture, positive, expected=422, query="?cursor=" + cursor)
            other = next(i for i in fixture["documents"] if i["case"] == "atomic")
            list_versions(api, "alice", fixture, other, expected=422, query="?cursor=" + cursor)
            list_versions(
                api, "alice", fixture, positive, expected=422, query="?cursor=" + cursor[:-1] + "!"
            )
            for query in ("?limit=0", "?limit=101", "?limit=2&limit=3", "?host=untrusted"):
                list_versions(api, "alice", fixture, positive, expected=422, query=query)
            foreign = next(f for f in manifest["fixtures"] if f["tenant"] != fixture["tenant"])
            outsider = next(i for i in foreign["documents"] if i["case"] == "atomic")
            with local(runtime, actors, foreign) as c:
                foreign_job = c.scalar(
                    sa.select(intents.c.job_id).where(intents.c.version_id == candidate(outsider))
                )
            list_versions(api, "alice", fixture, outsider, expected=404)
            api.json("alice", "GET", prefix + "/jobs/" + str(foreign_job), expected=404)
            # Revoke only Bob's ACL on this newly created run and restore even on failure.
            acl = prefix + "/repositories/" + fixture["repository"] + "/acl/" + str(actors["bob"])
            api.json("alice", "DELETE", acl)
            try:
                list_versions(api, "bob", fixture, positive, expected=403)
                with local(runtime, actors, fixture) as c:
                    own_job = c.scalar(
                        sa.select(intents.c.job_id).where(
                            intents.c.version_id == candidate(positive)
                        )
                    )
                api.json("bob", "GET", prefix + "/jobs/" + str(own_job), expected=403)
            finally:
                api.json("alice", "PUT", acl, value={"role": "editor"})

            save(
                "predelete-" + fixture["name"] + ".json",
                {
                    "tenant": fixture["tenant"],
                    "repository": fixture["repository"],
                    "state": "HTTP_CHECKED",
                },
            )
        positive = next(i for i in fixture["documents"] if i["case"] == "positive")
        with local(runtime, actors, fixture) as c:
            own_job = c.scalar(
                sa.select(intents.c.job_id).where(intents.c.version_id == candidate(positive))
            )
        # Delete a completed result through HTTP; preserve physical history/chunks.
        path = prefix + "/documents/" + positive["document"]
        result = api.json("alice", "DELETE", path)["document"]
        assert api.json("alice", "DELETE", path)["document"] == result
        list_versions(api, "alice", fixture, positive, expected=404)
        api.json("alice", "GET", prefix + "/jobs/" + str(own_job), expected=404)
        with local(runtime, actors, fixture) as c:
            assert (
                c.scalar(
                    sa.select(sa.func.count())
                    .select_from(chunks)
                    .where(chunks.c.version_id == candidate(positive))
                )
                > 0
            )
            assert (
                c.scalar(
                    sa.select(sa.func.count())
                    .select_from(audit)
                    .where(
                        audit.c.target_id == UUID(positive["document"]),
                        audit.c.action == "DOCUMENT_TOMBSTONED",
                    )
                )
                == 1
            )
        save(
            "verified-" + fixture["name"] + ".json",
            {"tenant": fixture["tenant"], "state": "VERIFIED"},
        )
        print(
            "PASS T006 VERIFY "
            + fixture["name"].upper()
            + ": job/version ACL+cursor+cross-tenant; HTTP tombstone retains chunks.",
            flush=True,
        )
    for labels in (("same-a", "same-b", "same-a"), ("two-a", "two-b", "two-a")):
        for label in labels:
            fixture = next(f for f in manifest["fixtures"] if f["name"] == label)
            item = next(i for i in fixture["documents"] if i["case"] == "atomic")
            assert (
                next(
                    v
                    for v in list_versions(api, "carol", fixture, item)["items"]
                    if v["kind"] == "PROCESSED"
                )["state"]
                == "READY_FOR_EMBEDDING"
            )
        print("PASS T006 HTTP A_B_A: own metadata only; reader SQL unchanged.", flush=True)


def run():
    global PHASE
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("seed", "verify"))
    p.add_argument("--run", type=UUID, required=True)
    args = p.parse_args()
    info = OUT.lstat()
    assert stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
    assert stat.S_IMODE(info.st_mode) == 0o700 and OUT.resolve() == OUT
    if args.mode == "seed":
        save("started.json", {"version": 1, "run_id": str(args.run), "state": "STARTED"})
    humans, api, runtime, control = None, None, None, None
    try:
        humans = Humans()
        humans.ready()
        api = API(humans)
        control = control_engine(
            Target("postgres", 5432, CA),
            Credential(
                "f02_identity_app",
                private_file("/run/secrets/identity_app_password", 4096).decode(),
            ),
        )
        actors = real_actors(control, humans)
        runtime = Runtime(
            control,
            private_file("/run/secrets/api_authority_key", 32),
            Path("/run/f04-worker"),
            "https://openbao:8200",
            CA,
            ROOT / "ops/f03/application-scope.json",
        )
        runtime.preflight()
        fixtures = json.loads((ROOT / "ops/f03/application-scope.json").read_text())["fixtures"]
        if args.mode == "seed":
            seed(api, runtime, actors, fixtures, args.run)
        else:
            manifest = json.loads(private_file(OUT / "manifest.json", 512 * 1024))
            assert manifest["run_id"] == str(args.run)
            assert manifest["actors"] == {k: str(v) for k, v in actors.items()}
            assert [(f["name"], f["tenant"]) for f in manifest["fixtures"]] == [
                (f["name"], f["tenant"]) for f in fixtures
            ]
            verify(api, runtime, actors, manifest)
        print("PASS T006: resources retained; no embeddings/PUBLISHED or F04 closure.", flush=True)
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
    try:
        run()
    except Exception as error:
        state = getattr(getattr(error, "orig", None), "sqlstate", None)
        code = (
            "SQLSTATE_" + state
            if isinstance(state, str) and len(state) == 5 and state.isalnum()
            else "REFUSED"
        )
        print("F04-T006 " + PHASE + " " + type(error).__name__ + " " + code, flush=True)
        raise SystemExit(1) from None
