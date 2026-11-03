"""Actual urllib3 retry loop with injected wire outcomes; unit network guard preserved."""

from contextlib import contextmanager
from http.client import RemoteDisconnected
from pathlib import Path

import pytest
from urllib3 import HTTPResponse
from urllib3.connectionpool import HTTPSConnectionPool
from urllib3.exceptions import (
    ConnectTimeoutError,
    MaxRetryError,
    ProtocolError,
    ReadTimeoutError,
    SSLError,
)

from rag_platform.provisioning.storage import StorageTarget


@contextmanager
def transport(monkeypatch, *, disconnects=1, status=403, error=None):
    seen = []
    target = StorageTarget("https://minio:9000", Path("/trusted/ca.crt"))
    url = "https://minio:9000/probe"
    pool = target.http.connection_from_url(url)

    def wire(_pool, _connection, method, _url, **_options):
        seen.append(method)
        if error is not None:
            raise error
        if len(seen) <= disconnects:
            raise ProtocolError("Connection aborted.", RemoteDisconnected("Synthetic disconnect"))
        headers = {"Content-Length": "0"}
        if status == 503:
            headers["Retry-After"] = "0"
        if status == 301:
            headers["Location"] = "/redirect-must-not-follow"
        return HTTPResponse(body=b"", status=status, headers=headers, request_method=method)

    # Keep urllib3's real urlopen/retry loop; replace only wire I/O, never the network guard.
    assert isinstance(pool, HTTPSConnectionPool)
    monkeypatch.setattr(HTTPSConnectionPool, "_make_request", wire)
    try:
        yield target, url, seen
    finally:
        target.close()


@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_read_retries_once_after_remote_disconnect_and_retains_real_denial(monkeypatch, method):
    with transport(monkeypatch) as (target, url, seen):
        response = target.http.urlopen(method, url)
        try:
            assert response.status == 403 and seen == [method, method]
        finally:
            response.close()
            response.release_conn()


@pytest.mark.parametrize("method", ["PUT", "POST", "DELETE", "PATCH"])
def test_write_is_never_replayed_after_body_may_have_reached_server(monkeypatch, method):
    with transport(monkeypatch) as (target, url, seen):
        with pytest.raises(ProtocolError):
            target.http.urlopen(method, url, body=b"synthetic-body")
        assert seen == [method]


@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_read_still_fails_closed_after_second_disconnect(monkeypatch, method):
    with transport(monkeypatch, disconnects=2) as (target, url, seen):
        with pytest.raises(MaxRetryError):
            target.http.urlopen(method, url)
        assert seen == [method, method]


@pytest.mark.parametrize("status", [401, 403, 429, 500, 503, 301])
def test_http_denials_failures_or_redirects_are_not_retried_or_followed(monkeypatch, status):
    with transport(monkeypatch, disconnects=0, status=status) as (target, url, seen):
        response = target.http.urlopen("GET", url)
        try:
            assert response.status == status and seen == ["GET"]
        finally:
            response.close()
            response.release_conn()


def test_tls_trust_and_connect_timeout_unchanged():
    target = StorageTarget("https://minio:9000", Path("/trusted/ca.crt"))
    try:
        config = target.http.connection_pool_kw
        assert config["cert_reqs"] == "CERT_REQUIRED" and config["ca_certs"] == "/trusted/ca.crt"
        assert config["timeout"].connect_timeout == 3 and config["timeout"].read_timeout == 5
        retry = config["retries"]
        assert retry.connect == retry.other == retry.redirect == retry.status == 0
    finally:
        target.close()


@pytest.mark.parametrize(
    "error", [ConnectTimeoutError("Synthetic connect"), SSLError("Synthetic TLS")]
)
def test_connect_or_tls_error_has_one_attempt_without_fallback(monkeypatch, error):
    with transport(monkeypatch, error=error) as (target, url, seen):
        with pytest.raises(MaxRetryError):
            target.http.urlopen("GET", url)
        assert seen == ["GET"]


def test_explicit_redirect_flag_cannot_leave_approved_storage_endpoint(monkeypatch):
    with transport(monkeypatch, disconnects=0, status=301) as (target, url, seen):
        response = target.http.urlopen("GET", url, redirect=True)
        assert response.status == 301 and seen == ["GET"]
        response.close()


@pytest.mark.parametrize(
    "error",
    [
        ProtocolError("PRIVATE_PROVIDER_RESPONSE"),
        RemoteDisconnected("PRIVATE_PROVIDER_RESPONSE"),
        ReadTimeoutError(None, "PRIVATE_PROVIDER_URL", "PRIVATE_PROVIDER_RESPONSE"),
    ],
)
def test_retry_logs_and_errors_never_echo_provider_payload(monkeypatch, caplog, error):
    with transport(monkeypatch, error=error) as (target, url, seen):
        with caplog.at_level("DEBUG", logger="urllib3"):
            with pytest.raises(MaxRetryError) as failure:
                target.http.urlopen("GET", url)
        assert seen == ["GET", "GET"]
        assert "PRIVATE_PROVIDER" not in caplog.text
        assert "PRIVATE_PROVIDER" not in str(failure.value)
