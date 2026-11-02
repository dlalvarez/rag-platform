"""Model-agnostic embedding boundaries. No storage, network or model selection."""

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from numbers import Real
from typing import Literal, Protocol

Kind = Literal["query", "passage"]
MAX_TEXT_CHARS = 8192
MAX_BATCH_CHARS = 262144


class EmbeddingError(RuntimeError):
    CODES = {
        "INPUT_INVALID",
        "INPUT_TOO_LONG",
        "PROFILE_MISMATCH",
        "DIMENSION_MISMATCH",
        "INVALID_VECTOR",
        "LIMIT_EXCEEDED",
        "DEPENDENCY_UNAVAILABLE",
    }

    def __init__(self, code="DEPENDENCY_UNAVAILABLE"):
        self.code = (
            code if isinstance(code, str) and code in self.CODES else "DEPENDENCY_UNAVAILABLE"
        )
        super().__init__(self.code)


@dataclass(frozen=True, slots=True, repr=False)
class EmbeddingProfile:
    provider: str
    model: str
    model_revision: str
    tokenizer: str
    tokenizer_revision: str
    dimension: int
    metric: str
    max_tokens: int
    normalization: str
    query_prefix: str
    passage_prefix: str
    adapter_revision: str
    dtype: str = "float32"
    max_batch: int = 32

    def __post_init__(self):
        identifiers = (
            self.provider,
            self.model,
            self.model_revision,
            self.tokenizer,
            self.tokenizer_revision,
            self.adapter_revision,
        )
        if any(
            not isinstance(v, str) or re.fullmatch(r"[A-Za-z0-9._/-]{1,256}", v) is None
            for v in identifiers
        ):
            raise EmbeddingError("INPUT_INVALID")
        if (
            type(self.dimension) is not int
            or not 1 <= self.dimension <= 2000
            or type(self.max_tokens) is not int
            or not 1 <= self.max_tokens <= 131072
            or type(self.max_batch) is not int
            or not 1 <= self.max_batch <= 32
            or self.metric not in ("cosine", "l2", "inner_product")
            or self.normalization not in ("l2", "none")
            or self.dtype != "float32"
        ):
            raise EmbeddingError("INPUT_INVALID")
        for prefix in (self.query_prefix, self.passage_prefix):
            if (
                not isinstance(prefix, str)
                or len(prefix) > 128
                or any((ord(c) < 32 and c != "\n") or ord(c) == 127 for c in prefix)
            ):
                raise EmbeddingError("INPUT_INVALID")

    def fingerprint(self):
        body = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(b"F05/profile/v1:" + body.encode()).hexdigest()

    def __repr__(self):
        return "EmbeddingProfile(<immutable metadata>)"


@dataclass(frozen=True, slots=True, repr=False)
class EmbeddingBatch:
    profile_fingerprint: str
    vectors: tuple[tuple[float, ...], ...]
    input_tokens: tuple[int, ...]

    @property
    def total_tokens(self):
        return sum(self.input_tokens)

    def __repr__(self):
        return "EmbeddingBatch(<private vectors>)"


def inputs(profile, texts, kind):
    if (
        not isinstance(profile, EmbeddingProfile)
        or kind not in ("query", "passage")
        or not isinstance(texts, (tuple, list))
    ):
        raise EmbeddingError("INPUT_INVALID")
    if not 1 <= len(texts) <= profile.max_batch:
        raise EmbeddingError("LIMIT_EXCEEDED")
    total = 0
    for text in texts:
        if not isinstance(text, str) or not text.strip() or "\0" in text:
            raise EmbeddingError("INPUT_INVALID")
        try:
            text.encode("utf-8", errors="strict")
        except UnicodeError:
            raise EmbeddingError("INPUT_INVALID") from None
        total += len(text)
        if len(text) > MAX_TEXT_CHARS or total > MAX_BATCH_CHARS:
            raise EmbeddingError("LIMIT_EXCEEDED")


def validate(profile, texts, kind, batch):
    """Validate a complete bounded response before callers can persist any vector."""
    inputs(profile, texts, kind)
    if not isinstance(batch, EmbeddingBatch) or batch.profile_fingerprint != profile.fingerprint():
        raise EmbeddingError("PROFILE_MISMATCH")
    if not isinstance(batch.vectors, tuple) or len(batch.vectors) != len(texts):
        raise EmbeddingError("DIMENSION_MISMATCH")
    if not isinstance(batch.input_tokens, tuple) or len(batch.input_tokens) != len(texts):
        raise EmbeddingError("INPUT_INVALID")
    for count in batch.input_tokens:
        if type(count) is not int or count < 1:
            raise EmbeddingError("INPUT_INVALID")
        if count > profile.max_tokens:
            raise EmbeddingError("INPUT_TOO_LONG")
    result = []
    for vector in batch.vectors:
        if not isinstance(vector, tuple) or len(vector) != profile.dimension:
            raise EmbeddingError("DIMENSION_MISMATCH")
        values = []
        for value in vector:
            if isinstance(value, bool) or not isinstance(value, Real):
                raise EmbeddingError("INVALID_VECTOR")
            try:
                number = float(value)
            except (OverflowError, ValueError):
                raise EmbeddingError("INVALID_VECTOR") from None
            if not math.isfinite(number) or abs(number) > 3.4028234663852886e38:
                raise EmbeddingError("INVALID_VECTOR")
            values.append(number)
        norm = math.sqrt(math.fsum(v * v for v in values))
        if (profile.metric == "cosine" and norm == 0) or (
            profile.normalization == "l2" and abs(norm - 1) > 1e-4
        ):
            raise EmbeddingError("INVALID_VECTOR")
        result.append(tuple(values))
    return EmbeddingBatch(profile.fingerprint(), tuple(result), batch.input_tokens)


class EmbeddingProvider(Protocol):
    profile: EmbeddingProfile

    def count_tokens(self, text: str, kind: Kind) -> int: ...
    def embed(self, texts: tuple[str, ...] | list[str], kind: Kind) -> EmbeddingBatch: ...
