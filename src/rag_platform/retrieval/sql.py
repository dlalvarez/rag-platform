"""Filtered tenant-local FTS/vector candidates in one PostgreSQL snapshot."""

import math

import sqlalchemy as sa

from rag_platform.embeddings.processing import ProcessingError, _space
from rag_platform.embeddings.retrieval_sql import (
    SearchError,
    _permitted,
    identifiers,
    query_vector,
)
from rag_platform.embeddings.space_ddl import Vector
from rag_platform.retrieval.contracts import (
    CANDIDATE_LIMIT,
    CitationRef,
    Evidence,
    QueryFilters,
    RetrievalError,
    uuid_value,
)
from rag_platform.retrieval.fusion import fuse

COLUMNS = (
    "repository_id",
    "document_id",
    "version_id",
    "chunk_id",
    "excerpt",
    "page",
    "section",
    "start_offset",
    "end_offset",
)


def eligible(actor, repositories, space, profile, filters, *, include_vector=True):
    if not isinstance(filters, QueryFilters):
        raise RetrievalError("INPUT_INVALID")
    permitted = _permitted(
        actor,
        repositories,
        space,
        profile,
        include_vector=include_vector,
        include_provenance=True,
    )
    conditions = []
    if filters.document_ids:
        conditions.append(permitted.c.document_id.in_(filters.document_ids))
    if filters.version_ids:
        conditions.append(permitted.c.version_id.in_(filters.version_ids))
    if filters.page_min is not None:
        conditions.append(permitted.c.page >= filters.page_min)
    if filters.page_max is not None:
        conditions.append(permitted.c.page <= filters.page_max)
    for index, value in enumerate(filters.section_prefix):
        conditions.append(permitted.c.section[index].as_string() == value)
    return sa.select(*permitted.c).where(*conditions).cte("eligible").prefix_with("MATERIALIZED")


def candidate_statement(actor, repositories, space, profile, vector, query, filters):
    identifiers(actor, repositories, space, CANDIDATE_LIMIT)
    vector = query_vector(profile, vector)
    if not isinstance(query, str) or not query.strip() or not 1 <= len(query) <= 8192:
        raise RetrievalError("INPUT_INVALID")
    allowed = eligible(actor, repositories, space, profile, filters)
    columns = [allowed.c[name] for name in COLUMNS]
    distance = allowed.c.embedding.op("<=>", return_type=sa.Float())(
        sa.cast(
            sa.bindparam("query_vector", vector, type_=Vector(profile.dimension)),
            Vector(profile.dimension),
        )
    )
    vector_candidates = (
        sa.select(*columns, distance.label("raw_score"))
        .order_by(distance, allowed.c.chunk_id)
        .limit(CANDIDATE_LIMIT)
        .cte("vector_candidates")
        .prefix_with("MATERIALIZED")
    )
    # This configuration is trusted, fixed SQL, never a caller-supplied identifier.
    config = sa.literal_column("'simple'::regconfig")
    document = sa.func.to_tsvector(config, allowed.c.text)
    question = sa.func.plainto_tsquery(config, sa.bindparam("lexical_query", query))
    rank = sa.func.ts_rank_cd(document, question, type_=sa.Float())
    lexical_candidates = (
        sa.select(*columns, rank.label("raw_score"))
        .where(document.op("@@", return_type=sa.Boolean())(question))
        .order_by(rank.desc(), allowed.c.chunk_id)
        .limit(CANDIDATE_LIMIT)
        .cte("lexical_candidates")
        .prefix_with("MATERIALIZED")
    )

    def output(candidates, modality, descending):
        score = candidates.c.raw_score
        order = (score.desc() if descending else score, candidates.c.chunk_id)
        return sa.select(
            *(candidates.c[name] for name in COLUMNS),
            score,
            sa.literal(modality).label("modality"),
            sa.func.row_number().over(order_by=order).label("position"),
        )

    return sa.union_all(
        output(vector_candidates, "vector", False),
        output(lexical_candidates, "lexical", True),
    ).order_by("modality", "position")


def evidence_row(row, tenant, space):
    return Evidence(
        CitationRef(
            tenant,
            space,
            row["repository_id"],
            row["document_id"],
            row["version_id"],
            row["chunk_id"],
        ),
        row["excerpt"],
        row["start_offset"],
        row["end_offset"],
        row["page"],
        tuple(row["section"]) if row["section"] else (),
    )


def hybrid(c, tenant, actor, repositories, space, profile, vector, query, top_k, filters):
    """Internal component. Caller must supply an authorized tenant connection/context."""
    uuid_value(tenant)
    identifiers(actor, repositories, space, top_k)
    statement = candidate_statement(actor, repositories, space, profile, vector, query, filters)
    if c.dialect.name != "postgresql":
        raise RetrievalError()
    try:
        _space(c, space, profile)
        candidates = {"vector": [], "lexical": []}
        for row in c.execute(statement).mappings():
            modality = row["modality"]
            if modality not in candidates:
                raise RetrievalError()
            if len(candidates[modality]) >= CANDIDATE_LIMIT:
                raise RetrievalError()
            position = row["position"]
            if type(position) is not int or position != len(candidates[modality]) + 1:
                raise RetrievalError()
            score = float(row["raw_score"])
            if not math.isfinite(score) or (modality == "lexical" and score <= 0):
                raise RetrievalError()
            candidates[modality].append(evidence_row(row, tenant, space))
        return fuse(candidates["vector"], candidates["lexical"], top_k)
    except (ProcessingError, SearchError) as error:
        raise RetrievalError(
            "PROFILE_MISMATCH" if error.code == "PROFILE_MISMATCH" else "DEPENDENCY_UNAVAILABLE"
        ) from None
    except RetrievalError:
        raise
    except Exception:
        raise RetrievalError() from None


def citation_statement(actor, reference, profile):
    if not isinstance(reference, CitationRef):
        raise RetrievalError("INPUT_INVALID")
    identifiers(actor, (reference.repository_id,), reference.space_id, 1)
    allowed = eligible(
        actor,
        (reference.repository_id,),
        reference.space_id,
        profile,
        QueryFilters(document_ids=(reference.document_id,), version_ids=(reference.version_id,)),
        include_vector=False,
    )
    return (
        sa.select(*(allowed.c[name] for name in COLUMNS))
        .where(allowed.c.chunk_id == reference.chunk_id)
        .limit(1)
    )


def resolve(c, tenant, actor, reference, profile):
    """Resolve current published evidence; a reference never substitutes for authorization."""
    uuid_value(tenant)
    if not isinstance(reference, CitationRef) or reference.tenant_id != tenant:
        raise RetrievalError("INPUT_INVALID")
    statement = citation_statement(actor, reference, profile)
    if c.dialect.name != "postgresql":
        raise RetrievalError()
    try:
        _space(c, reference.space_id, profile)
        row = c.execute(statement).mappings().first()
        if row is None:
            raise RetrievalError("NOT_FOUND")
        evidence = evidence_row(row, tenant, reference.space_id)
        if evidence.reference != reference:
            raise RetrievalError("INCONSISTENT_EVIDENCE")
        return evidence
    except (ProcessingError, SearchError) as error:
        raise RetrievalError(
            "PROFILE_MISMATCH" if error.code == "PROFILE_MISMATCH" else "DEPENDENCY_UNAVAILABLE"
        ) from None
    except RetrievalError:
        raise
    except Exception:
        raise RetrievalError() from None
