"""Provider accounting, memory preparation and acceptance gate; no real model."""

import sys
from copy import deepcopy
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from f06_quality_check import gates, prepare  # noqa: E402

from rag_platform.embeddings.contracts import EmbeddingError
from rag_platform.embeddings.fixture import DeterministicFixture, fixture_profile
from rag_platform.retrieval.evaluation import load_corpus

CORPUS = Path(__file__).resolve().parents[1] / "fixtures/rag-eval/technical-es-en-v1.json"


def test_prepare_counts_44_real_provider_operations_once_not_per_sql_fixture():
    data = load_corpus(CORPUS)
    base = DeterministicFixture(fixture_profile(max_tokens=512, max_batch=4))
    calls = []

    class Provider:
        profile = base.profile

        def embed(self, values, kind):
            calls.append((len(values), kind))
            return base.embed(values, kind)

    prepared, query_ms = prepare(data, Provider())
    assert calls == [(4, "passage")] * 4 + [(1, "query")] * 40
    assert prepared.requests == 44 and prepared.tokens > 0
    assert len(prepared.passages) == 16 and len(prepared.queries) == len(query_ms) == 40
    assert all(value >= 0 for value in query_ms)
    assert "FIXTURE" not in repr(prepared) and "vectors" not in repr(prepared)


def test_invalid_provider_response_cannot_prepare_quality_vectors():
    class Bad:
        profile = fixture_profile(max_tokens=512, max_batch=4)

        def embed(self, *_args):
            return object()

    with pytest.raises(EmbeddingError):
        prepare(load_corpus(CORPUS), Bad())


def results():
    return [
        dict(
            name=name,
            rollback_intact=True,
            query_failures=0,
            valid_citations=400,
            technical_fts_checks=8,
            metrics={"hybrid": {"recall_gate_passed": True, "by_language": {"es": 0.8, "en": 0.8}}},
        )
        for name in ("same-a", "same-b", "two-a", "two-b")
    ]


def test_gate_accepts_boundary_only_with_all_fixtures_citations_and_no_failures():
    assert gates(results())
    assert not gates([]) and not gates(results()[:3])


@pytest.mark.parametrize(
    "change",
    [
        {"rollback_intact": False},
        {"query_failures": 1},
        {"valid_citations": 399},
        {"technical_fts_checks": 7},
        {"name": "same-b"},
    ],
)
def test_gate_refuses_partial_evidence_or_duplicate_fixture(change):
    values = results()
    values[0].update(change)
    assert not gates(values)


@pytest.mark.parametrize(
    "languages", [{"es": 0.79, "en": 1.0}, {"es": 1.0}, {"es": float("nan"), "en": 1.0}]
)
def test_gate_does_not_hide_failing_or_missing_language_under_global_average(languages):
    values = deepcopy(results())
    values[0]["metrics"]["hybrid"]["by_language"] = languages
    assert not gates(values)


def test_gate_refuses_failed_overall_metric_even_if_language_values_claim_success():
    values = results()
    values[0]["metrics"]["hybrid"]["recall_gate_passed"] = False
    assert not gates(values)
