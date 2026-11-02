"""Deterministic CI fixture only. Never a semantic model or deployable provider."""

import hashlib
import math
import struct
from dataclasses import dataclass

from rag_platform.embeddings.contracts import (
    EmbeddingBatch,
    EmbeddingError,
    EmbeddingProfile,
    inputs,
    validate,
)


def fixture_profile(*, dimension=3, max_tokens=32, max_batch=4):
    return EmbeddingProfile(
        provider="fixture",
        model="sha256-fixture",
        model_revision="v1",
        tokenizer="whitespace-fixture",
        tokenizer_revision="v1",
        dimension=dimension,
        metric="cosine",
        max_tokens=max_tokens,
        normalization="l2",
        query_prefix="query: ",
        passage_prefix="passage: ",
        adapter_revision="fixture-v1",
        max_batch=max_batch,
    )


@dataclass(frozen=True, slots=True, repr=False)
class DeterministicFixture:
    profile: EmbeddingProfile

    def __post_init__(self):
        profile = self.profile
        if (
            not isinstance(profile, EmbeddingProfile)
            or profile.provider != "fixture"
            or profile.model != "sha256-fixture"
            or profile.model_revision != "v1"
            or profile.tokenizer != "whitespace-fixture"
            or profile.tokenizer_revision != "v1"
            or profile.adapter_revision != "fixture-v1"
        ):
            raise EmbeddingError("PROFILE_MISMATCH")

    def count_tokens(self, text, kind):
        inputs(self.profile, [text], kind)
        prefix = self.profile.query_prefix if kind == "query" else self.profile.passage_prefix
        # Fixture tokenizer only; not a claim about E5/BGE or billable model usage.
        return len((prefix + text).split()) + 2

    def embed(self, texts, kind):
        inputs(self.profile, texts, kind)
        counts = tuple(self.count_tokens(text, kind) for text in texts)
        if any(n > self.profile.max_tokens for n in counts):
            raise EmbeddingError("INPUT_TOO_LONG")
        vectors = []
        for text in texts:
            seed = (self.profile.fingerprint() + ":" + kind + ":" + text).encode()
            raw = []
            for index in range(self.profile.dimension):
                digest = hashlib.sha256(
                    b"F05/fixture/v1:" + seed + index.to_bytes(4, "big")
                ).digest()
                raw.append(int.from_bytes(digest[:8], "big") / 2**64 * 2 - 1)
            norm = math.sqrt(math.fsum(x * x for x in raw))
            if norm == 0:
                raise EmbeddingError("INVALID_VECTOR")
            values = tuple(struct.unpack("!f", struct.pack("!f", x / norm))[0] for x in raw)
            vectors.append(values)
        return validate(
            self.profile,
            texts,
            kind,
            EmbeddingBatch(self.profile.fingerprint(), tuple(vectors), counts),
        )

    def __repr__(self):
        return "DeterministicFixture(<not a semantic model>)"
