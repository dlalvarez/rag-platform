"""Frozen public Qwen vectors + tenant SQL retrieval, fully rolled back; not worker usage."""

import hashlib
import json
import logging
import math
import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import f05_publication_check as battery
import sqlalchemy as sa
from f04_schema_check import block_rows, candidate, chunk_rows, complete, fingerprint, fixture, role
from f05_adopt import save
from sqlalchemy.pool import NullPool

from rag_platform.embeddings import processing
from rag_platform.embeddings.contracts import EmbeddingBatch, validate
from rag_platform.embeddings.queue import EmbeddingClaim
from rag_platform.embeddings.qwen import REVISION, LocalQwen, qwen_profile
from rag_platform.embeddings.retrieval_ann import approximate
from rag_platform.embeddings.retrieval_sql import SearchError, exact
from rag_platform.embeddings.space_ddl import vector_table
from rag_platform.ingestion.extraction import NORMALIZER, PARSERS, ChunkConfig, from_wire
from rag_platform.ingestion.logging_setup import local_private_logging
from rag_platform.ingestion.schema import audit, blocks, chunks, versions
from rag_platform.ingestion.schema_f04_0003 import build_metadata as historical

CORPUS_SHA = "ca4d53dd72713febe740eebd958b384aae6dd9f2793c8433314c224b3284340e"
PHASE = "START"
RESULTS = []


def corpus(path):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != CORPUS_SHA:
        raise ValueError("Frozen corpus mismatch")
    value = json.loads(raw)
    assert value["synthetic"] and len(value["documents"]) == len(value["queries"]) == 16
    ids = {d["id"] for d in value["documents"]}
    assert len(ids) == 16
    assert {q["language"] for q in value["queries"]} == {"es", "en"}
    assert all(q["relevant"] and set(q["relevant"]) <= ids for q in value["queries"])
    return value


def parsed(text):
    return from_wire(
        {
            "version": 1,
            "parser": PARSERS["text/plain"],
            "normalizer": NORMALIZER,
            "page_count": None,
            "blocks": [{"text": text, "page": None, "section": ["Frozen gold"], "kind": "text"}],
        },
        "text/plain",
    )


@dataclass(repr=False)
class Prepared:
    profile: object
    passages: dict
    queries: dict
    texts: dict
    requests: int
    tokens: int

    def __repr__(self):
        return "PreparedPublicQualityVectors(<memory only>)"


def prepare(data, provider):
    # This runs before opening any control/tenant SQL connection. Public fixture only.
    texts = {item["id"]: parsed(item["text"]).text for item in data["documents"]}
    passages, queries, requests, tokens = {}, {}, 0, 0
    docs = data["documents"]
    for offset in range(0, len(docs), 4):
        items = docs[offset : offset + 4]
        values = tuple(texts[item["id"]] for item in items)
        batch = validate(provider.profile, values, "passage", provider.embed(values, "passage"))
        requests += 1
        tokens += batch.total_tokens
        for item, vector, count in zip(items, batch.vectors, batch.input_tokens, strict=True):
            passages[item["id"]] = EmbeddingBatch(batch.profile_fingerprint, (vector,), (count,))
    for item in data["queries"]:
        values = (item["text"],)
        batch = validate(provider.profile, values, "query", provider.embed(values, "query"))
        queries[item["id"]] = batch
        requests += 1
        tokens += batch.total_tokens
    return Prepared(provider.profile, passages, queries, texts, requests, tokens)


def recall(found, gold):
    if not gold:
        raise ValueError("Nonempty gold required")
    return len(set(found) & set(gold)) / len(set(gold))


def means(values):
    if set(values) != {"es", "en"} or any(not scores for scores in values.values()):
        raise ValueError("Both languages required")
    result = {language: math.fsum(scores) / len(scores) for language, scores in values.items()}
    if any(not math.isfinite(score) or not 0 <= score <= 1 for score in result.values()):
        raise ValueError("Invalid recall")
    return result


def publish(c, names, space, profile, item, prepared):
    # SQL-only original/guard/ledger fixture; not S3, independent commits or real worker usage.
    f = fixture(c)
    config = ChunkConfig(512, 64)
    version, _unused = candidate(
        c,
        f,
        chunk_size=config.size,
        chunk_overlap=config.overlap,
        config_hash=config.fingerprint("text/plain"),
    )
    c.execute(versions.update().where(versions.c.id == version).values(state="CHUNKING"))
    data = parsed(item["text"])
    rows = chunk_rows(f, version, data, config)
    assert len(rows) == 1 and rows[0]["text"] == prepared.texts[item["id"]]
    c.execute(blocks.insert(), block_rows(f, version, data))
    c.execute(chunks.insert(), rows)
    c.execute(complete(version, data, rows))
    c.execute(
        audit.insert().values(
            id=uuid4(),
            principal_id=f["actor"],
            repository_id=f["repo"],
            target_id=version,
            request_id=uuid4(),
            action="INGESTION_READY",
            outcome="OK",
        )
    )
    c.exec_driver_sql("SET CONSTRAINTS ALL IMMEDIATE")
    c.exec_driver_sql("SET CONSTRAINTS ALL DEFERRED")
    plan = processing.request(c, f["actor"], f["repo"], f["doc"], version, profile)
    assert plan.space_id == space
    claim = EmbeddingClaim(
        uuid4(),
        names.tenant,
        f["actor"],
        f["doc"],
        version,
        1,
        uuid4(),
        space,
        profile.fingerprint(),
    )
    guard = SimpleNamespace(
        claim=claim, intent_id=plan.id, check=lambda: datetime.now(UTC) + timedelta(seconds=180)
    )
    processing.start(c, guard, profile)
    task = processing.next_batch(c, guard, profile)
    assert task is not None and task.texts == (prepared.texts[item["id"]],)
    processing.save_batch(c, guard, profile, task, prepared.passages[item["id"]], 1)
    assert processing.next_batch(c, guard, profile) is None
    processing.complete(c, guard, profile)
    return f


def prove(target, names, bootstrap, data, prepared):
    global PHASE
    engine = sa.create_engine(
        "postgresql+psycopg://",
        creator=lambda: target.connect(names.database, bootstrap),
        poolclass=NullPool,
        hide_parameters=True,
    )
    profile = prepared.profile
    tables = list(historical().tables.values())
    fixture_name = ("same-a", "same-b", "two-a", "two-b")[len(RESULTS)]
    try:
        with engine.connect() as c:
            outer = c.begin()
            try:
                local_private_logging(c)
                c.exec_driver_sql("SET LOCAL lock_timeout='5s'")
                c.exec_driver_sql("SET LOCAL statement_timeout='20s'")
                before = fingerprint(c, tables)
                prior = c.scalar(sa.text("SELECT version_num FROM public.alembic_version_tenant"))
                assert prior == "f05_tenant_0006"
                space = c.scalar(
                    sa.select(processing.spaces.c.id).where(
                        processing.spaces.c.profile_fingerprint == profile.fingerprint()
                    )
                )
                processing._space(c, space, profile)
                vectors = vector_table(sa.MetaData(), space, profile)
                vector_count = c.scalar(sa.select(sa.func.count()).select_from(vectors))
                publication_count = c.scalar(
                    sa.select(sa.func.count()).select_from(processing.publications)
                )
                role(c, names, "app")
                PHASE = fixture_name + "/FIXTURES"
                fixtures = [
                    publish(c, names, space, profile, item, prepared) for item in data["documents"]
                ]
                actor = fixtures[0]["actor"]
                for f in fixtures[1:]:
                    c.execute(
                        sa.text(
                            "INSERT INTO security.repository_acl(repository_id,principal_id,role) "
                            "VALUES(:repo,:actor,'reader')"
                        ),
                        {"repo": f["repo"], "actor": actor},
                    )
                repositories = tuple(f["repo"] for f in fixtures)
                doc_gold = {
                    f["doc"]: item["id"]
                    for f, item in zip(fixtures, data["documents"], strict=True)
                }
                scores = {mode: {"es": [], "en": []} for mode in ("exact", "ann")}
                overlap = []
                role(c, names, "readonly")
                PHASE = fixture_name + "/RETRIEVAL"
                for query in data["queries"]:
                    vector = prepared.queries[query["id"]].vectors[0]
                    found = {}
                    for mode, search in (("exact", exact), ("ann", approximate)):
                        hits = search(c, actor, repositories, space, profile, vector, 3)
                        assert len(hits) == 3
                        assert all(
                            hit.repository_id in repositories and hit.document_id in doc_gold
                            for hit in hits
                        )
                        found[mode] = {doc_gold[hit.document_id] for hit in hits}
                        scores[mode][query["language"]].append(
                            recall(found[mode], query["relevant"])
                        )
                        assert search(c, uuid4(), repositories, space, profile, vector, 3) == ()
                        assert search(c, actor, (uuid4(),), space, profile, vector, 3) == ()
                    overlap.append(recall(found["ann"], found["exact"]))
                foreign = c.scalar(
                    sa.select(processing.documents.c.repository_id)
                    .where(processing.documents.c.repository_id.not_in(repositories))
                    .limit(1)
                )
                assert foreign is not None
                vector = next(iter(prepared.queries.values())).vectors[0]
                for search in (exact, approximate):
                    assert search(c, actor, (foreign,), space, profile, vector, 3) == ()
                    try:
                        search(
                            c,
                            actor,
                            repositories,
                            space,
                            replace(profile, model="quality-other-same-dimension"),
                            vector,
                            3,
                        )
                    except SearchError as error:
                        assert error.code == "PROFILE_MISMATCH"
                    else:
                        raise AssertionError("Incompatible model accepted")
                metrics = {mode: means(values) for mode, values in scores.items()}
                assert all(v >= 0.8 for modes in metrics.values() for v in modes.values())
                assert math.fsum(overlap) / len(overlap) >= 0.8
            finally:
                outer.rollback()
            PHASE = fixture_name + "/ROLLBACK"
            assert fingerprint(c, tables) == before
            assert (
                c.scalar(sa.text("SELECT version_num FROM public.alembic_version_tenant")) == prior
            )
            assert c.scalar(sa.select(sa.func.count()).select_from(vectors)) == vector_count
            assert (
                c.scalar(sa.select(sa.func.count()).select_from(processing.publications))
                == publication_count
            )
            RESULTS.append(
                dict(
                    name=fixture_name,
                    recall_at_3=metrics,
                    ann_overlap_at_3=math.fsum(overlap) / len(overlap),
                    rollback_intact=True,
                )
            )
            print(
                "PASS F05 QUALITY " + fixture_name + ": ES/EN exact/ANN/ACL/rollback.", flush=True
            )
    finally:
        engine.dispose()


def run():
    global PHASE
    data = corpus(Path("/app/tests/fixtures/f05/retrieval-es-en.json"))
    PHASE = "MODEL"
    provider = LocalQwen.load(Path("/models/qwen3-embedding-0.6b") / REVISION)
    prepared = prepare(data, provider)
    assert prepared.profile == qwen_profile() and prepared.requests == 20
    battery.run(
        probe=lambda target, names, bootstrap: prove(target, names, bootstrap, data, prepared),
        sources=("f05_tenant_0006",),
    )
    assert len(RESULTS) == 4
    save(
        "verified.json",
        dict(
            fixtures=RESULTS,
            corpus_sha256=CORPUS_SHA,
            synthetic_only=True,
            real_provider_requests=prepared.requests,
            real_provider_input_tokens=prepared.tokens,
            ledger_scope="synthetic SQL fixtures; not independent worker usage",
        ),
    )
    print("PASS F05 QUALITY: frozen public corpus, Qwen/SQL four fixtures; no content output.")


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    try:
        run()
    except Exception as error:
        state = getattr(getattr(error, "orig", error), "sqlstate", None)
        code = state if isinstance(state, str) and re.fullmatch("[A-Z0-9]{5}", state) else "REFUSED"
        print("F05 QUALITY " + PHASE + " " + code + "; rollback/resources retained.")
        raise SystemExit(1) from None
