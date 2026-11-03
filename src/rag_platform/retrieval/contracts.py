"""Bounded internal F06 evidence. No SQL, inference, HTTP or context creation."""

import math
from dataclasses import dataclass
from uuid import UUID

RRF_REVISION = "f06-rrf-k60-v1"
RRF_K = 60
CANDIDATE_LIMIT = 50


class RetrievalError(RuntimeError):
    CODES = {"INPUT_INVALID", "INCONSISTENT_EVIDENCE", "DEPENDENCY_UNAVAILABLE"}

    def __init__(self, code="DEPENDENCY_UNAVAILABLE"):
        self.code = (
            code if isinstance(code, str) and code in self.CODES else "DEPENDENCY_UNAVAILABLE"
        )
        super().__init__(self.code)


def uuid_value(value):
    if not isinstance(value, UUID) or value.int == 0:
        raise RetrievalError("INPUT_INVALID")


def identifiers(values, maximum=32):
    if (
        type(values) is not tuple
        or len(values) > maximum
        or any(not isinstance(v, UUID) or v.int == 0 for v in values)
        or len(set(values)) != len(values)
    ):
        raise RetrievalError("INPUT_INVALID")


def section_path(value):
    if (
        type(value) is not tuple
        or len(value) > 16
        or any(
            not isinstance(v, str)
            or not 1 <= len(v) <= 256
            or any(ord(c) < 32 or ord(c) == 127 for c in v)
            for v in value
        )
    ):
        raise RetrievalError("INPUT_INVALID")


@dataclass(frozen=True, slots=True, repr=False)
class QueryFilters:
    document_ids: tuple[UUID, ...] = ()
    version_ids: tuple[UUID, ...] = ()
    page_min: int | None = None
    page_max: int | None = None
    section_prefix: tuple[str, ...] = ()

    def __post_init__(self):
        identifiers(self.document_ids)
        identifiers(self.version_ids)
        section_path(self.section_prefix)
        for value in (self.page_min, self.page_max):
            if value is not None and (type(value) is not int or not 1 <= value <= 2_000_000):
                raise RetrievalError("INPUT_INVALID")
        if (
            self.page_min is not None
            and self.page_max is not None
            and self.page_min > self.page_max
        ):
            raise RetrievalError("INPUT_INVALID")

    def __repr__(self):
        return "QueryFilters(<private selection>)"


@dataclass(frozen=True, slots=True, repr=False)
class CitationRef:
    tenant_id: UUID
    space_id: UUID
    repository_id: UUID
    document_id: UUID
    version_id: UUID
    chunk_id: UUID

    def __post_init__(self):
        for value in (
            self.tenant_id,
            self.space_id,
            self.repository_id,
            self.document_id,
            self.version_id,
            self.chunk_id,
        ):
            uuid_value(value)

    def __repr__(self):
        return "CitationRef(<private identifiers>)"


@dataclass(frozen=True, slots=True, repr=False)
class Evidence:
    reference: CitationRef
    excerpt: str
    start_offset: int
    end_offset: int
    page: int | None = None
    section: tuple[str, ...] = ()

    def __post_init__(self):
        if (
            not isinstance(self.reference, CitationRef)
            or not isinstance(self.excerpt, str)
            or not 1 <= len(self.excerpt) <= 512
            or type(self.start_offset) is not int
            or type(self.end_offset) is not int
            or not 0 <= self.start_offset < self.end_offset <= 2_000_000
            or len(self.excerpt) > self.end_offset - self.start_offset
            or (
                self.page is not None
                and (type(self.page) is not int or not 1 <= self.page <= 2_000_000)
            )
        ):
            raise RetrievalError("INPUT_INVALID")
        section_path(self.section)

    def __repr__(self):
        return "Evidence(<private document evidence>)"


@dataclass(frozen=True, slots=True, repr=False)
class HybridHit:
    evidence: Evidence
    score: float
    vector_rank: int | None
    lexical_rank: int | None
    ranking_revision: str = RRF_REVISION

    def __post_init__(self):
        if (
            not isinstance(self.evidence, Evidence)
            or type(self.score) is not float
            or not math.isfinite(self.score)
            or self.ranking_revision != RRF_REVISION
        ):
            raise RetrievalError("INPUT_INVALID")
        ranks = (self.vector_rank, self.lexical_rank)
        if all(v is None for v in ranks) or any(
            v is not None and (type(v) is not int or not 1 <= v <= CANDIDATE_LIMIT) for v in ranks
        ):
            raise RetrievalError("INPUT_INVALID")
        expected = math.fsum(1.0 / (RRF_K + v) for v in ranks if v is not None)
        if self.score != expected:
            raise RetrievalError("INPUT_INVALID")

    def __repr__(self):
        return "HybridHit(<private ranked evidence>)"
