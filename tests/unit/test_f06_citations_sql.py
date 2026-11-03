"""Reference resolution keeps publication/ACL checks and does not infer."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from test_f05_retrieval_sql import params

from rag_platform.embeddings.processing import ProcessingError
from rag_platform.retrieval import sql
from rag_platform.retrieval.contracts import CitationRef, RetrievalError


def reference():
    return CitationRef(*(uuid4() for _ in range(6)))


def test_resolver_binds_all_identity_fields_and_preserves_visibility_filters():
    ref = reference()
    actor, _repos, _space, profile, _vector, _top = params()
    statement = sql.citation_statement(actor, ref, profile)
    compiled = statement.compile(dialect=postgresql.dialect())
    text = str(compiled)
    for term in (
        "repository_acl",
        "tombstoned_at IS NULL",
        "current_version_id",
        "embedding_publications",
        "original_version_id",
        "start_offset",
        "end_offset",
        "eligible.chunk_id =",
        "document_id IN",
        "version_id IN",
        "LIMIT",
    ):
        assert term in text
    assert "<=>" not in text and "to_tsvector" not in text and "embedding AS" not in text
    assert str(ref.chunk_id) not in text and str(actor) not in text
    assert ref.chunk_id in compiled.params.values()
    assert (ref.document_id,) in [
        tuple(v) for v in compiled.params.values() if isinstance(v, (list, tuple))
    ]


@pytest.fixture
def connection(monkeypatch):
    rows, queries = [], []

    def execute(statement):
        queries.append(statement)
        return SimpleNamespace(
            mappings=lambda: SimpleNamespace(first=lambda: rows[0] if rows else None)
        )

    c = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"), execute=execute)
    monkeypatch.setattr(sql, "_space", lambda *_args: None)
    return c, rows, queries


def run(c, ref):
    actor, _repos, _space, profile, _vector, _top = params()
    return sql.resolve(c, ref.tenant_id, actor, ref, profile)


def test_existing_reference_returns_actual_provenance(connection):
    c, rows, queries = connection
    ref = reference()
    rows.append(
        dict(
            repository_id=ref.repository_id,
            document_id=ref.document_id,
            version_id=ref.version_id,
            chunk_id=ref.chunk_id,
            excerpt="PRIVATE_CITATION",
            start_offset=0,
            end_offset=16,
            page=None,
            section=["Title"],
        )
    )
    evidence = run(c, ref)
    assert evidence.reference == ref and evidence.excerpt == "PRIVATE_CITATION"
    assert evidence.start_offset == 0 and evidence.end_offset == 16 and len(queries) == 1
    assert "PRIVATE_CITATION" not in repr(evidence)


def test_missing_or_ineligible_reference_fails_closed(connection):
    c, _rows, queries = connection
    with pytest.raises(RetrievalError, match="^NOT_FOUND$"):
        run(c, reference())
    assert len(queries) == 1


def test_cross_tenant_reference_rejected_before_space_or_query(connection, monkeypatch):
    c, _rows, queries = connection
    ref = reference()
    monkeypatch.setattr(sql, "_space", lambda *_args: pytest.fail("unexpected space access"))
    with pytest.raises(RetrievalError, match="^INPUT_INVALID$"):
        sql.resolve(c, uuid4(), uuid4(), ref, params()[3])
    assert queries == []


def test_unknown_profile_prevents_resolution_query(connection, monkeypatch):
    c, _rows, queries = connection

    def failed(*_args):
        raise ProcessingError("PROFILE_MISMATCH")

    monkeypatch.setattr(sql, "_space", failed)
    with pytest.raises(RetrievalError, match="^PROFILE_MISMATCH$"):
        run(c, reference())
    assert queries == []


def test_database_exception_never_echoes_text_or_parameters(connection):
    c, _rows, _queries = connection

    def failed(_statement):
        raise RuntimeError("PRIVATE SQL params")

    c.execute = failed
    with pytest.raises(RetrievalError, match="^DEPENDENCY_UNAVAILABLE$"):
        run(c, reference())


def test_wrong_reference_type_rejected_before_sql(connection):
    c, _rows, queries = connection
    with pytest.raises(RetrievalError, match="^INPUT_INVALID$"):
        sql.resolve(c, uuid4(), uuid4(), "PRIVATE", params()[3])
    assert queries == []


def test_contradictory_backend_reference_is_not_returned(connection):
    c, rows, _queries = connection
    ref = reference()
    rows.append(
        dict(
            repository_id=ref.repository_id,
            document_id=ref.document_id,
            version_id=ref.version_id,
            chunk_id=uuid4(),
            excerpt="PRIVATE_CITATION",
            start_offset=0,
            end_offset=16,
            page=None,
            section=[],
        )
    )
    with pytest.raises(RetrievalError, match="^INCONSISTENT_EVIDENCE$"):
        run(c, ref)
