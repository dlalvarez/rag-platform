"""Bounded filtered HNSW with the same authorized intersection as exact retrieval."""

import math

import sqlalchemy as sa

from rag_platform.embeddings.processing import ProcessingError, _space
from rag_platform.embeddings.publication_schema_f05_0006 import build_metadata
from rag_platform.embeddings.retrieval_sql import (
    Hit,
    SearchError,
    _permitted,
    exact,
    identifiers,
    query_vector,
)
from rag_platform.embeddings.space_ddl import Vector, vector_table


def ann_statement(actor, repositories, space, profile, vector, top_k):
    identifiers(actor, repositories, space, top_k)
    vector = query_vector(profile, vector)
    permitted = _permitted(actor, repositories, space, profile, include_vector=False)
    vectors = vector_table(build_metadata(), space, profile)
    distance = vectors.c.embedding.op("<=>", return_type=sa.Float())(
        sa.cast(
            sa.bindparam("query_vector", vector, type_=Vector(profile.dimension)),
            Vector(profile.dimension),
        )
    )
    # Membership is part of the ordered scan, not a filter on a fixed global window.
    candidates = (
        sa.select(vectors.c.chunk_id, distance.label("distance"))
        .where(vectors.c.chunk_id.in_(sa.select(permitted.c.chunk_id)))
        .order_by(distance)
        .limit(top_k + 1)
        .cte("candidates")
        .prefix_with("MATERIALIZED")
    )
    return (
        sa.select(
            permitted.c.repository_id,
            permitted.c.document_id,
            permitted.c.version_id,
            permitted.c.chunk_id,
            permitted.c.excerpt,
            permitted.c.page,
            permitted.c.section,
            candidates.c.distance,
        )
        .select_from(candidates.join(permitted, candidates.c.chunk_id == permitted.c.chunk_id))
        .order_by(candidates.c.distance, permitted.c.chunk_id)
        .limit(top_k + 1)
    )


def approximate(c, actor, repositories, space, profile, vector, top_k):
    statement = ann_statement(actor, repositories, space, profile, vector, top_k)
    if c.dialect.name != "postgresql":
        raise SearchError("DEPENDENCY_UNAVAILABLE")
    try:
        _space(c, space, profile)
        c.exec_driver_sql("SET LOCAL hnsw.iterative_scan='strict_order'")
        c.exec_driver_sql("SET LOCAL hnsw.ef_search=200")
        c.exec_driver_sql("SET LOCAL hnsw.max_scan_tuples=20000")
        rows = list(c.execute(statement).mappings())
        distances = [float(row["distance"]) for row in rows]
        if any(not math.isfinite(value) for value in distances):
            raise SearchError()
        # Exact resolves selective underfill and globally deterministic boundary ties.
        boundary_tie = len(rows) > top_k and math.isclose(
            distances[top_k - 1], distances[top_k], rel_tol=0, abs_tol=1e-12
        )
        if len(rows) <= top_k or boundary_tie:
            return exact(c, actor, repositories, space, profile, vector, top_k)
        return tuple(
            Hit(
                row["repository_id"],
                row["document_id"],
                row["version_id"],
                row["chunk_id"],
                max(-1.0, min(1.0, 1.0 - distance)),
                row["excerpt"],
                row["page"],
                tuple(row["section"]) if row["section"] else None,
            )
            for row, distance in zip(rows[:top_k], distances[:top_k], strict=True)
        )
    except ProcessingError as error:
        raise SearchError(
            "PROFILE_MISMATCH" if error.code == "PROFILE_MISMATCH" else "DEPENDENCY_UNAVAILABLE"
        ) from None
    except SearchError:
        raise
    except Exception:
        raise SearchError() from None
