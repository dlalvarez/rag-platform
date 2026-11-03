"""Frozen quality data/memory preparation/metrics, offline; never load Qwen."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from f05_sql_quality_check import corpus, means, parsed, prepare, recall  # noqa: E402

from rag_platform.embeddings.contracts import EmbeddingError
from rag_platform.embeddings.fixture import DeterministicFixture, fixture_profile
from rag_platform.ingestion.extraction import ChunkConfig, chunks

CORPUS = Path(__file__).resolve().parents[1] / "fixtures/f05/retrieval-es-en.json"


def test_frozen_corpus_has_one_chunk_per_document_and_complete_gold():
    data = corpus(CORPUS)
    for item in data["documents"]:
        normalized = parsed(item["text"])
        result = chunks(normalized, ChunkConfig(512, 64))
        assert len(result) == 1 and result[0].text == normalized.text


def test_corpus_change_rejected_before_provider(tmp_path):
    target = tmp_path / "changed.json"
    target.write_bytes(CORPUS.read_bytes() + b" ")
    with pytest.raises(ValueError, match="Frozen corpus mismatch"):
        corpus(target)


def test_preparation_counts_actual_calls_once_and_hides_vectors():
    data = corpus(CORPUS)
    base = DeterministicFixture(fixture_profile(max_tokens=512, max_batch=4))
    calls = []

    class Provider:
        profile = base.profile

        def embed(self, values, kind):
            calls.append((len(values), kind))
            return base.embed(values, kind)

    result = prepare(data, Provider())
    assert calls == [(4, "passage")] * 4 + [(1, "query")] * 16
    assert result.requests == 20 and result.tokens > 0
    assert len(result.passages) == len(result.queries) == len(result.texts) == 16
    assert "Fictional" not in repr(result) and "vectors" not in repr(result)
    for item in data["documents"]:
        assert result.passages[item["id"]].total_tokens > 0


def test_bad_embedding_response_refused_before_sql():
    data = corpus(CORPUS)
    provider = type(
        "BadProvider",
        (),
        dict(
            profile=fixture_profile(max_tokens=512, max_batch=4),
            embed=lambda *_args: object(),
        ),
    )()
    with pytest.raises(EmbeddingError):
        prepare(data, provider)


def test_recall_uses_gold_denominator_and_deduplicates_hits():
    assert recall(["a", "a", "x"], ["a", "b"]) == 0.5
    assert recall(["a", "b", "x"], ["a", "b"]) == 1
    with pytest.raises(ValueError):
        recall([], [])


@pytest.mark.parametrize(
    "values",
    [
        {"es": [], "en": [1]},
        {"es": [1]},
        {"es": [float("nan")], "en": [1]},
        {"es": [1.1], "en": [1]},
    ],
)
def test_invalid_metric_groups_are_not_accepted(values):
    with pytest.raises(ValueError):
        means(values)


def test_language_means_are_computed_separately():
    assert means({"es": [1, 0.5], "en": [1, 1]}) == {"es": 0.75, "en": 1.0}
