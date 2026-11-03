"""RRF behavior, privacy boundaries and invalid evidence, without services."""

from dataclasses import FrozenInstanceError, replace
from uuid import UUID, uuid4

import pytest

from rag_platform.retrieval.contracts import (
    RRF_REVISION,
    CitationRef,
    Evidence,
    HybridHit,
    QueryFilters,
    RetrievalError,
)
from rag_platform.retrieval.fusion import fuse

TENANT, SPACE, REPO, DOC, VERSION = (uuid4() for _ in range(5))


def evidence(number, **changes):
    reference = CitationRef(TENANT, SPACE, REPO, DOC, VERSION, UUID(int=number))
    return replace(Evidence(reference, "PRIVATE_EVIDENCE", 10, 80, 2, ("Section",)), **changes)


def test_shared_match_beats_single_modality_and_carries_both_ranks():
    a, b, c = (evidence(i) for i in (1, 2, 3))
    hits = fuse((a, b), (c, b), 3)
    assert hits[0].evidence == b
    assert hits[0].vector_rank == hits[0].lexical_rank == 2
    assert hits[0].score == pytest.approx(2 / 62)
    assert hits[0].ranking_revision == RRF_REVISION
    assert len(hits) == 3


def test_ties_use_uuid_not_modality_or_input_dictionary_order():
    a, b = evidence(1), evidence(2)
    assert [h.evidence for h in fuse((b,), (a,), 2)] == [a, b]
    assert [h.evidence for h in fuse((a,), (b,), 2)] == [a, b]


def test_fusion_keeps_input_rank_not_uuid_and_applies_limit_after_merge():
    a, b, c = (evidence(i) for i in (1, 2, 3))
    assert [h.evidence for h in fuse((c, b, a), (), 2)] == [c, b]
    assert fuse((), (), 1) == ()


def test_modalities_are_symmetric_and_inputs_unchanged():
    a, b, c = (evidence(i) for i in (1, 2, 3))
    vector, lexical = [a, b], [b, c]
    left, right = fuse(vector, lexical, 3), fuse(lexical, vector, 3)
    assert [(h.evidence, h.score) for h in left] == [(h.evidence, h.score) for h in right]
    assert vector == [a, b] and lexical == [b, c]


def test_candidate_cap_can_produce_union_then_top50():
    vector = tuple(evidence(i) for i in range(1, 51))
    lexical = tuple(evidence(i) for i in range(51, 101))
    hits = fuse(vector, lexical, 50)
    assert len(hits) == 50 and len({h.evidence.reference.chunk_id for h in hits}) == 50
    assert hits[0].score == pytest.approx(1 / 61)


@pytest.mark.parametrize("top_k", [0, 51, True, 1.0, "3", None])
def test_invalid_top_k_is_closed(top_k):
    with pytest.raises(RetrievalError, match="^INPUT_INVALID$"):
        fuse((), (), top_k)


@pytest.mark.parametrize("values", [None, "PRIVATE", iter(()), (None,), [evidence(1)] * 51])
def test_invalid_or_unbounded_candidates_rejected(values):
    with pytest.raises(RetrievalError, match="^INPUT_INVALID$"):
        fuse(values, (), 1)


def test_duplicate_within_modality_does_not_inflate_score():
    a = evidence(1)
    with pytest.raises(RetrievalError, match="^INCONSISTENT_EVIDENCE$"):
        fuse((a, a), (), 1)


@pytest.mark.parametrize("field", ["excerpt", "start_offset", "page", "reference"])
def test_shared_chunk_with_changed_evidence_fails_closed(field):
    a = evidence(1)
    values = {
        "excerpt": "DIFFERENT_PRIVATE",
        "start_offset": 11,
        "page": 3,
        "reference": replace(a.reference, document_id=uuid4()),
    }
    with pytest.raises(RetrievalError, match="^INCONSISTENT_EVIDENCE$"):
        fuse((a,), (replace(a, **{field: values[field]}),), 1)


@pytest.mark.parametrize("field", ["tenant_id", "space_id"])
def test_cross_tenant_or_space_cannot_be_fused(field):
    a, b = evidence(1), evidence(2)
    b = replace(b, reference=replace(b.reference, **{field: uuid4()}))
    with pytest.raises(RetrievalError, match="^INCONSISTENT_EVIDENCE$"):
        fuse((a,), (b,), 2)


@pytest.mark.parametrize(
    "field", ["tenant_id", "space_id", "repository_id", "document_id", "version_id", "chunk_id"]
)
def test_citation_requires_nonzero_uuid_for_every_identifier(field):
    with pytest.raises(RetrievalError, match="^INPUT_INVALID$"):
        replace(evidence(1).reference, **{field: UUID(int=0)})


@pytest.mark.parametrize(
    "changes",
    [
        {"excerpt": ""},
        {"excerpt": "x" * 513},
        {"excerpt": None},
        {"start_offset": True},
        {"start_offset": -1},
        {"end_offset": 10},
        {"end_offset": 2_000_001},
        {"end_offset": 11},
        {"page": True},
        {"page": 0},
        {"section": ["Section"]},
        {"section": ("PRIVATE\n",)},
        {"reference": None},
    ],
)
def test_invalid_provenance_fails_without_private_payload(changes):
    with pytest.raises(RetrievalError) as error:
        evidence(1, **changes)
    assert str(error.value) == "INPUT_INVALID" and "PRIVATE" not in repr(error.value)


@pytest.mark.parametrize(
    "changes",
    [
        {"document_ids": [DOC]},
        {"document_ids": (DOC, DOC)},
        {"document_ids": tuple(uuid4() for _ in range(33))},
        {"version_ids": ("PRIVATE",)},
        {"page_min": True},
        {"page_max": 0},
        {"page_min": 3, "page_max": 2},
        {"section_prefix": ("",)},
        {"section_prefix": ("x" * 257,)},
        {"section_prefix": ("x",) * 17},
    ],
)
def test_filters_reject_unbounded_ambiguous_or_invalid_inputs(changes):
    with pytest.raises(RetrievalError, match="^INPUT_INVALID$"):
        QueryFilters(**changes)


def test_valid_filters_offsets_and_immutable_private_representations():
    filters = QueryFilters((DOC,), (VERSION,), 1, 3, ("PRIVATE_SECTION",))
    item = evidence(1, excerpt="á漢字", start_offset=0, end_offset=3)
    hit = fuse((item,), (), 1)[0]
    for value in (filters, item.reference, item, hit):
        assert "PRIVATE" not in repr(value) and str(DOC) not in repr(value)
    with pytest.raises(FrozenInstanceError):
        item.page = 3


@pytest.mark.parametrize(
    "changes",
    [
        {"score": float("nan")},
        {"score": 1.0},
        {"score": True},
        {"vector_rank": 0},
        {"vector_rank": True},
        {"vector_rank": 51},
        {"vector_rank": None, "lexical_rank": None},
        {"ranking_revision": "unknown"},
    ],
)
def test_hybrid_score_cannot_be_misrepresented_as_cosine_or_unknown_revision(changes):
    hit = HybridHit(evidence(1), 1 / 61, 1, None)
    with pytest.raises(RetrievalError, match="^INPUT_INVALID$"):
        replace(hit, **changes)
