"""Frozen public F06 corpus and transparent metrics. No model, SQL or network."""

import hashlib
import json
import math
import re
from numbers import Real

CORPUS_SHA256 = "35976933e799d23ca87e4718dceedab0f8989b3204c881dc4972294d4b8b4bb7"
KINDS = {"answerable", "semantic", "technical", "ambiguous", "negative"}


def logical_id(value):
    return isinstance(value, str) and re.fullmatch("[a-z][a-z0-9-]{0,63}", value) is not None


def text_value(value, maximum):
    return (
        isinstance(value, str)
        and 1 <= len(value) <= maximum
        and bool(value.strip())
        and "\0" not in value
    )


def validate_corpus(data):
    if (
        not isinstance(data, dict)
        or set(data) != {"version", "synthetic", "documents", "queries"}
        or data["version"] != "f06-technical-es-en-v1"
        or data["synthetic"] is not True
        or not isinstance(data["documents"], list)
        or not 1 <= len(data["documents"]) <= 64
        or not isinstance(data["queries"], list)
        or not 30 <= len(data["queries"]) <= 128
    ):
        raise ValueError("Invalid evaluation corpus")
    documents = set()
    for item in data["documents"]:
        if (
            not isinstance(item, dict)
            or set(item) != {"id", "language", "text"}
            or not logical_id(item["id"])
            or item["id"] in documents
            or item["language"] not in {"es", "en"}
            or not text_value(item["text"], 512)
        ):
            raise ValueError("Invalid evaluation document")
        documents.add(item["id"])
    queries, languages, kinds = set(), set(), set()
    for item in data["queries"]:
        if (
            not isinstance(item, dict)
            or set(item) != {"id", "language", "text", "relevant", "kind"}
            or not logical_id(item["id"])
            or item["id"] in queries
            or item["language"] not in {"es", "en"}
            or not text_value(item["text"], 1024)
            or item["kind"] not in KINDS
            or not isinstance(item["relevant"], list)
            or any(not logical_id(v) for v in item["relevant"])
            or len(set(item["relevant"])) != len(item["relevant"])
            or not set(item["relevant"]) <= documents
            or (item["kind"] == "negative") != (len(item["relevant"]) == 0)
            or (item["kind"] == "ambiguous" and len(item["relevant"]) < 2)
        ):
            raise ValueError("Invalid evaluation query")
        queries.add(item["id"])
        languages.add(item["language"])
        kinds.add(item["kind"])
    if languages != {"es", "en"} or kinds != KINDS:
        raise ValueError("Missing evaluation coverage")
    for language in languages:
        if not any(q["language"] == language and q["relevant"] for q in data["queries"]):
            raise ValueError("Missing answerable language")
    return data


def load_corpus(path):
    raw = path.read_bytes()
    if len(raw) > 131072 or hashlib.sha256(raw).hexdigest() != CORPUS_SHA256:
        raise ValueError("Frozen corpus mismatch")
    return validate_corpus(json.loads(raw))


def recall_at_k(found, gold, k=10):
    if (
        type(k) is not int
        or not 1 <= k <= 50
        or type(found) not in (tuple, list)
        or len(found) > 100
        or type(gold) not in (tuple, list)
        or not gold
        or any(not logical_id(v) for v in (*found, *gold))
    ):
        raise ValueError("Invalid recall inputs")
    return len(set(found[:k]) & set(gold)) / len(set(gold))


def evaluate(data, retrieved):
    validate_corpus(data)
    if not isinstance(retrieved, dict) or set(retrieved) != {q["id"] for q in data["queries"]}:
        raise ValueError("Incomplete evaluation results")
    ids = {d["id"] for d in data["documents"]}
    scores, by_language, by_kind = {}, {"es": [], "en": []}, {}
    negative_hits = []
    for query in data["queries"]:
        found = retrieved[query["id"]]
        if (
            type(found) not in (tuple, list)
            or len(found) > 50
            or any(not logical_id(v) or v not in ids for v in found)
        ):
            raise ValueError("Invalid evaluation results")
        if not query["relevant"]:
            negative_hits.append(len(found))
            continue
        value = recall_at_k(found, query["relevant"])
        scores[query["id"]] = value
        by_language[query["language"]].append(value)
        by_kind.setdefault(query["kind"], []).append(value)
    mean = math.fsum(scores.values()) / len(scores)
    return {
        "metric": "document_recall_at_10",
        "answerable_queries": len(scores),
        "recall_at_10": mean,
        "by_language": {
            key: math.fsum(values) / len(values) for key, values in by_language.items()
        },
        "by_kind": {key: math.fsum(values) / len(values) for key, values in by_kind.items()},
        "per_query": scores,
        "negative_queries": len(negative_hits),
        "negative_queries_with_hits": sum(value > 0 for value in negative_hits),
        "negative_returned_hits": negative_hits,
        "recall_gate_passed": mean >= 0.8,
        "negative_interpretation": "ranking only; no semantic abstention claimed",
    }


def latency_summary(milliseconds):
    if (
        type(milliseconds) not in (tuple, list)
        or not 1 <= len(milliseconds) <= 10000
        or any(
            isinstance(v, bool) or not isinstance(v, Real) or not math.isfinite(v) or v < 0
            for v in milliseconds
        )
    ):
        raise ValueError("Invalid latency samples")
    values = sorted(float(v) for v in milliseconds)
    return {
        "samples": len(values),
        "p50_ms": values[math.ceil(len(values) * 0.5) - 1],
        "p95_ms": values[math.ceil(len(values) * 0.95) - 1],
        "minimum_ms": values[0],
        "maximum_ms": values[-1],
        "method": "nearest-rank",
    }
