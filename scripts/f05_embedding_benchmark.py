"""Opt-in local Qwen measurement on the frozen fictional ES/EN integration corpus."""

import argparse
import hashlib
import json
import math
import resource
import statistics
import time
from pathlib import Path

from rag_platform.embeddings.contracts import EmbeddingError
from rag_platform.embeddings.qwen import LocalQwen

CORPUS_SHA = "ca4d53dd72713febe740eebd958b384aae6dd9f2793c8433314c224b3284340e"


def run(root):
    corpus = Path(__file__).resolve().parents[1] / "tests/fixtures/f05/retrieval-es-en.json"
    raw = corpus.read_bytes()
    if hashlib.sha256(raw).hexdigest() != CORPUS_SHA:
        raise EmbeddingError("INPUT_INVALID")
    data = json.loads(raw)
    start = time.perf_counter()
    provider = LocalQwen.load(root)
    load_seconds = time.perf_counter() - start
    passages = []
    index_seconds = 0.0
    total_tokens = 0
    for offset in range(0, len(data["documents"]), 4):
        texts = [item["text"] for item in data["documents"][offset : offset + 4]]
        start = time.perf_counter()
        batch = provider.embed(texts, "passage")
        index_seconds += time.perf_counter() - start
        total_tokens += batch.total_tokens
        passages.extend(batch.vectors)
    recall = {"es": [], "en": []}
    latency = []
    for query in data["queries"]:
        start = time.perf_counter()
        batch = provider.embed([query["text"]], "query")
        latency.append(time.perf_counter() - start)
        total_tokens += batch.total_tokens
        vector = batch.vectors[0]
        scores = [math.fsum(a * b for a, b in zip(vector, item, strict=True)) for item in passages]
        indices = sorted(range(len(scores)), key=lambda index: (-scores[index], index))[:3]
        found = {data["documents"][index]["id"] for index in indices}
        relevant = set(query["relevant"])
        recall[query["language"]].append(len(found & relevant) / len(relevant))
    query = data["queries"][0]["text"]
    first = provider.embed([query], "query")
    second = provider.embed([query], "query")
    stable = (
        max(abs(a - b) for a, b in zip(first.vectors[0], second.vectors[0], strict=True)) <= 1e-6
    )
    bounded = False
    try:
        provider.embed(["word " * 1000], "passage")
    except EmbeddingError as exc:
        bounded = exc.code == "INPUT_TOO_LONG"
    warmed = []
    for _ in range(8):
        start = time.perf_counter()
        provider.embed([query], "query")
        warmed.append(time.perf_counter() - start)
    values = sorted(latency)
    metrics = {
        "model": provider.profile.model,
        "revision": provider.profile.model_revision,
        "profile_fingerprint": provider.profile.fingerprint(),
        "corpus_sha256": CORPUS_SHA,
        "synthetic_only": True,
        "documents": len(passages),
        "queries": len(latency),
        "dimension": provider.profile.dimension,
        "operational_max_tokens": provider.profile.max_tokens,
        "batch_max": provider.profile.max_batch,
        "torch_threads": 2,
        "load_seconds": round(load_seconds, 3),
        "index_seconds": round(index_seconds, 3),
        "index_fragments_per_second": round(len(passages) / index_seconds, 3),
        "query_p50_seconds": round(statistics.median(latency), 3),
        "query_p95_seconds": round(values[math.ceil(len(values) * 0.95) - 1], 3),
        "warm_repeated_query_p50_seconds": round(statistics.median(warmed), 3),
        "process_max_rss_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
        "usage_tokens_primary_batches": total_tokens,
        "recall_at_3": {lang: statistics.mean(scores) for lang, scores in recall.items()},
        "repeat_within_1e_6": stable,
        "over_limit_rejected_before_model": bounded,
        "scope": "provider/exact synthetic integration only; not SQL/ANN/ACL/domain quality/F06",
    }
    metrics["passed"] = (
        all(value >= 0.8 for value in metrics["recall_at_3"].values()) and stable and bounded
    )
    return metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Reserve a new evidence file before inference; never overwrite an earlier run.
    try:
        with args.output.open("x") as target:
            result = run(args.model_dir)
            target.write(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, sort_keys=True))
        return 0 if result["passed"] else 1
    except EmbeddingError as exc:
        print("F05-MODEL " + exc.code)
        return 1
    except Exception:
        print("F05-MODEL DEPENDENCY_UNAVAILABLE")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
