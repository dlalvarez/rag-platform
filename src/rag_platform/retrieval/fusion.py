"""Versioned reciprocal rank fusion over already-authorized bounded candidates."""

import math

from rag_platform.retrieval.contracts import (
    CANDIDATE_LIMIT,
    RRF_K,
    Evidence,
    HybridHit,
    RetrievalError,
)


def fuse(
    vector: tuple[Evidence, ...] | list[Evidence],
    lexical: tuple[Evidence, ...] | list[Evidence],
    top_k: int,
) -> tuple[HybridHit, ...]:
    """One contribution per modality; no scores from incompatible ranking scales."""
    if type(top_k) is not int or not 1 <= top_k <= 50:
        raise RetrievalError("INPUT_INVALID")
    items, ranks = {}, {}
    scope = None
    for modality, candidates in enumerate((vector, lexical)):
        if type(candidates) not in (tuple, list) or len(candidates) > CANDIDATE_LIMIT:
            raise RetrievalError("INPUT_INVALID")
        seen = set()
        for position, item in enumerate(candidates, 1):
            if not isinstance(item, Evidence):
                raise RetrievalError("INPUT_INVALID")
            ref = item.reference
            if scope is None:
                scope = (ref.tenant_id, ref.space_id)
            elif scope != (ref.tenant_id, ref.space_id):
                raise RetrievalError("INCONSISTENT_EVIDENCE")
            key = ref.chunk_id
            if key in seen:
                # A duplicate must never inflate a contribution or shift later ranks silently.
                raise RetrievalError("INCONSISTENT_EVIDENCE")
            seen.add(key)
            if key in items and items[key] != item:
                raise RetrievalError("INCONSISTENT_EVIDENCE")
            items[key] = item
            ranks.setdefault(key, [None, None])[modality] = position
    hits = [
        HybridHit(
            item,
            math.fsum(1.0 / (RRF_K + rank) for rank in ranks[key] if rank is not None),
            *ranks[key],
        )
        for key, item in items.items()
    ]
    hits.sort(key=lambda hit: (-hit.score, hit.evidence.reference.chunk_id.int))
    return tuple(hits[:top_k])
