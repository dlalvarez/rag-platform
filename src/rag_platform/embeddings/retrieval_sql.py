"""Tenant-local exact vector retrieval. No inference, DDL, network or context creation."""

import math
from dataclasses import dataclass
from numbers import Real
from uuid import UUID

import sqlalchemy as sa

from rag_platform.embeddings.contracts import EmbeddingProfile
from rag_platform.embeddings.processing import ProcessingError, _space
from rag_platform.embeddings.publication_schema_f05_0006 import build_metadata
from rag_platform.embeddings.space_ddl import Vector, vector_table


class SearchError(RuntimeError):
    CODES = {"INPUT_INVALID", "PROFILE_MISMATCH", "DEPENDENCY_UNAVAILABLE"}

    def __init__(self, code="DEPENDENCY_UNAVAILABLE"):
        self.code = (
            code if isinstance(code, str) and code in self.CODES else "DEPENDENCY_UNAVAILABLE"
        )
        super().__init__(self.code)


@dataclass(frozen=True, slots=True, repr=False)
class Hit:
    repository_id: UUID
    document_id: UUID
    version_id: UUID
    chunk_id: UUID
    score: float
    excerpt: str
    page: int | None
    section: tuple[str, ...] | None

    def __repr__(self):
        return "SearchHit(<private evidence>)"


def identifiers(actor, repositories, space, top_k):
    if (
        not isinstance(repositories, (tuple, list))
        or not 1 <= len(repositories) <= 16
        or any(not isinstance(v, UUID) or v.int == 0 for v in (actor, space, *repositories))
        or len(set(repositories)) != len(repositories)
        or type(top_k) is not int
        or not 1 <= top_k <= 50
    ):
        raise SearchError("INPUT_INVALID")


def query_vector(profile, vector):
    if (
        not isinstance(profile, EmbeddingProfile)
        or profile.metric != "cosine"
        or profile.normalization != "l2"
    ):
        raise SearchError("PROFILE_MISMATCH")
    if (
        not isinstance(vector, (tuple, list))
        or len(vector) != profile.dimension
        or any(isinstance(v, bool) or not isinstance(v, Real) for v in vector)
    ):
        raise SearchError("INPUT_INVALID")
    try:
        values = tuple(float(v) for v in vector)
        if any(not math.isfinite(v) for v in values):
            raise ValueError()
        if abs(math.sqrt(math.fsum(v * v for v in values)) - 1.0) >= 0.0001:
            raise ValueError()
    except (ValueError, OverflowError):
        raise SearchError("INPUT_INVALID") from None
    return values


def _permitted(
    actor, repositories, space, profile, *, include_vector=True, include_provenance=False
):
    metadata = build_metadata()
    vectors = vector_table(metadata, space, profile)
    chunks = metadata.tables["knowledge.chunks"]
    versions = metadata.tables["knowledge.document_versions"]
    documents = metadata.tables["knowledge.documents"]
    published = metadata.tables["knowledge.embedding_publications"]
    repos = metadata.tables["knowledge.repositories"]
    acl = metadata.tables["security.repository_acl"]
    joined = (
        vectors.join(
            chunks,
            sa.and_(
                chunks.c.id == vectors.c.chunk_id,
                chunks.c.version_id == vectors.c.version_id,
                chunks.c.document_id == vectors.c.document_id,
                chunks.c.repository_id == vectors.c.repository_id,
            ),
        )
        .join(
            versions,
            sa.and_(
                versions.c.id == vectors.c.version_id,
                versions.c.document_id == vectors.c.document_id,
                versions.c.repository_id == vectors.c.repository_id,
            ),
        )
        .join(
            documents,
            sa.and_(
                documents.c.id == vectors.c.document_id,
                documents.c.repository_id == vectors.c.repository_id,
                documents.c.current_version_id == vectors.c.version_id,
            ),
        )
        .join(
            published,
            sa.and_(
                published.c.space_id == vectors.c.space_id,
                published.c.profile_fingerprint == vectors.c.profile_fingerprint,
                published.c.version_id == vectors.c.version_id,
                published.c.document_id == vectors.c.document_id,
                published.c.repository_id == vectors.c.repository_id,
            ),
        )
        .join(repos, repos.c.id == vectors.c.repository_id)
        .join(acl, acl.c.repository_id == vectors.c.repository_id)
    )
    return (
        sa.select(
            vectors.c.repository_id,
            vectors.c.document_id,
            vectors.c.version_id,
            vectors.c.chunk_id,
            *((vectors.c.embedding,) if include_vector else ()),
            sa.func.left(chunks.c.text, 512).label("excerpt"),
            chunks.c.page,
            chunks.c.section,
            *(
                (chunks.c.text, chunks.c.start_offset, chunks.c.end_offset)
                if include_provenance
                else ()
            ),
        )
        .select_from(joined)
        .where(
            vectors.c.space_id == space,
            vectors.c.profile_fingerprint == profile.fingerprint(),
            vectors.c.dimension == profile.dimension,
            vectors.c.repository_id.in_(tuple(repositories)),
            acl.c.principal_id == actor,
            acl.c.role.in_(("owner", "admin", "editor", "reader")),
            repos.c.state == "ACTIVE",
            documents.c.state == "RECEIVED",
            documents.c.tombstoned_at.is_(None),
            documents.c.current_version_kind == "PROCESSED",
            versions.c.kind == "PROCESSED",
            versions.c.state == "PUBLISHED",
            versions.c.original_version_id == documents.c.original_version_id,
        )
        .cte("permitted")
        .prefix_with("MATERIALIZED")
    )


def exact_statement(actor, repositories, space, profile, vector, top_k):
    """Internal only: callers supply a validated context and trusted query embedding.

    The ACL/pointer/publication intersection is materialized before ranking. This is
    the exact reference, deliberately independent of any HNSW candidate limit.
    """
    identifiers(actor, repositories, space, top_k)
    vector = query_vector(profile, vector)
    permitted = _permitted(actor, repositories, space, profile)
    distance = permitted.c.embedding.op("<=>", return_type=sa.Float())(
        sa.cast(
            sa.bindparam("query_vector", vector, type_=Vector(profile.dimension)),
            Vector(profile.dimension),
        )
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
            distance.label("distance"),
        )
        .order_by(distance, permitted.c.chunk_id)
        .limit(top_k)
    )


def exact(c, actor, repositories, space, profile, vector, top_k):
    """Read component only. Context/schema authority must be enforced by its caller."""
    statement = exact_statement(actor, repositories, space, profile, vector, top_k)
    if c.dialect.name != "postgresql":
        raise SearchError("DEPENDENCY_UNAVAILABLE")
    try:
        _space(c, space, profile)
        hits = []
        for row in c.execute(statement).mappings():
            distance = float(row["distance"])
            if not math.isfinite(distance):
                raise SearchError()
            hits.append(
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
            )
        return tuple(hits)
    except ProcessingError as error:
        raise SearchError(
            "PROFILE_MISMATCH" if error.code == "PROFILE_MISMATCH" else "DEPENDENCY_UNAVAILABLE"
        ) from None
    except SearchError:
        raise
    except Exception:
        raise SearchError() from None
