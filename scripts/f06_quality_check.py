"""Frozen Qwen/SQL F06 baseline; one model, public inputs, all SQL fixtures rolled back."""

import logging
import re
import time
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import f05_publication_check as battery
import f05_sql_quality_check as source
import sqlalchemy as sa
from f04_schema_check import fingerprint, role
from f05_adopt import save
from sqlalchemy.pool import NullPool

from rag_platform.embeddings import processing
from rag_platform.embeddings.qwen import REVISION, LocalQwen, qwen_profile
from rag_platform.embeddings.retrieval_sql import exact
from rag_platform.embeddings.space_ddl import vector_table
from rag_platform.ingestion.logging_setup import local_private_logging
from rag_platform.ingestion.schema_f04_0003 import build_metadata as historical
from rag_platform.retrieval.contracts import QueryFilters, RetrievalError
from rag_platform.retrieval.evaluation import CORPUS_SHA256, evaluate, latency_summary, load_corpus
from rag_platform.retrieval.sql import candidate_statement, hybrid, resolve

PHASE = "START"
RESULTS = []


class TimedProvider:
    def __init__(self, provider):
        self.provider, self.profile, self.query_ms = provider, provider.profile, []

    def embed(self, values, kind):
        started = time.perf_counter()
        result = self.provider.embed(values, kind)
        elapsed = (time.perf_counter() - started) * 1000
        if kind == "query":
            self.query_ms.append(elapsed)
        return result


def prepare(data, provider):
    timed = TimedProvider(provider)
    prepared = source.prepare(data, timed)
    assert len(timed.query_ms) == len(data["queries"])
    expected = (len(data["documents"]) + 3) // 4 + len(data["queries"])
    assert prepared.requests == expected
    return prepared, timed.query_ms


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
                    source.publish(c, names, space, profile, item, prepared)
                    for item in data["documents"]
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
                found = {"vector": {}, "hybrid": {}}
                elapsed = {"vector": [], "hybrid": []}
                citation_count, lexical_checks = 0, 0
                first_ref = None
                role(c, names, "readonly")
                PHASE = fixture_name + "/RETRIEVAL"
                for query in data["queries"]:
                    vector = prepared.queries[query["id"]].vectors[0]
                    started = time.perf_counter()
                    vector_hits = exact(c, actor, repositories, space, profile, vector, 10)
                    elapsed["vector"].append((time.perf_counter() - started) * 1000)
                    started = time.perf_counter()
                    hits = hybrid(
                        c,
                        names.tenant,
                        actor,
                        repositories,
                        space,
                        profile,
                        vector,
                        query["text"],
                        10,
                        QueryFilters(),
                    )
                    elapsed["hybrid"].append((time.perf_counter() - started) * 1000)
                    assert len(vector_hits) == len(hits) == 10
                    assert all(
                        h.repository_id in repositories and h.document_id in doc_gold
                        for h in vector_hits
                    )
                    assert all(
                        h.evidence.reference.repository_id in repositories
                        and h.evidence.reference.document_id in doc_gold
                        and h.evidence.reference.tenant_id == names.tenant
                        for h in hits
                    )
                    found["vector"][query["id"]] = [doc_gold[h.document_id] for h in vector_hits]
                    found["hybrid"][query["id"]] = [
                        doc_gold[h.evidence.reference.document_id] for h in hits
                    ]
                    for hit in hits:
                        evidence = resolve(c, names.tenant, actor, hit.evidence.reference, profile)
                        assert evidence == hit.evidence
                        first_ref = hit.evidence.reference
                        citation_count += 1
                    if query["kind"] == "technical":
                        rows = c.execute(
                            candidate_statement(
                                actor,
                                repositories,
                                space,
                                profile,
                                vector,
                                query["text"],
                                QueryFilters(),
                            )
                        ).mappings()
                        lexical = {
                            doc_gold[r["document_id"]] for r in rows if r["modality"] == "lexical"
                        }
                        assert set(query["relevant"]) <= lexical
                        lexical_checks += 1
                PHASE = fixture_name + "/NEGATIVES"
                vector = next(iter(prepared.queries.values())).vectors[0]
                assert (
                    hybrid(
                        c,
                        names.tenant,
                        uuid4(),
                        repositories,
                        space,
                        profile,
                        vector,
                        "query",
                        10,
                        QueryFilters(),
                    )
                    == ()
                )
                foreign = c.scalar(
                    sa.select(processing.documents.c.repository_id)
                    .where(processing.documents.c.repository_id.not_in(repositories))
                    .limit(1)
                )
                assert foreign is not None
                assert (
                    hybrid(
                        c,
                        names.tenant,
                        actor,
                        (foreign,),
                        space,
                        profile,
                        vector,
                        "query",
                        10,
                        QueryFilters(),
                    )
                    == ()
                )
                try:
                    resolve(c, names.tenant, uuid4(), first_ref, profile)
                except RetrievalError as error:
                    assert error.code == "NOT_FOUND"
                else:
                    raise AssertionError("Unauthorized citation")
                try:
                    hybrid(
                        c,
                        names.tenant,
                        actor,
                        repositories,
                        space,
                        replace(profile, model="f06-other-same-dimension"),
                        vector,
                        "query",
                        10,
                        QueryFilters(),
                    )
                except RetrievalError as error:
                    assert error.code == "PROFILE_MISMATCH"
                else:
                    raise AssertionError("Incompatible model")
                metrics = {mode: evaluate(data, values) for mode, values in found.items()}
                latency = {mode: latency_summary(values) for mode, values in elapsed.items()}
                assert citation_count == len(data["queries"]) * 10 and lexical_checks == 8
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
                    metrics=metrics,
                    sql_latency_ms=latency,
                    query_failures=0,
                    valid_citations=citation_count,
                    technical_fts_checks=lexical_checks,
                    rollback_intact=True,
                )
            )
            print(
                "PASS F06 QUALITY " + fixture_name + ": retrieval/citations/FTS/ACL/rollback.",
                flush=True,
            )
    finally:
        engine.dispose()


def gates(results):
    if len(results) != 4 or {item["name"] for item in results} != {
        "same-a",
        "same-b",
        "two-a",
        "two-b",
    }:
        return False
    return all(
        item["rollback_intact"] is True
        and item["query_failures"] == 0
        and item["valid_citations"] == 400
        and item["technical_fts_checks"] == 8
        and item["metrics"]["hybrid"]["recall_gate_passed"] is True
        and all(value >= 0.8 for value in item["metrics"]["hybrid"]["by_language"].values())
        and set(item["metrics"]["hybrid"]["by_language"]) == {"es", "en"}
        for item in results
    )


def run():
    global PHASE
    data = load_corpus(Path("/app/tests/fixtures/rag-eval/technical-es-en-v1.json"))
    PHASE = "MODEL"
    provider = LocalQwen.load(Path("/models/qwen3-embedding-0.6b") / REVISION)
    prepared, query_ms = prepare(data, provider)
    assert prepared.profile == qwen_profile() and prepared.requests == 44
    battery.run(
        probe=lambda target, names, bootstrap: prove(target, names, bootstrap, data, prepared),
        sources=("f05_tenant_0006",),
    )
    assert len(RESULTS) == 4
    baseline = dict(
        version="f06-baseline-v1",
        fixtures=RESULTS,
        corpus_sha256=CORPUS_SHA256,
        synthetic_only=True,
        profile_fingerprint=prepared.profile.fingerprint(),
        real_provider_requests=prepared.requests,
        real_provider_input_tokens=prepared.tokens,
        query_inference_latency_ms=latency_summary(query_ms),
        ledger_scope="synthetic SQL fixtures; not independent worker usage or billing",
        latency_scope="one pass; model queries measured once, SQL per fixture; not HTTP latency",
        resources=dict(cpu_limit=1.5, memory_gib=6, model_threads=2),
    )
    save("baseline.json", baseline)
    PHASE = "RECALL_GATE"
    assert gates(RESULTS)
    save("verified.json", baseline)
    print("PASS F06 QUALITY: frozen corpus/recall gate/citations four fixtures; no content output.")


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    try:
        run()
    except Exception as error:
        state = getattr(getattr(error, "orig", error), "sqlstate", None)
        code = state if isinstance(state, str) and re.fullmatch("[A-Z0-9]{5}", state) else "REFUSED"
        print("F06 QUALITY " + PHASE + " " + code + "; rollback/resources retained.")
        raise SystemExit(1) from None
