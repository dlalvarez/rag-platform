"""Opt-in application-only Qwen publication proof; explicit retained atomic fixtures only."""

import argparse
import hashlib
import json
import logging
import os
import re
import stat
from pathlib import Path
from uuid import UUID, uuid4, uuid5

import sqlalchemy as sa
from f02_testing import Humans
from f03_http_check import API
from f03_testing import real_actors
from f04_api_check import CA, ROOT, candidate
from f04_api_check import OUT as MANIFEST_ROOT
from f05_adopt import save

from rag_platform.embeddings import processing
from rag_platform.embeddings.queue_schema_f05_0007 import jobs
from rag_platform.embeddings.qwen import qwen_profile
from rag_platform.embeddings.space_ddl import vector_table
from rag_platform.identity_api import private_file
from rag_platform.ingestion.runtime import Runtime
from rag_platform.providers.secrets import Credential
from rag_platform.provisioning.postgres import Target
from rag_platform.tenancy.resolver import control_engine

OUT = Path("/run/f05-qa")
PHASE = "START"


def selection(manifest, actors, scope):
    """Only the exact retained scope and authenticated principals may select work."""
    expected = [(r["name"], r["tenant"]) for r in scope]
    if (
        manifest.get("actors") != {k: str(v) for k, v in actors.items()}
        or [(r["name"], r["tenant"]) for r in manifest["fixtures"]] != expected
        or len(expected) != 4
        or len(set(expected)) != 4
        or {r[0] for r in expected} != {"same-a", "same-b", "two-a", "two-b"}
    ):
        raise ValueError("Fixture scope mismatch")
    result = []
    for fixture in manifest["fixtures"]:
        items = [r for r in fixture["documents"] if r["case"] == "atomic"]
        if len(items) != 1 or items[0]["actor"] != "alice":
            raise ValueError("Explicit fixture missing")
        item = items[0]
        tenant, repository, document, original = (
            UUID(value)
            for value in (
                fixture["tenant"],
                fixture["repository"],
                item["document"],
                item["original"],
            )
        )
        if any(v.int == 0 for v in (tenant, repository, document, original)):
            raise ValueError("Invalid fixture identity")
        profile = qwen_profile()
        version = candidate(item)
        space = uuid5(tenant, "F05/space/v1:" + profile.fingerprint())
        result.append(
            dict(
                name=fixture["name"],
                tenant=str(tenant),
                repository=str(repository),
                document=str(document),
                original=str(original),
                version=str(version),
                space=str(space),
                intent=str(uuid5(space, "F05/intent/v1:" + str(version))),
                sha256=item["sha256"],
                byte_size=item["byte_size"],
            )
        )
    if len({r["document"] for r in result}) != 4:
        raise ValueError("Duplicate fixture identity")
    return result


def request(runtime, actor, record):
    trace = uuid4()
    tenant, repo, doc, version = (
        UUID(record[k]) for k in ("tenant", "repository", "document", "version")
    )
    context = runtime.authority.authorize(actor, tenant, trace)
    with runtime.repositories.connections.connection(context, trace) as c, c.begin():
        plan = processing.request(c, actor, repo, doc, version, qwen_profile())
        assert (str(plan.id), str(plan.space_id)) == (record["intent"], record["space"])
        runtime.authority.validate(context, trace)


def verify(runtime, control, api, actor, record):
    trace = uuid4()
    tenant, repo, doc, version, space, intent = (
        UUID(record[k]) for k in ("tenant", "repository", "document", "version", "space", "intent")
    )
    context = runtime.authority.authorize(actor, tenant, trace)
    with runtime.repositories.connections.connection(context, trace) as c:
        row = (
            c.execute(sa.select(processing.intents).where(processing.intents.c.id == intent))
            .mappings()
            .one()
        )
        assert row["status"] == "COMPLETE" and row["dispatch_state"] == "DISPATCHED"
        job = row["job_id"]
        publication = (
            c.execute(
                sa.select(processing.publications).where(
                    processing.publications.c.version_id == version,
                    processing.publications.c.space_id == space,
                )
            )
            .mappings()
            .one()
        )
        assert publication["intent_id"] == intent
        chunk_count = c.scalar(
            sa.select(sa.func.count())
            .select_from(processing.chunks)
            .where(processing.chunks.c.version_id == version)
        )
        assert chunk_count > 0
        vectors = vector_table(sa.MetaData(), space, qwen_profile())
        assert (
            c.scalar(
                sa.select(sa.func.count())
                .select_from(vectors)
                .where(vectors.c.version_id == version)
            )
            == chunk_count
        )
        usage = c.execute(
            sa.select(
                sa.func.count(),
                sa.func.sum(processing.batches.c.input_tokens),
                sa.func.sum(processing.batches.c.requests),
            ).where(processing.batches.c.intent_id == intent)
        ).one()
        assert usage[0] > 0 and usage[1] > 0 and usage[2] == usage[0]
        pointer = c.execute(
            sa.select(
                processing.documents.c.original_version_id,
                processing.documents.c.current_version_id,
                processing.documents.c.current_version_kind,
            ).where(processing.documents.c.id == doc)
        ).one()
        assert tuple(pointer) == (UUID(record["original"]), version, "PROCESSED")
        assert (
            c.scalar(
                sa.select(processing.versions.c.state).where(processing.versions.c.id == version)
            )
            == "PUBLISHED"
        )
        runtime.authority.validate(context, trace)
    with control.connect() as c:
        envelope = c.execute(sa.select(jobs).where(jobs.c.id == job)).mappings().one()
        assert (
            envelope["tenant_id"],
            envelope["actor_id"],
            envelope["document_id"],
            envelope["version_id"],
            envelope["space_id"],
            envelope["profile_fingerprint"],
            envelope["kind"],
            envelope["status"],
        ) == (
            tenant,
            actor,
            doc,
            version,
            space,
            qwen_profile().fingerprint(),
            "EMBED",
            "SUCCEEDED",
        )
    base = f"/api/v1/tenants/{tenant}/repositories/{repo}/documents/{doc}"
    metadata = api.json("alice", "GET", base)["document"]
    assert metadata["version_id"] == record["original"]
    body, _ = api.call("alice", "GET", base + "/original")
    assert hashlib.sha256(body).hexdigest() == record["sha256"]
    assert len(body) == record["byte_size"]
    history = api.json("alice", "GET", f"/api/v1/tenants/{tenant}/documents/{doc}/versions")
    assert any(
        v["version_id"] == str(version) and v["state"] == "PUBLISHED" for v in history["items"]
    )
    return dict(
        name=record["name"],
        chunks=chunk_count,
        batches=usage[0],
        input_tokens=usage[1],
        requests=usage[2],
        original_retained=True,
    )


def run(mode):
    global PHASE
    if mode not in ("request", "verify"):
        raise ValueError("Unknown proof mode")
    info = OUT.lstat()
    assert (
        stat.S_ISDIR(info.st_mode)
        and info.st_uid == os.getuid()
        and stat.S_IMODE(info.st_mode) == 0o700
        and OUT.resolve() == OUT
    )
    humans, api, control, runtime = None, None, None, None
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
            profile="embedding_publication",
        )
        runtime.preflight()
        manifest = json.loads(private_file(MANIFEST_ROOT / "manifest.json", 512 * 1024))
        scope = json.loads((ROOT / "ops/f03/application-scope.json").read_text())["fixtures"]
        records = selection(manifest, actors, scope)
        save("selection.json", {"profile": qwen_profile().fingerprint(), "records": records})
        results = []
        for record in records:
            PHASE = record["name"] + "/" + mode.upper()
            # Verify repeats the explicit request to prove its idempotent binding.
            request(runtime, actors["alice"], record)
            if mode == "verify":
                results.append(verify(runtime, control, api, actors["alice"], record))
            print("PASS F05 QWEN " + PHASE + "; no content output.", flush=True)
        if mode == "verify":
            save("verified.json", {"fixtures": results})
            print("PASS F05 QWEN: usage/vectors/publication/ack and original HTTP SHA; 4 fixtures.")
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
    parser.add_argument("mode", choices=("request", "verify"))
    args = parser.parse_args()
    try:
        run(args.mode)
    except Exception as error:
        state = getattr(getattr(error, "orig", error), "sqlstate", None)
        code = state if isinstance(state, str) and re.fullmatch("[A-Z0-9]{5}", state) else "REFUSED"
        print("F05 QWEN " + PHASE + " " + code + "; resources retained.")
        raise SystemExit(1) from None
