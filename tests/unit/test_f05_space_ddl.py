from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from sqlalchemy.dialects.postgresql import dialect
from sqlalchemy.schema import CreateIndex, CreateTable

from rag_platform.embeddings.contracts import EmbeddingError
from rag_platform.embeddings.qwen import qwen_profile
from rag_platform.embeddings.space_ddl import Vector, build_metadata, table_name, vector_table
from rag_platform.ingestion.schema_f04_0003 import build_metadata as historical


@pytest.mark.parametrize("value", ["x; DROP TABLE chunks", None, 1024, UUID(int=0)])
def test_identifier_rejects_untrusted_sql_and_nil_uuid(value):
    with pytest.raises(EmbeddingError, match="INPUT_INVALID"):
        table_name(value)


@pytest.mark.parametrize("value", [True, "1024", 0, 2001, -1])
def test_dimension_must_be_bounded_integer(value):
    with pytest.raises(EmbeddingError, match="INPUT_INVALID"):
        Vector(value)


@pytest.mark.parametrize("value", [[1], [True, 0], [float("nan"), 0], [float("inf"), 0]])
def test_bind_rejects_bad_vector_before_sql(value):
    with pytest.raises(EmbeddingError):
        Vector(2).bind_processor(dialect())(value)


def test_bind_never_interpolates_client_text():
    with pytest.raises(EmbeddingError, match="INVALID_VECTOR"):
        Vector(2).bind_processor(dialect())(["0); DROP TABLE chunks", 1])


def test_space_factory_retains_f04_schema_and_immutable_original_checks():
    before = historical()
    expected = str(
        CreateTable(before.tables["knowledge.document_versions"]).compile(dialect=dialect())
    )
    current = build_metadata()
    assert "knowledge.embedding_spaces" in current.tables
    assert (
        str(
            CreateTable(historical().tables["knowledge.document_versions"]).compile(
                dialect=dialect()
            )
        )
        == expected
    )
    assert "knowledge.embedding_spaces" not in historical().tables


def test_qwen_typed_ddl_has_space_and_provenance_fk_and_hnsw_cosine():
    space = uuid4()
    table = vector_table(build_metadata(), space, qwen_profile())
    ddl = str(CreateTable(table).compile(dialect=dialect()))
    assert "embedding vector(1024) NOT NULL" in ddl
    assert "FOREIGN KEY(chunk_id, version_id, document_id, repository_id)" in ddl
    assert "knowledge.chunks (id, version_id, document_id, repository_id)" in ddl
    assert qwen_profile().fingerprint() in ddl
    assert str(space) in ddl
    index = str(CreateIndex(next(iter(table.indexes))).compile(dialect=dialect()))
    assert "USING hnsw (embedding vector_cosine_ops)" in index


def test_different_spaces_get_separate_tables_and_profile_constants():
    metadata = build_metadata()
    profile = qwen_profile()
    old = vector_table(metadata, uuid4(), profile)
    new = vector_table(metadata, uuid4(), replace(profile, model_revision="other-revision"))
    assert old.name != new.name
    assert str(CreateTable(old).compile(dialect=dialect())) != str(
        CreateTable(new).compile(dialect=dialect())
    )
    assert old.c.embedding.type.dimension == new.c.embedding.type.dimension == 1024


def test_unsupported_metric_cannot_silently_get_cosine_index():
    with pytest.raises(EmbeddingError, match="PROFILE_MISMATCH"):
        vector_table(build_metadata(), uuid4(), replace(qwen_profile(), metric="l2"))
