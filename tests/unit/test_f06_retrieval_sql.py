"""Shared permissions before both rankings, parameterization and closed failures."""

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy.dialects import postgresql
from test_f05_retrieval_sql import params

from rag_platform.embeddings.processing import ProcessingError
from rag_platform.embeddings.retrieval_sql import _permitted
from rag_platform.retrieval import sql
from rag_platform.retrieval.contracts import QueryFilters, RetrievalError

EMPTY_FILTERS = QueryFilters()


def statement(filters=EMPTY_FILTERS, query="PRIVATE_QUERY --max-connections"):
    actor, repositories, space, profile, vector, _top = params()
    return sql.candidate_statement(actor, repositories, space, profile, vector, query, filters)


def test_shared_permission_set_and_metadata_filters_precede_both_rank_limits():
    document, version = uuid4(), uuid4()
    compiled = statement(QueryFilters((document,), (version,), 2, 8, ("PRIVATE_SECTION",))).compile(
        dialect=postgresql.dialect()
    )
    text = str(compiled)
    for term in (
        "repository_acl",
        "principal_id",
        "tombstoned_at IS NULL",
        "current_version_id",
        "current_version_kind",
        "embedding_publications",
        "original_version_id",
        "profile_fingerprint",
        "start_offset",
        "end_offset",
    ):
        assert term in text
    eligible = text[text.index("eligible AS MATERIALIZED") : text.index("vector_candidates AS")]
    for term in ("document_id IN", "version_id IN", "page >=", "page <=", "section"):
        assert term in eligible
    assert text.index("eligible AS MATERIALIZED") < text.index("vector_candidates AS")
    assert text.index("eligible AS MATERIALIZED") < text.index("lexical_candidates AS")
    assert text.count("LIMIT") == 2 and text.count("UNION ALL") == 1
    assert "FROM eligible" in text and "row_number() OVER" in text
    assert "to_tsvector('simple'::regconfig" in text
    assert "plainto_tsquery('simple'::regconfig" in text
    assert "@@" in text and "ts_rank_cd" in text and "<=>" in text
    assert "PRIVATE_QUERY" not in text and "PRIVATE_SECTION" not in text
    assert str(document) not in text and str(version) not in text
    values = compiled.params.values()
    assert "PRIVATE_QUERY --max-connections" in values and "PRIVATE_SECTION" in values


def test_default_f05_projection_unchanged_and_provenance_opt_in():
    actor, repos, space, profile, _vector, _top = params()
    default = _permitted(actor, repos, space, profile)
    assert list(default.c.keys()) == [
        "repository_id",
        "document_id",
        "version_id",
        "chunk_id",
        "embedding",
        "excerpt",
        "page",
        "section",
    ]
    expanded = _permitted(actor, repos, space, profile, include_provenance=True)
    assert list(expanded.c.keys())[-3:] == ["text", "start_offset", "end_offset"]


@pytest.mark.parametrize("query", ["", "   ", None, "x" * 8193, 3])
def test_invalid_query_never_builds_executable_sql(query):
    with pytest.raises(RetrievalError, match="^INPUT_INVALID$"):
        statement(query=query)


def test_filter_requires_typed_bounded_contract():
    with pytest.raises(RetrievalError, match="^INPUT_INVALID$"):
        statement(filters={"query": "PRIVATE"})


def row(chunk=1, modality="vector", position=1, raw_score=0.1):
    return dict(
        repository_id=UUID(int=11),
        document_id=UUID(int=12),
        version_id=UUID(int=13),
        chunk_id=UUID(int=chunk),
        excerpt="PRIVATE_SQL_EVIDENCE",
        page=2,
        section=["Title"],
        start_offset=10,
        end_offset=100,
        modality=modality,
        position=position,
        raw_score=raw_score,
    )


@pytest.fixture
def connection(monkeypatch):
    rows, executed = [], []

    def execute(statement):
        executed.append(statement)
        return SimpleNamespace(mappings=lambda: iter(rows))

    c = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"), execute=execute)
    monkeypatch.setattr(sql, "_space", lambda *_args: None)
    return c, rows, executed


def retrieve(c):
    actor, repositories, space, profile, vector, _top = params()
    return sql.hybrid(
        c, uuid4(), actor, repositories, space, profile, vector, "query", 3, QueryFilters()
    )


def test_one_snapshot_candidate_rows_fuse_with_provenance(connection):
    c, rows, executed = connection
    rows.extend(
        [
            row(2, "lexical", 1, 0.8),
            row(1, "lexical", 2, 0.4),
            row(1, "vector", 1, 0.1),
            row(3, "vector", 2, 0.2),
        ]
    )
    hits = retrieve(c)
    assert len(executed) == 1 and len(hits) == 3
    assert hits[0].evidence.reference.chunk_id == UUID(int=1)
    assert hits[0].vector_rank == 1 and hits[0].lexical_rank == 2
    assert hits[0].evidence.start_offset == 10 and hits[0].evidence.end_offset == 100
    assert "PRIVATE" not in repr(hits)


def test_no_candidates_is_empty_not_fake_evidence(connection):
    c, _rows, executed = connection
    assert retrieve(c) == () and len(executed) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"position": 2},
        {"position": True},
        {"modality": "unknown"},
        {"raw_score": float("nan")},
        {"raw_score": float("inf")},
        {"modality": "lexical", "raw_score": 0},
        {"modality": "lexical", "raw_score": -0.1},
        {"end_offset": 10},
    ],
)
def test_malformed_backend_rows_fail_closed(connection, changes):
    c, rows, _executed = connection
    rows.append(row() | changes)
    with pytest.raises(RetrievalError) as error:
        retrieve(c)
    assert "PRIVATE" not in str(error.value)


def test_backend_exception_does_not_expose_sql_or_text(connection):
    c, _rows, _executed = connection

    def failed(_statement):
        raise RuntimeError("PRIVATE SQL params and text")

    c.execute = failed
    with pytest.raises(RetrievalError, match="^DEPENDENCY_UNAVAILABLE$"):
        retrieve(c)


def test_profile_rejection_prevents_candidate_query(connection, monkeypatch):
    c, _rows, executed = connection

    def failed(*_args):
        raise ProcessingError("PROFILE_MISMATCH")

    monkeypatch.setattr(sql, "_space", failed)
    with pytest.raises(RetrievalError, match="^PROFILE_MISMATCH$"):
        retrieve(c)
    assert executed == []


def test_candidate_cap_rejected_before_materializing_excess_rows(connection):
    c, rows, _executed = connection
    rows.extend(row(i, position=i) for i in range(1, 52))
    with pytest.raises(RetrievalError, match="^DEPENDENCY_UNAVAILABLE$"):
        retrieve(c)
