"""Typed per-space DDL factory. No execution, network or profile selection."""

import math
from numbers import Real
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.types import UserDefinedType

from rag_platform.embeddings.contracts import EmbeddingError, EmbeddingProfile


class Vector(UserDefinedType):
    cache_ok = True

    def __init__(self, dimension):
        if type(dimension) is not int or not 1 <= dimension <= 2000:
            raise EmbeddingError("INPUT_INVALID")
        self.dimension = dimension

    def get_col_spec(self, **kwargs):
        return f"vector({self.dimension})"

    def bind_processor(self, dialect):
        def process(value):
            if not isinstance(value, (tuple, list)) or len(value) != self.dimension:
                raise EmbeddingError("DIMENSION_MISMATCH")
            numbers = []
            for number in value:
                if isinstance(number, bool) or not isinstance(number, Real):
                    raise EmbeddingError("INVALID_VECTOR")
                try:
                    number = float(number)
                except (ValueError, OverflowError):
                    raise EmbeddingError("INVALID_VECTOR") from None
                if not math.isfinite(number) or abs(number) > 3.4028234663852886e38:
                    raise EmbeddingError("INVALID_VECTOR")
                numbers.append(repr(number))
            return "[" + ",".join(numbers) + "]"

        return process


def table_name(space_id):
    if not isinstance(space_id, UUID) or space_id.int == 0:
        raise EmbeddingError("INPUT_INVALID")
    return "embeddings_" + space_id.hex


def space_table(metadata):
    """Administrative immutable catalog; callers must restrict grants before adoption."""
    return sa.Table(
        "embedding_spaces",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("profile_fingerprint", sa.String(64), nullable=False, unique=True),
        sa.Column("provider", sa.String(256), nullable=False),
        sa.Column("model", sa.String(256), nullable=False),
        sa.Column("model_revision", sa.String(256), nullable=False),
        sa.Column("tokenizer", sa.String(256), nullable=False),
        sa.Column("tokenizer_revision", sa.String(256), nullable=False),
        sa.Column("dimension", sa.Integer(), nullable=False),
        sa.Column("metric", sa.String(16), nullable=False),
        sa.Column("normalization", sa.String(8), nullable=False),
        sa.Column("query_prefix", sa.String(128), nullable=False),
        sa.Column("passage_prefix", sa.String(128), nullable=False),
        sa.Column("max_tokens", sa.Integer(), nullable=False),
        sa.Column("max_batch", sa.Integer(), nullable=False),
        sa.Column("adapter_revision", sa.String(256), nullable=False),
        sa.Column("dtype", sa.String(16), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("id", "dimension", "profile_fingerprint", name="f05_space_identity"),
        sa.CheckConstraint("profile_fingerprint ~ '^[0-9a-f]{64}$'", name="f05_space_fingerprint"),
        sa.CheckConstraint("dimension BETWEEN 1 AND 2000", name="f05_space_dimension"),
        sa.CheckConstraint(
            "max_tokens BETWEEN 1 AND 131072 AND max_batch BETWEEN 1 AND 32",
            name="f05_space_limits",
        ),
        sa.CheckConstraint("metric IN ('cosine','l2','inner_product')", name="f05_space_metric"),
        sa.CheckConstraint(
            "normalization IN ('l2','none') AND dtype='float32'", name="f05_space_dtype"
        ),
        schema="knowledge",
    )


def vector_table(metadata, space_id, profile):
    """Build metadata only. No table name/dimension can originate as unchecked SQL."""
    name = table_name(space_id)
    if not isinstance(profile, EmbeddingProfile):
        raise EmbeddingError("INPUT_INVALID")
    # Initial approved F05 search is cosine/L2; other metrics need explicit implementation.
    if profile.metric != "cosine" or profile.normalization != "l2":
        raise EmbeddingError("PROFILE_MISMATCH")
    if "knowledge.embedding_spaces" not in metadata.tables:
        space_table(metadata)
    table = sa.Table(
        name,
        metadata,
        sa.Column("chunk_id", sa.Uuid(), primary_key=True),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("space_id", sa.Uuid(), nullable=False),
        sa.Column("dimension", sa.Integer(), nullable=False),
        sa.Column("profile_fingerprint", sa.String(64), nullable=False),
        sa.Column("embedding", Vector(profile.dimension), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["space_id", "dimension", "profile_fingerprint"],
            [
                "knowledge.embedding_spaces.id",
                "knowledge.embedding_spaces.dimension",
                "knowledge.embedding_spaces.profile_fingerprint",
            ],
            name="f05_vector_space_" + space_id.hex,
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id", "version_id", "document_id", "repository_id"],
            [
                "knowledge.chunks.id",
                "knowledge.chunks.version_id",
                "knowledge.chunks.document_id",
                "knowledge.chunks.repository_id",
            ],
            name="f05_vector_chunk_" + space_id.hex,
        ),
        sa.CheckConstraint(
            f"space_id='{space_id}'::uuid AND dimension={profile.dimension} "
            f"AND profile_fingerprint='{profile.fingerprint()}'",
            name="f05_vector_profile_" + space_id.hex,
        ),
        sa.CheckConstraint(
            "abs(vector_norm(embedding)-1.0)<0.0001",
            name="f05_vector_norm_" + space_id.hex,
        ),
        schema="knowledge",
    )
    sa.Index(
        "hnsw_" + space_id.hex,
        table.c.embedding,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    return table


def build_metadata():
    from rag_platform.ingestion.schema_f04_0003 import build_metadata as historical

    metadata = historical()
    chunks = metadata.tables["knowledge.chunks"]
    chunks.append_constraint(
        sa.UniqueConstraint(
            "id", "version_id", "document_id", "repository_id", name="f05_chunk_identity"
        )
    )
    space_table(metadata)
    return metadata
