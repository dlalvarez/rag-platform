"""Opt-in HTTP fragments/originals proof; no model, SQL credentials or mutations."""

import hashlib
import importlib.util
import json
import logging
import math
from uuid import UUID

from f02_testing import Humans
from f03_http_check import API
from f05_adopt import save
from f05_search_check import selection

from rag_platform.identity_api import private_file

PHASE = "START"


def run():
    global PHASE
    assert importlib.util.find_spec("torch") is None
    _actor, records = selection()
    recovery = json.loads(private_file("/run/f05-recovery/selection.json", 512 * 1024))["records"]
    assert [(r["name"], r["tenant"], r["repository"], r["space"]) for r in recovery] == [
        (r["name"], r["tenant"], r["repository"], r["space"]) for r in records
    ]
    humans, api, results = None, None, []
    try:
        humans = Humans()
        humans.ready()
        api = API(humans)
        for index, (record, retained) in enumerate(zip(records, recovery, strict=True)):
            PHASE = record["name"]
            tenant, repository, space = (record[k] for k in ("tenant", "repository", "space"))
            path = f"/api/v1/tenants/{tenant}/search"
            value = dict(
                repository_ids=[repository], space_id=space, query="documento de prueba", top_k=3
            )
            denials = []
            for user, data, expected in (
                (None, value, 401),
                (
                    "alice",
                    {
                        **value,
                        "repository_ids": [repository, records[(index + 1) % 4]["repository"]],
                    },
                    403,
                ),
                ("alice", {**value, "assistant_id": str(UUID(int=1))}, 422),
                ("alice", {**value, "top_k": True}, 422),
                ("alice", {**value, "query": "palabra " * 1024}, 422),
            ):
                denied = api.json(user, "POST", path, value=data, expected=expected)
                denials.append(denied["request_id"])
            result = api.json(
                "alice", "POST", path, value=value, headers={"X-Request-ID": "ignored-client-trace"}
            )
            assert set(result) == {"request_id", "space_id", "hits", "usage"}
            assert result["space_id"] == space and 1 <= len(result["hits"]) <= 3
            assert result["request_id"] != "ignored-client-trace"
            expected_versions = {(r["document"], r["version"]) for r in (record, retained)}
            for hit in result["hits"]:
                assert set(hit) == {
                    "repository_id",
                    "document_id",
                    "version_id",
                    "chunk_id",
                    "score",
                    "excerpt",
                    "page",
                    "section",
                }
                assert hit["repository_id"] == repository
                assert (hit["document_id"], hit["version_id"]) in expected_versions
                assert UUID(hit["chunk_id"]).int != 0
                assert type(hit["score"]) in (int, float) and math.isfinite(hit["score"])
                assert -1 <= hit["score"] <= 1 and isinstance(hit["excerpt"], str)
                assert 1 <= len(hit["excerpt"]) <= 512
            assert result["usage"]["embedding_requests"] == 1
            assert type(result["usage"]["embedding_input_tokens"]) is int
            assert 1 <= result["usage"]["embedding_input_tokens"] <= 512
            # Existing atomic and recovered TXT originals must still be downloadable.
            for original in (record, retained):
                base = (
                    f"/api/v1/tenants/{tenant}/repositories/{repository}"
                    f"/documents/{original['document']}"
                )
                metadata = api.json("alice", "GET", base)["document"]
                assert metadata["version_id"] == original["original"]
                raw, _headers = api.call("alice", "GET", base + "/original")
                assert len(raw) == original["byte_size"]
                assert hashlib.sha256(raw).hexdigest() == original["sha256"]
            results.append(
                dict(
                    name=record["name"],
                    success_trace=result["request_id"],
                    denied_traces=denials,
                    hits=len(result["hits"]),
                    embedding_input_tokens=result["usage"]["embedding_input_tokens"],
                    embedding_requests=1,
                    originals_verified=2,
                )
            )
            print(
                "PASS F05 HTTP " + PHASE + ": authorized fragments/denials/original SHA.",
                flush=True,
            )
        save("verified.json", {"fixtures": results})
        print("PASS F05 HTTP: four fixtures/two instances, eight originals; no content output.")
    finally:
        if api is not None:
            api.close()
        if humans is not None:
            humans.close()


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    try:
        run()
    except Exception:
        print("F05 HTTP " + PHASE + " REFUSED; resources retained.")
        raise SystemExit(1) from None
