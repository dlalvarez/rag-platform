"""Opt-in capacity boundary for the approved local profile, with fictional inputs only."""

import argparse
import json
import logging
import os
import resource
import threading
import time
from pathlib import Path

from rag_platform.embeddings.contracts import EmbeddingError
from rag_platform.embeddings.qwen import _INFERENCE, LocalQwen


def run(root):
    wall = time.perf_counter()
    initial = resource.getrusage(resource.RUSAGE_SELF)
    provider = LocalQwen.load(root)
    load_seconds = time.perf_counter() - wall
    # Predeclared synthetic capacity case, not a semantic-quality corpus.
    text = " ".join(["word"] * 511)
    count = provider.count_tokens(text, "passage")
    if count != provider.profile.max_tokens:
        raise EmbeddingError("INPUT_INVALID")
    result = {}

    def batch():
        start = time.perf_counter()
        before = resource.getrusage(resource.RUSAGE_SELF)
        try:
            value = provider.embed([text] * 4, "passage")
            after = resource.getrusage(resource.RUSAGE_SELF)
            result.update(
                tokens=value.total_tokens,
                vectors=len(value.vectors),
                counts=list(value.input_tokens),
                seconds=time.perf_counter() - start,
                cpu_seconds=(after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime),
            )
        except Exception as error:
            result["error"] = error.code if isinstance(error, EmbeddingError) else "REFUSED"

    worker = threading.Thread(target=batch)
    worker.start()
    busy = False
    for _ in range(500):
        if not _INFERENCE.acquire(blocking=False):
            busy = True
            break
        _INFERENCE.release()
        if not worker.is_alive():
            break
        time.sleep(0.01)
    rejected = False
    if busy:
        try:
            provider.embed(["fictional query"], "query")
        except EmbeddingError as error:
            rejected = error.code == "LIMIT_EXCEEDED"
    worker.join(timeout=180)
    if worker.is_alive() or "error" in result or not rejected:
        raise EmbeddingError("DEPENDENCY_UNAVAILABLE")
    recovered = provider.embed(["fictional query"], "query")
    final = resource.getrusage(resource.RUSAGE_SELF)
    elapsed = time.perf_counter() - wall
    cpu = final.ru_utime + final.ru_stime - initial.ru_utime - initial.ru_stime
    rss = final.ru_maxrss / 1024
    return {
        "model": provider.profile.model,
        "revision": provider.profile.model_revision,
        "profile_fingerprint": provider.profile.fingerprint(),
        "synthetic_capacity_only": True,
        "allocated_vcpus": os.cpu_count(),
        "torch_threads": 2,
        "max_tokens_per_passage": count,
        "batch_size": 4,
        "primary_inference_tokens": result["tokens"],
        "load_seconds": round(load_seconds, 3),
        "batch_seconds": round(result["seconds"], 3),
        "batch_cpu_seconds": round(result["cpu_seconds"], 3),
        "batch_average_process_cpu_percent": round(
            result["cpu_seconds"] / result["seconds"] * 100, 1
        ),
        "total_seconds": round(elapsed, 3),
        "total_cpu_seconds": round(cpu, 3),
        "process_max_rss_mib": round(rss, 1),
        "predeclared_single_process_rss_cap_mib": 6144,
        "concurrent_call_rejected": rejected,
        "next_call_after_release_ok": len(recovered.vectors) == 1,
        "passed": result["counts"] == [512] * 4 and rss <= 6144 and rejected,
        "limits": "One process/CPU2; no multi-process/NAS4/SQL/ANN/ACL/domain claims.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    try:
        with args.output.open("x") as stream:
            result = run(args.model_dir)
            stream.write(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, sort_keys=True))
        return 0 if result["passed"] else 1
    except Exception:
        print("F05-CAPACITY REFUSED; no input/vector details.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
