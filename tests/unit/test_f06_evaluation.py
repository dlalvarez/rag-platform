"""Frozen gold coverage and denominator/rank/negative/latency behavior, no model."""

from copy import deepcopy
from pathlib import Path

import pytest

from rag_platform.ingestion.extraction import NORMALIZER, PARSERS, ChunkConfig, chunks, from_wire
from rag_platform.retrieval.evaluation import (
    evaluate,
    latency_summary,
    load_corpus,
    recall_at_k,
    validate_corpus,
)

CORPUS = Path(__file__).resolve().parents[1] / "fixtures/rag-eval/technical-es-en-v1.json"


def corpus():
    return load_corpus(CORPUS)


def test_frozen_dataset_has_40_queries_with_balanced_languages_and_explicit_negatives():
    data = corpus()
    assert len(data["documents"]) == 16 and len(data["queries"]) == 40
    assert sum(q["language"] == "es" for q in data["queries"]) == 20
    assert sum(q["kind"] == "negative" for q in data["queries"]) == 4
    assert sum(q["kind"] == "ambiguous" for q in data["queries"]) == 4
    assert sum(q["kind"] == "technical" for q in data["queries"]) == 8


def test_corpus_change_is_rejected_before_any_measurement(tmp_path):
    target = tmp_path / "modified.json"
    target.write_bytes(CORPUS.read_bytes() + b" ")
    with pytest.raises(ValueError, match="Frozen corpus mismatch"):
        load_corpus(target)


def test_gold_is_never_inferred_from_retrieved_results():
    data = corpus()
    retrieved = {q["id"]: list(q["relevant"]) for q in data["queries"]}
    result = evaluate(data, retrieved)
    assert result["answerable_queries"] == 36 and result["recall_at_10"] == 1.0
    assert result["negative_queries"] == 4 and result["negative_queries_with_hits"] == 0
    assert result["by_language"] == {"es": 1.0, "en": 1.0}
    assert result["recall_gate_passed"]
    assert data == corpus()


def test_empty_rankings_fail_recall_without_counting_negatives_as_success():
    data = corpus()
    report = evaluate(data, {q["id"]: [] for q in data["queries"]})
    assert report["answerable_queries"] == 36 and report["recall_at_10"] == 0
    assert not report["recall_gate_passed"]


def test_negative_hits_are_reported_separately_without_faking_abstention():
    data = corpus()
    found = {q["id"]: list(q["relevant"]) for q in data["queries"]}
    for q in data["queries"]:
        if q["kind"] == "negative":
            found[q["id"]] = [data["documents"][0]["id"]]
    report = evaluate(data, found)
    assert report["negative_queries_with_hits"] == 4
    assert report["recall_at_10"] == 1.0 and report["answerable_queries"] == 36
    assert "no semantic abstention" in report["negative_interpretation"]


def test_recall_respects_cutoff_gold_denominator_and_no_duplicate_credit():
    assert recall_at_k(["a", "a", "b"], ["a", "b"], 2) == 0.5
    assert recall_at_k(["a", "b"], ["a", "b"], 1) == 0.5
    assert recall_at_k(["x", "a"], ["a"], 1) == 0
    assert recall_at_k(["a"], ["a", "b"]) == 0.5


@pytest.mark.parametrize(
    "found,gold,k",
    [
        ([], [], 10),
        ("a", ["a"], 10),
        (["a"], ["a"], True),
        (["a"], ["a"], 0),
        (["a"], ["a"], 51),
        ([None], ["a"], 10),
    ],
)
def test_invalid_recall_inputs_are_closed(found, gold, k):
    with pytest.raises(ValueError):
        recall_at_k(found, gold, k)


@pytest.mark.parametrize("change", ["missing-query", "unknown-doc", "too-many-hits"])
def test_incomplete_or_foreign_results_cannot_count_as_evidence(change):
    data = corpus()
    found = {q["id"]: [] for q in data["queries"]}
    key = data["queries"][0]["id"]
    if change == "missing-query":
        del found[key]
    elif change == "unknown-doc":
        found[key] = ["foreign-tenant-document"]
    else:
        found[key] = [data["documents"][0]["id"]] * 51
    with pytest.raises(ValueError):
        evaluate(data, found)


@pytest.mark.parametrize(
    "change", ["unknown-gold", "negative-gold", "ambiguous-one-gold", "duplicate-id"]
)
def test_malformed_gold_or_coverage_rejected(change):
    data = deepcopy(corpus())
    if change == "unknown-gold":
        data["queries"][0]["relevant"] = ["unknown"]
    elif change == "negative-gold":
        next(q for q in data["queries"] if q["kind"] == "negative")["relevant"] = ["es-tls-rotate"]
    elif change == "ambiguous-one-gold":
        next(q for q in data["queries"] if q["kind"] == "ambiguous")["relevant"] = ["es-tls-rotate"]
    else:
        data["queries"][1]["id"] = data["queries"][0]["id"]
    with pytest.raises(ValueError):
        validate_corpus(data)


def test_latency_nearest_rank_has_explicit_denominator_and_boundaries():
    report = latency_summary(list(range(1, 21)))
    assert report["samples"] == 20 and report["p50_ms"] == 10 and report["p95_ms"] == 19
    assert report["minimum_ms"] == 1 and report["maximum_ms"] == 20


@pytest.mark.parametrize("samples", [[], [float("nan")], [float("inf")], [True], [-1], ["PRIVATE"]])
def test_invalid_latency_samples_do_not_create_baseline(samples):
    with pytest.raises(ValueError):
        latency_summary(samples)


def test_every_document_is_one_complete_chunk_without_truncation():
    for item in corpus()["documents"]:
        data = from_wire(
            {
                "version": 1,
                "parser": PARSERS["text/plain"],
                "normalizer": NORMALIZER,
                "page_count": None,
                "blocks": [
                    {"text": item["text"], "page": None, "section": ["Frozen gold"], "kind": "text"}
                ],
            },
            "text/plain",
        )
        pieces = chunks(data, ChunkConfig(512, 64))
        assert len(pieces) == 1 and pieces[0].text == data.text == item["text"]
