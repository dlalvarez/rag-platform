"""T001 / V03 partial: transport failures, CAS, version and authentication, no network."""

import ssl
import uuid
from pathlib import Path

import httpx
import pytest

from rag_platform.providers.secrets import (
    Credential,
    OpenBaoSecretStore,
    SecretErrorCode,
    SecretStoreError,
)
from rag_platform.tenancy.contracts import SecretRef

CA = Path(ssl.get_default_verify_paths().cafile)
MARKER = "synthetic-sensitive-marker-never-log"


def make_store(handler):
    return OpenBaoSecretStore("https://openbao:8200", CA, transport=httpx.MockTransport(handler))


def auth():
    return {
        "auth": {
            "client_token": MARKER,
            "lease_duration": 900,
            "policies": ["default", "f01-provisioner"],
        }
    }


def test_cas_and_exact_version():
    ref_id = uuid.uuid4()
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.path.endswith("/login"):
            return httpx.Response(200, json=auth())
        if request.method == "POST":
            assert b'"cas":0' in request.content
            return httpx.Response(200, json={"data": {"version": 1}})
        assert request.url.params["version"] == "1"
        assert request.headers["X-Vault-Token"] == MARKER
        return httpx.Response(
            200,
            json={
                "data": {
                    "metadata": {"version": 1, "destroyed": False, "deletion_time": ""},
                    "data": {"username": "synthetic", "password": MARKER},
                }
            },
        )

    with make_store(handler) as store:
        store.login("role", "one-use-id")
        ref = store.write(ref_id, Credential("synthetic", MARKER), expected_version=0)
        assert ref == SecretRef(ref_id, 1)
        assert store.read(ref).password == MARKER
        assert MARKER not in repr(store) + repr(store.read(ref))
        with pytest.raises(SecretStoreError):
            store.write("../../other", Credential("synthetic", MARKER), expected_version=0)
    assert len(seen) == 4


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (403, SecretErrorCode.DENIED),
        (404, SecretErrorCode.NOT_FOUND),
        (503, SecretErrorCode.UNAVAILABLE),
        (307, SecretErrorCode.UNAVAILABLE),
    ],
)
def test_failures_never_echo_server_body_or_fallback(status, code, caplog):
    count = 0

    def handler(request):
        nonlocal count
        count += 1
        if request.url.path.endswith("/login"):
            return httpx.Response(200, json=auth())
        return httpx.Response(
            status, json={"errors": [MARKER]}, headers={"Location": "https://untrusted.example"}
        )

    with make_store(handler) as store:
        store.login("role", "id")
        with pytest.raises(SecretStoreError) as raised:
            store.read(SecretRef(uuid.uuid4(), 1))
        assert raised.value.code == code
        assert MARKER not in str(raised.value) + caplog.text
        assert raised.value.__cause__ is None
    assert count == 2


def test_root_or_extra_policy_rejected_before_secret_access():
    def handler(request):
        result = auth()
        result["auth"]["policies"] += ["root"]
        return httpx.Response(200, json=result)

    with make_store(handler) as store, pytest.raises(SecretStoreError):
        store.login("role", "id")


def test_expired_token_does_not_retry_with_consumed_secret_id(monkeypatch):
    now = [100.0]
    monkeypatch.setattr("rag_platform.providers.secrets.time.monotonic", lambda: now[0])
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=auth())

    with make_store(handler) as store:
        store.login("role", "id")
        now[0] += 901
        with pytest.raises(SecretStoreError) as raised:
            store.read(SecretRef(uuid.uuid4(), 1))
        assert raised.value.code == SecretErrorCode.DENIED
    assert len(calls) == 1


def test_cas_conflict_is_not_success():
    def handler(request):
        if request.url.path.endswith("/login"):
            return httpx.Response(200, json=auth())
        return httpx.Response(400, json={"errors": [MARKER]})

    with make_store(handler) as store:
        store.login("role", "id")
        with pytest.raises(SecretStoreError) as raised:
            store.write(uuid.uuid4(), Credential("synthetic", MARKER), expected_version=0)
        assert raised.value.code == SecretErrorCode.CONFLICT


@pytest.mark.parametrize(
    "metadata",
    [
        {"version": 2},
        {"version": 1, "destroyed": True},
        {"version": 1, "deletion_time": "2026-10-30"},
    ],
)
def test_wrong_deleted_or_destroyed_version_is_never_used(metadata):
    def handler(request):
        if request.url.path.endswith("/login"):
            return httpx.Response(200, json=auth())
        return httpx.Response(
            200,
            json={
                "data": {
                    "metadata": metadata,
                    "data": {"username": "synthetic", "password": MARKER},
                }
            },
        )

    with make_store(handler) as store:
        store.login("role", "id")
        with pytest.raises(SecretStoreError):
            store.read(SecretRef(uuid.uuid4(), 1))


def test_tls_and_endpoint_validation():
    for endpoint in (
        "http://openbao:8200",
        "https://user:password@openbao:8200",
        "https://openbao:8200/v1/f01",
        "https://openbao:8200?token=value",
    ):
        with pytest.raises(SecretStoreError):
            OpenBaoSecretStore(endpoint, CA)


def test_timeout_is_sanitized(caplog):
    def handler(request):
        if request.url.path.endswith("/login"):
            return httpx.Response(200, json=auth())
        raise httpx.ReadTimeout(MARKER)

    with make_store(handler) as store:
        store.login("role", "id")
        with pytest.raises(SecretStoreError) as raised:
            store.read(SecretRef(uuid.uuid4(), 1))
        assert MARKER not in str(raised.value) + caplog.text


def test_non_json_response_is_sanitized():
    def handler(request):
        if request.url.path.endswith("/login"):
            return httpx.Response(200, json=auth())
        return httpx.Response(200, text=MARKER)

    with make_store(handler) as store:
        store.login("role", "id")
        with pytest.raises(SecretStoreError) as raised:
            store.read(SecretRef(uuid.uuid4(), 1))
        assert MARKER not in str(raised.value)
