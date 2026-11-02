"""F04 HTTP boundaries, metadata minimization and identity binding, offline."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4, uuid5

import pytest
from fastapi.testclient import TestClient

from rag_platform.documents.api import install
from rag_platform.documents.errors import DocumentError
from rag_platform.documents.pagination import Pagination
from rag_platform.identity_api import create_app
from rag_platform.ingestion.service import VERSION_FIELDS, IngestionService, binding, version_view


@pytest.fixture
def api():
    actor, tenant, document, job = (uuid4() for _ in range(4))
    state = SimpleNamespace(calls=[], denied=False, broken=False)

    def authorize(*args):
        state.calls.append(("authorize", args))
        if state.denied:
            raise DocumentError("ROLE_DENIED")
        return SimpleNamespace(principal_id=actor, tenant_id=tenant)

    def versions(*args, **kwargs):
        state.calls.append(("versions", args, kwargs))
        if state.broken:
            raise DocumentError()
        return {
            "items": [{"version_id": str(document), "state": "READY_FOR_EMBEDDING"}],
            "next_cursor": None,
        }

    def progress(*args):
        state.calls.append(("job", args))
        if state.broken:
            raise DocumentError()
        return {"job_id": str(job), "status": "PENDING"}

    def delete(*args):
        state.calls.append(("delete", args))
        if state.broken:
            raise DocumentError()
        return {"document_id": str(document), "state": "TOMBSTONED"}

    runtime = SimpleNamespace(
        authority=SimpleNamespace(authorize=authorize),
        ingestion=SimpleNamespace(versions=versions, job=progress),
        document_state=SimpleNamespace(delete=delete),
    )
    app = create_app(SimpleNamespace(), SimpleNamespace(), b"k" * 32)
    app.dependency_overrides[app.state.principal_dependency] = lambda: actor
    install(app, runtime)
    with TestClient(app) as client:
        yield client, state, f"/api/v1/tenants/{tenant}", document, job


def test_version_and_job_routes_authorize_and_use_logical_ids(api):
    client, state, base, document, job = api
    result = client.get(base + f"/documents/{document}/versions?limit=2")
    assert result.status_code == 200
    assert result.json()["items"][0]["state"] == "READY_FOR_EMBEDDING"
    assert result.headers["cache-control"] == "no-store"
    assert result.headers["x-request-id"] == result.json()["request_id"]
    assert state.calls[0][0] == "authorize" and state.calls[1][0] == "versions"
    assert state.calls[1][1][2] == document
    assert state.calls[1][2] == {"limit": 2, "cursor": None}
    state.calls.clear()
    result = client.get(base + f"/jobs/{job}")
    assert result.status_code == 200 and result.json()["job"]["status"] == "PENDING"
    assert state.calls[0][0] == "authorize" and state.calls[1][1][2] == job


@pytest.mark.parametrize(
    "suffix",
    [
        "?limit=x",
        "?limit=1000",
        "?limit=-1",
        "?cursor=a&cursor=b",
        "?limit=2&limit=3",
        "?host=private-canary",
    ],
)
def test_version_bad_query_never_queries_service(api, suffix):
    client, state, base, document, _ = api
    result = client.get(base + f"/documents/{document}/versions" + suffix)
    assert result.status_code == 422 and "private-canary" not in result.text
    assert [c[0] for c in state.calls] == ["authorize"]


@pytest.mark.parametrize("path", ["documents/not-a-uuid/versions", "jobs/not-a-uuid"])
def test_uuid_error_is_sanitized(api, path):
    client, state, base, _, _ = api
    result = client.get(base + "/" + path)
    assert result.status_code == 422 and "not-a-uuid" not in result.text
    assert all(c[0] == "authorize" for c in state.calls)


@pytest.mark.parametrize("kind", ["versions", "job", "delete"])
def test_authority_denial_precedes_service(api, kind):
    client, state, base, document, job = api
    state.denied = True
    paths = {
        "versions": f"/documents/{document}/versions",
        "job": f"/jobs/{job}",
        "delete": f"/documents/{document}",
    }
    result = client.request("DELETE" if kind == "delete" else "GET", base + paths[kind])
    assert result.status_code == 403
    assert [c[0] for c in state.calls] == ["authorize"]


@pytest.mark.parametrize("kind", ["versions", "job", "delete"])
def test_dependency_error_is_closed(api, kind):
    client, state, base, document, job = api
    state.broken = True
    path = {
        "versions": f"/documents/{document}/versions",
        "job": f"/jobs/{job}",
        "delete": f"/documents/{document}",
    }[kind]
    result = client.request("DELETE" if kind == "delete" else "GET", base + path)
    assert result.status_code == 503 and result.json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"


def test_delete_reply_and_body_rejection(api):
    client, state, base, document, _ = api
    path = base + f"/documents/{document}"
    result = client.delete(path)
    assert result.status_code == 200 and result.json()["document"]["state"] == "TOMBSTONED"
    state.calls.clear()
    result = client.request("DELETE", path, content=b"private-canary")
    assert result.status_code in (413, 422) and "private-canary" not in result.text
    assert [c[0] for c in state.calls] == ["authorize"]
    state.calls.clear()
    result = client.delete(path + "?purge=true")
    assert result.status_code == 422 and [c[0] for c in state.calls] == ["authorize"]


def test_job_unknown_query_rejected_before_service(api):
    client, state, base, _, job = api
    assert client.get(base + f"/jobs/{job}?lease_token=private-canary").status_code == 422
    assert [c[0] for c in state.calls] == ["authorize"]


def pair():
    version, document, actor = uuid4(), uuid4(), uuid4()
    local = {
        "id": version,
        "document_id": document,
        "kind": "PROCESSED",
        "processing_actor_id": actor,
    }
    envelope = {
        "id": uuid4(),
        "version_id": version,
        "document_id": document,
        "kind": "INGEST",
        "actor_id": actor,
        "idempotency_id": uuid5(version, "F04/intent/v1"),
    }
    return local, envelope


@pytest.mark.parametrize(
    "field", ["document_id", "version_id", "actor_id", "idempotency_id", "kind"]
)
def test_mismatched_envelope_cannot_be_adopted(field):
    local, envelope = pair()
    binding(envelope, local)
    envelope[field] = "wrong" if field == "kind" else uuid4()
    with pytest.raises(DocumentError, match="STATE_CONFLICT"):
        binding(envelope, local)


def test_original_cannot_be_bound_to_processing_job():
    local, envelope = pair()
    local["kind"] = "ORIGINAL"
    with pytest.raises(DocumentError, match="STATE_CONFLICT"):
        binding(envelope, local)


def test_version_output_minimizes_private_columns():
    row = {name: None for name in VERSION_FIELDS}
    row.update(
        id=uuid4(),
        document_id=uuid4(),
        kind="ORIGINAL",
        original_version_id=None,
        content_hash="a" * 64,
        created_at=datetime.now(UTC),
        state="RECEIVED",
        blob_key="private-canary",
        filename="private-canary",
        processing_actor_id=uuid4(),
        text="private-canary",
        lease_token=uuid4(),
    )
    result = version_view(row, None)
    assert result["sha256"] == "a" * 64 and result["job_id"] is None
    assert "private-canary" not in str(result)
    assert (
        not {"blob_key", "filename", "processing_actor_id", "text", "lease_token"} & result.keys()
    )


@pytest.mark.parametrize("changed", ["document", "actor", "tenant"])
def test_version_cursor_is_bound_before_connection(changed):
    context = SimpleNamespace(principal_id=uuid4(), tenant_id=uuid4())
    document, last = uuid4(), uuid4()
    pagination = Pagination(b"k" * 32)
    cursor = pagination.encode(context, "F04/versions:" + str(document), last)
    if changed == "document":
        document = uuid4()
    else:
        context = SimpleNamespace(**vars(context))
        setattr(context, "principal_id" if changed == "actor" else "tenant_id", uuid4())
    repositories = SimpleNamespace(
        authority=SimpleNamespace(profile="ingestion"),
        pagination=pagination,
        _run=lambda *_: pytest.fail("must reject before any connection"),
    )
    with pytest.raises(DocumentError, match="INPUT_INVALID"):
        IngestionService(repositories).versions(context, uuid4(), document, cursor=cursor)
