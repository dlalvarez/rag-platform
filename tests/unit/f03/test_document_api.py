"""HTTP boundaries on the real adapter; synthetic repositories and identities only."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from rag_platform.documents.api import OriginalResponse, install
from rag_platform.documents.content import Download
from rag_platform.documents.errors import DocumentError
from rag_platform.documents.receipt import Received
from rag_platform.documents.validation import MAX_BYTES, UploadSpool
from rag_platform.identity_api import create_app


@pytest.fixture
def api():
    actor, tenant, repo = uuid4(), uuid4(), uuid4()
    state = SimpleNamespace(events=[], denied=False, failure=False, downloads=[])
    ctx = SimpleNamespace(principal_id=actor, tenant_id=tenant)

    def authorize(*args):
        state.events.append("authorize")
        return ctx

    def preflight(*args):
        state.events.append("preflight")
        if state.denied:
            raise DocumentError("ROLE_DENIED")

    def receive(context, trace, repository, key, file):
        state.events.append("receive")
        if state.failure:
            raise DocumentError()
        return Received(
            {"sha256": file.content_hash, "byte_size": file.byte_size, "state": "RECEIVED"}, True
        )

    def original(*args):
        state.events.append("original")
        spool = UploadSpool("synthetic.txt", "text/plain")
        spool.accept(b"synthetic original\n")
        download = Download(spool, spool.finish())
        state.downloads.append(download)
        return download

    def list_page(*args, **kwargs):
        state.events.append("list")
        return {"items": [], "next_cursor": None}

    runtime = SimpleNamespace(
        authority=SimpleNamespace(authorize=authorize),
        receipts=SimpleNamespace(preflight=preflight, receive=receive),
        repositories=SimpleNamespace(list=list_page),
        documents=SimpleNamespace(original=original, list=list_page),
    )
    state.runtime = runtime
    app = create_app(SimpleNamespace(), SimpleNamespace(), b"k" * 32)
    app.dependency_overrides[app.state.principal_dependency] = lambda: actor
    install(app, runtime)
    with TestClient(app) as client:
        yield client, state, f"/api/v1/tenants/{tenant}/repositories/{repo}"


def headers(**extra):
    return {"Content-Type": "text/plain", "Idempotency-Key": "synthetic-key-123456", **extra}


def upload(client, base, body=b"synthetic\n", **kwargs):
    return client.post(
        base + "/documents?filename=synthetic.txt", content=body, headers=headers(**kwargs)
    )


def test_upload_uses_real_validator_and_logical_response(api):
    client, state, base = api
    response = upload(client, base)
    assert response.status_code == 201
    assert response.json()["document"]["byte_size"] == 10
    assert state.events == ["authorize", "preflight", "receive"]
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-request-id"] == response.json()["request_id"]


@pytest.mark.parametrize("body", [b"", b"\xff", b"%PDF-1.7\n%%EOF\n"])
def test_invalid_format_never_enters_receipt(api, body):
    client, state, base = api
    response = upload(client, base, body)
    assert response.status_code == 422
    assert "receive" not in state.events


@pytest.mark.parametrize(
    "extra",
    [
        {"Idempotency-Key": "short"},
        {"Content-Encoding": "gzip"},
        {"Content-Length": "not-a-number"},
        {"Content-Length": "-1"},
    ],
)
def test_bad_headers_rejected_without_receipt(api, extra):
    client, state, base = api
    response = upload(client, base, **extra)
    assert response.status_code == 422
    assert "receive" not in state.events


def test_declared_and_actual_size_limits(api):
    client, state, base = api
    assert upload(client, base, **{"Content-Length": str(MAX_BYTES + 1)}).status_code == 413
    # Unknown total size, chunked body: actual byte count is still enforced.
    response = client.post(
        base + "/documents?filename=synthetic.txt",
        content=iter([b"a" * MAX_BYTES, b"b"]),
        headers=headers(),
    )
    assert response.status_code == 413
    assert "receive" not in state.events


def test_bad_key_is_rejected_before_spool_body(api):
    client, state, base = api
    response = upload(client, base, **{"Idempotency-Key": "short"})
    assert response.status_code == 422
    assert state.events == ["authorize", "preflight"]


def test_acl_denial_precedes_bad_body_and_headers(api):
    client, state, base = api
    state.denied = True
    response = upload(client, base, b"\xff", **{"Idempotency-Key": "short"})
    assert response.status_code == 403
    assert state.events == ["authorize", "preflight"]
    assert "synthetic" not in response.text


def test_json_unknown_fields_duplicate_keys_and_oversize_are_closed(api):
    client, state, base = api
    root = base.rsplit("/", 1)[0]
    for body in (b'{"name":"one","name":"two"}', b"[]", b"{broken", b"x" * 4097):
        response = client.post(root, content=body, headers={"Content-Type": "application/json"})
        assert response.status_code in (413, 422)
        assert "broken" not in response.text
    assert "receive" not in state.events


def test_unknown_query_and_duplicate_filename_are_closed(api):
    client, state, base = api
    for query in ("filename=synthetic.txt&filename=second.txt", "filename=synthetic.txt&extra=x"):
        response = client.post(
            base + "/documents?" + query, content=b"synthetic", headers=headers()
        )
        assert response.status_code == 422
    assert "receive" not in state.events


def test_original_is_attachment_verified_spool_and_closed(api):
    client, state, base = api
    response = client.get(base + f"/documents/{uuid4()}/original")
    assert response.status_code == 200 and response.content == b"synthetic original\n"
    assert response.headers["content-length"] == str(len(response.content))
    assert response.headers["content-type"].startswith("text/plain")
    assert response.headers["content-disposition"].startswith("attachment;")
    assert "filename*=UTF-8''synthetic.txt" in response.headers["content-disposition"]
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"
    assert state.downloads[0].file.file.closed


def test_range_rejected_before_storage(api):
    client, state, base = api
    response = client.get(base + f"/documents/{uuid4()}/original", headers={"Range": "bytes=0-1"})
    assert response.status_code == 422 and "original" not in state.events


def test_slots_released_after_validation_or_dependency_failure(api):
    client, state, base = api
    for _ in range(3):
        assert upload(client, base, b"\xff").status_code == 422
    state.failure = True
    for _ in range(3):
        assert upload(client, base).status_code == 503
    state.failure = False
    assert upload(client, base).status_code == 201


def test_response_cleanup_runs_when_send_fails():
    import asyncio

    spool = UploadSpool("synthetic.txt", "text/plain")
    spool.accept(b"synthetic")
    download = Download(spool, spool.finish())
    releases = []
    response = OriginalResponse(download, lambda: releases.append(True))

    async def send(message):
        raise RuntimeError("synthetic disconnect")

    async def receive():
        return {"type": "http.disconnect"}

    scope = {"type": "http", "asgi": {"spec_version": "2.4"}}
    with pytest.raises(RuntimeError, match="synthetic disconnect"):
        asyncio.run(response(scope, receive, send))
    assert spool.file.closed and releases == [True]


@pytest.mark.parametrize("kind", ["upload", "download"])
def test_http_concurrency_budget_is_two_per_direction(api, kind):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    client, state, base = api
    condition, release = threading.Condition(), threading.Event()
    entered = 0
    owner = state.runtime.receipts if kind == "upload" else state.runtime.documents
    attribute = "receive" if kind == "upload" else "original"
    original = getattr(owner, attribute)

    def held(*args):
        nonlocal entered
        with condition:
            entered += 1
            condition.notify_all()
        assert release.wait(10)
        return original(*args)

    setattr(owner, attribute, held)

    def request():
        if kind == "upload":
            return upload(client, base)
        return client.get(base + f"/documents/{uuid4()}/original")

    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(request) for _ in range(2)]
        try:
            with condition:
                assert condition.wait_for(lambda: entered == 2, timeout=10)
            assert request().status_code == 429
            assert entered == 2
        finally:
            release.set()
        assert [f.result().status_code for f in futures] == (
            [201, 201] if kind == "upload" else [200, 200]
        )
