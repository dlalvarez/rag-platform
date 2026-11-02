"""Exact backend rejects untrusted shape and binds private vectors as parameters."""

from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from rag_platform.embeddings.fixture import fixture_profile
from rag_platform.embeddings.retrieval_sql import Hit, SearchError, exact_statement


def params():
    return [uuid4(), (uuid4(),), uuid4(), fixture_profile(), (1.0, 0.0, 0.0), 3]


@pytest.mark.parametrize(
    "index,value",
    [
        (0, "untrusted-actor"),
        (1, ()),
        (1, ("repo; DROP TABLE knowledge.documents",)),
        (2, "space; DROP TABLE knowledge.documents"),
        (5, True),
        (5, 0),
        (5, 51),
        (4, (0.0, 0.0, 0.0)),
        (4, (float("nan"), 0.0, 0.0)),
        (4, (float("inf"), 0.0, 0.0)),
        (4, (True, 0.0, 0.0)),
        (4, (1.0, 0.0)),
    ],
)
def test_invalid_shape_rejected_without_echoing_arguments(index, value):
    args = params()
    args[index] = value
    with pytest.raises(SearchError, match="INPUT_INVALID") as error:
        exact_statement(*args)
    assert str(error.value) == "INPUT_INVALID"


def test_duplicate_repositories_refused():
    args = params()
    repo = uuid4()
    args[1] = (repo, repo)
    with pytest.raises(SearchError):
        exact_statement(*args)


def test_private_vector_and_actor_are_bound_not_interpolated():
    args = params()
    statement = exact_statement(*args)
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert str(args[0]) not in sql and str(args[1][0]) not in sql
    assert compiled.params["query_vector"] == args[4]
    assert "MATERIALIZED" in sql and "<=>" in sql
    assert sql.index("WHERE") < sql.index("ORDER BY") < sql.index("LIMIT")


def test_hit_representation_hides_evidence():
    hit = Hit(uuid4(), uuid4(), uuid4(), uuid4(), 1.0, "PRIVATE_EVIDENCE", 1, None)
    assert "PRIVATE_EVIDENCE" not in repr(hit)
