"""HTTP shape/privacy with real offline authority/ACL; fake embeddings are explicit."""

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from test_f05_embedding_worker import setup  # noqa: F401
from test_f05_search_service import case  # noqa: F401

from rag_platform.control.identity_models import Membership
from rag_platform.documents.errors import DocumentError
from rag_platform.embeddings import api
from rag_platform.identity_api import create_app


@pytest.fixture
def http(case, monkeypatch):  # noqa: F811
    s = case.s
    app = create_app(s.control, SimpleNamespace(), b"k" * 32)
    app.dependency_overrides[app.state.principal_dependency] = lambda: s.actor

    @app.exception_handler(DocumentError)
    async def error(request, exception):
        return app.state.error_response(request, exception.code, exception.status)

    calls = []

    def provider(*args):
        calls.append(args)
        return s.provider

    monkeypatch.setattr(api, "QueryClient", provider)
    runtime = SimpleNamespace(authority=s.runtime.authority, repositories=case.service.repositories)
    api.install(app, runtime, "/private-not-opened/qwen.sock")
    data = dict(
        repository_ids=[str(s.repo)],
        space_id=str(case.space),
        query="PRIVATE_QUERY_CANARY",
        top_k=3,
    )
    with TestClient(app) as client:
        yield SimpleNamespace(
            client=client,
            app=app,
            case=case,
            calls=calls,
            data=data,
            url=f"/api/v1/tenants/{s.tenant}/search",
        )


def send(http, **changes):
    return http.client.post(http.url, json={**http.data, **changes})


def test_success_provenance_usage_trace_and_no_private_payload(http, caplog):
    result = send(http)
    assert result.status_code == 200
    value = result.json()
    assert set(value) == {"request_id", "space_id", "hits", "usage"}
    assert result.headers["cache-control"] == "no-store"
    assert result.headers["x-request-id"] == value["request_id"]
    assert value["space_id"] == http.data["space_id"]
    assert set(value["hits"][0]) == {
        "repository_id",
        "document_id",
        "version_id",
        "chunk_id",
        "score",
        "excerpt",
        "page",
        "section",
    }
    assert value["hits"][0]["section"] == ["Title"]
    assert value["usage"]["embedding_requests"] == 1
    assert "PRIVATE_QUERY_CANARY" not in result.text + caplog.text
    assert "vectors" not in result.text and "answer" not in value
    assert http.calls[0][3] != http.case.trace


@pytest.mark.parametrize(
    "changes",
    [
        {"repository_ids": []},
        {"repository_ids": [str(uuid4())] * 2},
        {"repository_ids": [str(uuid4())] * 17},
        {"repository_ids": "wrong"},
        {"repository_ids": [1]},
        {"repository_ids": [str(uuid4()), "CANARY_BAD_UUID"]},
        {"space_id": "CANARY_BAD_UUID"},
        {"space_id": str(uuid4()).replace("-", "x")},
        {"space_id": 1},
        {"query": ""},
        {"query": " "},
        {"query": None},
        {"query": "x" * 8193},
        {"query": "\0"},
        {"top_k": True},
        {"top_k": 0},
        {"top_k": 51},
        {"top_k": "3"},
        {"top_k": 1.5},
        {"assistant_id": str(uuid4())},
        {"endpoint": "CANARY_ENDPOINT"},
    ],
)
def test_invalid_input_never_constructs_provider(http, changes):
    result = send(http, **changes)
    assert result.status_code == 422
    assert not http.calls and not http.case.s.provider.calls
    assert "CANARY" not in result.text
    assert result.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "raw",
    [
        '{"query":NaN}',
        "[]",
        '{"query":"first","query":"second"}',
        '{"query":',
        '{"top_k":Infinity}',
        '{"query":"\\ud800"}',
    ],
)
def test_malformed_json_is_closed(http, raw):
    result = http.client.post(http.url, content=raw, headers={"content-type": "application/json"})
    assert result.status_code == 422 and not http.calls


@pytest.mark.parametrize(
    "headers",
    [
        {"content-type": "text/plain"},
        {"content-encoding": "gzip"},
        {"content-length": "999999"},
        {"content-length": "bad"},
        {"content-length": "1", "transfer-encoding": "chunked"},
    ],
)
def test_framing_rejects_before_provider(http, headers):
    result = http.client.post(
        http.url,
        content=json.dumps(http.data),
        headers={"content-type": "application/json", **headers},
    )
    assert result.status_code in (413, 422) and not http.calls


def test_streamed_body_size_and_query_parameters_are_bounded(http):
    result = http.client.post(
        http.url, content=b"x" * 65537, headers={"content-type": "application/json"}
    )
    assert result.status_code == 413 and not http.calls
    result = http.client.post(http.url + "?host=CANARY", json=http.data)
    assert result.status_code == 422 and not http.calls and "CANARY" not in result.text


def test_foreign_repository_precedes_inference(http):
    result = send(http, repository_ids=[http.data["repository_ids"][0], str(uuid4())])
    assert result.status_code in (403, 404)
    assert not http.case.s.provider.calls and not http.case.counts


def test_membership_denial_precedes_body_and_provider(http):
    with http.case.s.control.begin() as c:
        c.execute(sa.update(Membership).values(state="REVOKED"))
    result = http.client.post(http.url, content=b"not-json")
    assert result.status_code == 403 and not http.calls


def test_revoked_membership_during_inference_returns_no_fragments(http):
    def revoke(_texts):
        with http.case.s.control.begin() as c:
            c.execute(sa.update(Membership).values(state="REVOKED"))

    http.case.s.provider.callback = revoke
    result = send(http)
    assert result.status_code == 403 and "PRIVATE_RESULT" not in result.text
    assert len(http.case.s.provider.calls) == 1


def test_dependency_error_does_not_leak_body_or_traceback(http, monkeypatch):
    def broken(*_args):
        raise RuntimeError("PRIVATE_QUERY_CANARY provider secret")

    monkeypatch.setattr(http.case.s.provider, "count_tokens", broken)
    result = send(http)
    assert result.status_code == 503 and "CANARY" not in result.text
    assert "traceback" not in result.text.lower()


def test_empty_hits_and_incoming_trace_are_safe(http, monkeypatch):
    from rag_platform.embeddings import search

    monkeypatch.setattr(search, "exact", lambda *_args: ())
    result = http.client.post(http.url, json=http.data, headers={"X-Request-ID": "CANARY"})
    assert result.status_code == 200 and result.json()["hits"] == []
    assert result.headers["x-request-id"] != "CANARY"


def test_route_absent_until_installed(http):
    app = create_app(http.case.s.control, SimpleNamespace(), b"k" * 32)
    with TestClient(app) as client:
        assert client.post(http.url, json=http.data).status_code == 404


def test_missing_identity_is_401_before_provider(http):
    http.app.dependency_overrides.clear()
    result = http.client.post(http.url, json=http.data)
    assert result.status_code == 401 and not http.calls
    assert result.headers["www-authenticate"] == "Bearer"


def test_all_repos_authorized_before_count_and_infer(http):
    result = send(http, repository_ids=[str(uuid4())])
    assert result.status_code in (403, 404)
    assert not http.case.counts and not http.case.s.provider.calls


def test_input_exact_unicode_character_limit_reaches_token_budget(http):
    result = send(http, query=chr(0x1F9EA) * 8192)
    # The fixture counts this whitespace-free string as one token.
    assert result.status_code == 200 and http.calls
    assert len(http.case.s.provider.calls) == 1
    result = send(http, query=chr(0x1F9EA) * 8193)
    assert result.status_code == 422 and len(http.calls) == 1


def test_http_slots_are_bounded_and_released(http, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Condition, Event

    entered, release, count = Condition(), Event(), [0]

    def paused(*_args):
        with entered:
            count[0] += 1
            entered.notify_all()
        assert release.wait(10)
        from rag_platform.embeddings.search import SearchResult

        return SearchResult((http.case.hit,), 1)

    # This test targets HTTP admission, not concurrency assertions of the SQL fixture.
    monkeypatch.setattr(api, "SearchService", lambda *_args: SimpleNamespace(search=paused))
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(send, http)
        second = executor.submit(send, http)
        try:
            with entered:
                assert entered.wait_for(lambda: count[0] == 2, timeout=5)
            rejected = send(http)
            assert rejected.status_code == 429
        finally:
            release.set()
        assert first.result().status_code == second.result().status_code == 200
    assert send(http).status_code == 200


def test_response_bound_never_returns_oversized_content(http, monkeypatch):
    monkeypatch.setattr(api, "MAX_RESPONSE", 1)
    result = send(http)
    assert result.status_code == 503 and "PRIVATE_RESULT" not in result.text
