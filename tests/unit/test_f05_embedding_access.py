"""Readonly handoff deadline and denied access stop new model work."""

from pathlib import Path

import pytest

from rag_platform.embeddings import access
from rag_platform.providers.application_handoff import FileApplicationStore
from rag_platform.providers.secrets import SecretErrorCode, SecretStoreError


@pytest.fixture
def store():
    # Lifecycle/locking is tested by F03; this fixture isolates the new readonly gate.
    result = object.__new__(access.ExpiringStore)
    result.path, result._denied, result._closed = Path("/private-fixture"), False, False
    return result


@pytest.mark.parametrize("remaining,ready", [(179, False), (180, False), (181, True)])
def test_expiry_margin_is_closed_and_returns_only_boolean(store, monkeypatch, remaining, ready):
    monkeypatch.setattr(access.time, "time", lambda: 1000)
    monkeypatch.setattr(
        access,
        "read_record",
        lambda _: {
            "expires_at": 1000 + remaining,
            "token": "PRIVATE_RUNTIME_BEARER",
        },
    )
    assert store.ready() is ready


@pytest.mark.parametrize("code", [SecretErrorCode.DENIED, SecretErrorCode.INVALID])
def test_denied_or_invalid_credentials_require_a_new_consumer(store, monkeypatch, code):
    def denied(*_):
        raise SecretStoreError(code)

    monkeypatch.setattr(FileApplicationStore, "read", denied)
    with pytest.raises(SecretStoreError):
        store.read(None)
    assert not store.ready()


def test_missing_or_invalid_handoff_is_not_retried_as_ready(store, monkeypatch):
    monkeypatch.setattr(
        access,
        "read_record",
        lambda _: (_ for _ in ()).throw(RuntimeError("PRIVATE_RUNTIME_BEARER")),
    )
    assert not store.ready()
