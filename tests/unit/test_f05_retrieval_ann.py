"""Filtered ANN SQL shape, bounded settings and correctness fallbacks, offline."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from test_f05_retrieval_sql import params

from rag_platform.embeddings import retrieval_ann as ann
from rag_platform.embeddings.processing import ProcessingError
from rag_platform.embeddings.retrieval_sql import SearchError


def test_ann_has_shared_permissions_inside_ordered_scan_and_bound_vector():
    args = params()
    statement = ann.ann_statement(*args)
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert compiled.params["query_vector"] == args[4]
    assert str(args[0]) not in sql and str(args[1][0]) not in sql
    for text in (
        "repository_acl",
        "tombstoned_at IS NULL",
        "current_version_id",
        "embedding_publications",
        "original_version_id",
        "MATERIALIZED",
        "IN (SELECT permitted.chunk_id",
        "<=>",
    ):
        assert text in sql
    candidate = sql[sql.index("candidates AS MATERIALIZED") :]
    assert candidate.index("IN (SELECT") < candidate.index("ORDER BY") < candidate.index("LIMIT")
    assert list(compiled.params.values()).count(args[-1] + 1) == 2


@pytest.fixture
def connection(monkeypatch):
    commands, rows = [], []
    c = SimpleNamespace(
        dialect=SimpleNamespace(name="postgresql"),
        exec_driver_sql=commands.append,
        execute=lambda _statement: SimpleNamespace(mappings=lambda: rows),
    )
    monkeypatch.setattr(ann, "_space", lambda *_args: None)
    return c, commands, rows


def row(distance):
    return dict(
        repository_id=uuid4(),
        document_id=uuid4(),
        version_id=uuid4(),
        chunk_id=uuid4(),
        excerpt="PRIVATE_ANN",
        page=None,
        section=["Title"],
        distance=distance,
    )


@pytest.mark.parametrize("distances", [[], [0.1], [0.1, 0.2], [0.1, 0.2, 0.2]])
def test_underfill_or_boundary_tie_uses_authorized_exact(connection, monkeypatch, distances):
    c, commands, rows = connection
    args = params()
    args[-1] = 2
    rows.extend(row(d) for d in distances)
    called = []
    sentinel = object()
    monkeypatch.setattr(ann, "exact", lambda *a: called.append(a) or sentinel)
    assert ann.approximate(c, *args) is sentinel
    assert called == [(c, *args)]
    assert commands == [
        "SET LOCAL hnsw.iterative_scan='strict_order'",
        "SET LOCAL hnsw.ef_search=200",
        "SET LOCAL hnsw.max_scan_tuples=20000",
    ]


def test_full_candidate_set_returns_only_authorized_hits(connection, monkeypatch):
    c, _commands, rows = connection
    rows.extend([row(0.1), row(0.2), row(0.3), row(0.4)])
    monkeypatch.setattr(ann, "exact", lambda *_args: pytest.fail("unexpected exact fallback"))
    hits = ann.approximate(c, *params())
    assert len(hits) == 3 and hits[0].score == pytest.approx(0.9)
    assert hits[0].section == ("Title",)
    assert "PRIVATE_ANN" not in repr(hits[0])


@pytest.mark.parametrize("distance", [float("nan"), float("inf")])
def test_invalid_distance_fails_closed(connection, distance):
    c, _commands, rows = connection
    rows.append(row(distance))
    with pytest.raises(SearchError) as error:
        ann.approximate(c, *params())
    assert str(error.value) == "DEPENDENCY_UNAVAILABLE"


def test_other_model_same_dimension_fails_before_scan(connection, monkeypatch):
    c, commands, _rows = connection

    def mismatch(*_args):
        raise ProcessingError("PROFILE_MISMATCH")

    monkeypatch.setattr(ann, "_space", mismatch)
    with pytest.raises(SearchError, match="PROFILE_MISMATCH"):
        ann.approximate(c, *params())
    assert commands == []


def test_non_postgresql_refused_before_sql(connection):
    c, commands, _rows = connection
    c.dialect.name = "sqlite"
    with pytest.raises(SearchError, match="DEPENDENCY_UNAVAILABLE"):
        ann.approximate(c, *params())
    assert commands == []


@pytest.mark.parametrize(
    "index,value",
    [
        (0, "untrusted"),
        (1, ()),
        (2, "table;DROP"),
        (4, (0.0, 0.0, 0.0)),
        (5, True),
        (5, 51),
    ],
)
def test_ann_rejects_untrusted_shape(index, value):
    args = params()
    args[index] = value
    with pytest.raises(SearchError, match="INPUT_INVALID"):
        ann.ann_statement(*args)


def test_native_explain_wrapper_preserves_bound_parameters():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    from f05_ann_check import Explain

    args = params()
    compiled = Explain(ann.ann_statement(*args)).compile(dialect=postgresql.dialect())
    assert str(compiled).startswith("EXPLAIN (FORMAT JSON) WITH")
    assert compiled.params["query_vector"] == args[4]
    assert str(args[0]) not in str(compiled)
