"""Synthetic ANN/filter/reference SQL probe; all DDL/data rolled back, no Qwen."""

import logging
import math
import re
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import f05_publication_check as battery
import f05_retrieval_check as reference
import sqlalchemy as sa
from f04_schema_check import complete, fixture, stage
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.expression import ClauseElement, Executable

from rag_platform.embeddings import processing
from rag_platform.embeddings.contracts import EmbeddingBatch
from rag_platform.embeddings.queue import EmbeddingClaim
from rag_platform.embeddings.retrieval_ann import ann_statement, approximate
from rag_platform.embeddings.retrieval_sql import exact
from rag_platform.embeddings.space_ddl import vector_table
from rag_platform.ingestion.schema import audit

COUNTS = dict(comparisons=0, index_plans=0, selective_filters=0)


class Explain(Executable, ClauseElement):
    inherit_cache = False

    def __init__(self, statement):
        self.statement = statement


@compiles(Explain)
def explain(element, compiler, **kwargs):
    return "EXPLAIN (FORMAT JSON) " + compiler.process(element.statement, **kwargs)


def compared(c, *args):
    candidate, baseline = approximate(c, *args), exact(c, *args)
    assert [h.chunk_id for h in candidate] == [h.chunk_id for h in baseline]
    assert all(
        math.isclose(a.score, b.score, abs_tol=1e-6)
        for a, b in zip(candidate, baseline, strict=True)
    )
    COUNTS["comparisons"] += 1
    return candidate


def index_names(value):
    if isinstance(value, dict):
        return ([value["Index Name"]] if "Index Name" in value else []) + [
            name for item in value.values() for name in index_names(item)
        ]
    if isinstance(value, list):
        return [name for item in value for name in index_names(item)]
    return []


def selective(c, names, space, profile, allowed, embedded):
    reference.PHASE = "SELECTIVE_FIXTURES"
    # More than 40 closer vectors belong to foreign repositories without this actor's ACL.
    query, foreign = (1.0, 0.0, 0.0), 0
    for _ in range(16):
        f = fixture(c)
        version, _config, data, rows = stage(c, f)
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
        while True:
            task = processing.next_batch(c, guard, profile)
            if task is None:
                break
            response = EmbeddingBatch(
                profile.fingerprint(),
                tuple(query for _ in task.texts),
                tuple(1 for _ in task.texts),
            )
            processing.save_batch(c, guard, profile, task, response, 1)
            foreign += len(task.chunk_ids)
        processing.complete(c, guard, profile)
    reference.PHASE = "GLOBAL_WINDOW_FILTER"
    assert foreign > 40
    vectors = vector_table(sa.MetaData(), space, profile)
    distance = vectors.c.embedding.op("<=>", return_type=sa.Float())(
        sa.cast(
            sa.bindparam("probe_vector", query, type_=vectors.c.embedding.type),
            vectors.c.embedding.type,
        )
    )
    global_window = set(c.scalars(sa.select(vectors.c.chunk_id).order_by(distance).limit(40)))
    assert not global_window.intersection(embedded)
    args = (allowed["actor"], (allowed["repo"],), space, profile, query, 3)
    reference.PHASE = "SELECTIVE_COMPARE"
    hits = compared(c, *args)
    reference.PHASE = "SELECTIVE_COVERAGE"
    assert len(hits) == 3 and all(hit.repository_id == allowed["repo"] for hit in hits)
    COUNTS["selective_filters"] += 1
    # A forced test plan demonstrates index eligibility; production planner is not forced.
    reference.PHASE = "INDEX_PLAN"
    with c.begin_nested() as temporary:
        c.exec_driver_sql("SET LOCAL enable_seqscan=off")
        plan = c.execute(Explain(ann_statement(*args))).scalar_one()
        assert "hnsw_" + space.hex in index_names(plan)
        # Execute the eligible path too, rather than asserting EXPLAIN alone.
        assert len(compared(c, *args)) == 3
        temporary.rollback()
    COUNTS["index_plans"] += 1


def prove(target, names, bootstrap):
    reference.prove(target, names, bootstrap, retrieve=compared, after_publication=selective)


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    try:
        battery.run(probe=prove, sources=("f05_tenant_0004", "f05_tenant_0006"))
        assert COUNTS["index_plans"] == COUNTS["selective_filters"] == 4
        print("PASS F05 ANN: four index plans/selective filters, exact comparison and rollback.")
    except Exception as error:
        state = getattr(getattr(error, "orig", error), "sqlstate", None)
        code = state if isinstance(state, str) and re.fullmatch("[A-Z0-9]{5}", state) else "REFUSED"
        print(
            "F05 ANN "
            + reference.PHASE
            + " "
            + code
            + " "
            + type(error).__name__
            + "; rollback/resources retained."
        )
        raise SystemExit(1) from None
