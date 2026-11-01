"""Real filesystem/locking and adversarial deliveries; all credentials synthetic."""

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

from rag_platform.providers.application_handoff import (
    NAME,
    FileApplicationStore,
    publish,
    read_record,
)
from rag_platform.providers.secrets import SecretErrorCode, SecretStoreError

SYNTHETIC = "synthetic-application-bearer"


def record(token=SYNTHETIC, **changes):
    now = time.time()
    return {"version": 1, "token": token, "issued_at": now, "expires_at": now + 3590, **changes}


@pytest.fixture
def delivery(tmp_path):
    tmp_path.chmod(0o700)
    for name in ("consumer.lock", "issuer.lock"):
        path = tmp_path / name
        path.write_bytes(b"1")
        path.chmod(0o600)
    publish(tmp_path, record())
    return tmp_path


class Client:
    def __init__(self, _, __):
        self.token, self.revoked, self.closed, self.reads = None, False, False, 0
        self.denied = False
        self.fail_revoke = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def attach_application(self, token):
        if token == "synthetic-wrong-profile":
            raise SecretStoreError(SecretErrorCode.DENIED)
        self.token = token

    def read(self, ref):
        self.reads += 1
        if self.denied:
            raise SecretStoreError(SecretErrorCode.DENIED)
        return ref

    def revoke(self):
        self.revoked = True
        if self.fail_revoke:
            raise SecretStoreError(SecretErrorCode.UNAVAILABLE)

    def close(self):
        self.closed = True


def factory_log():
    clients = []

    def factory(*args):
        client = Client(*args)
        clients.append(client)
        return client

    return clients, factory


def consumer(delivery, factory):
    return FileApplicationStore(
        delivery, "https://synthetic", Path("/synthetic-ca"), factory=factory
    )


def test_delivery_is_private_atomic_and_never_prints_bearer(delivery):
    clients, factory = factory_log()
    store = consumer(delivery, factory)
    try:
        assert store.read("synthetic-ref") == "synthetic-ref"
        assert repr(store) == "FileApplicationStore(<redacted>)"
        assert SYNTHETIC not in repr(store)
        assert (delivery / NAME).stat().st_mode & 0o777 == 0o600
        assert clients[0].token == SYNTHETIC
    finally:
        store.close()
    assert clients[0].revoked and clients[0].closed


def test_second_consumer_refused_and_close_releases_lock(delivery):
    _, factory = factory_log()
    first = consumer(delivery, factory)
    with pytest.raises(SecretStoreError):
        consumer(delivery, factory)
    first.close()
    next_store = consumer(delivery, factory)
    next_store.close()


@pytest.mark.parametrize(
    "changes",
    [
        {"version": True},
        {"version": 2},
        {"extra": "rejected"},
        {"token": ""},
        {"token": "line\nbreak"},
        {"token": "ñ"},
        {"token": "a" * 4097},
        {"issued_at": float("nan")},
        {"expires_at": float("inf")},
        {"issued_at": True},
        {"expires_at": time.time() + 7200},
    ],
)
def test_bad_delivery_never_attaches_or_reads(delivery, changes):
    payload = record(**changes)
    (delivery / NAME).write_text(json.dumps(payload))
    clients, factory = factory_log()
    store = consumer(delivery, factory)
    try:
        with pytest.raises(SecretStoreError):
            store.read("synthetic-ref")
        assert clients == []
    finally:
        store.close()


def test_missing_expired_or_unsafe_file_cannot_use_hot_client(delivery):
    clients, factory = factory_log()
    store = consumer(delivery, factory)
    try:
        store.read("first")
        (delivery / NAME).unlink()
        with pytest.raises(SecretStoreError):
            store.read("missing")
        publish(delivery, record(issued_at=time.time() - 3600, expires_at=time.time() - 1))
        with pytest.raises(SecretStoreError):
            store.read("expired")
        publish(delivery, record())
        (delivery / NAME).chmod(0o644)
        with pytest.raises(SecretStoreError):
            store.read("unsafe")
        assert len(clients) == 1 and clients[0].reads == 1
    finally:
        store.close()


@pytest.mark.parametrize("kind", ["symlink", "hardlink"])
def test_linked_bearer_is_never_consumed(delivery, kind):
    target = delivery / "synthetic-copy"
    (delivery / NAME).rename(target)
    if kind == "symlink":
        (delivery / NAME).symlink_to(target)
    else:
        os.link(target, delivery / NAME)
    clients, factory = factory_log()
    store = consumer(delivery, factory)
    try:
        with pytest.raises(SecretStoreError):
            store.read("ref")
        assert clients == []
        with pytest.raises(SecretStoreError):
            publish(delivery, record("new"))
        assert target.read_text()
    finally:
        store.close()


def test_changed_invalid_profile_has_no_fallback_and_does_not_revoke_supplied_token(delivery):
    clients, factory = factory_log()
    store = consumer(delivery, factory)
    try:
        store.read("first")
        publish(delivery, record("synthetic-wrong-profile"))
        with pytest.raises(SecretStoreError):
            store.read("second")
        assert clients[0].reads == 1 and not clients[0].revoked
        assert clients[1].closed and not clients[1].revoked
        publish(delivery, record("synthetic-replacement"))
        assert store.read("third") == "third"
        assert clients[0].revoked and clients[0].closed
        assert clients[2].reads == 1
    finally:
        store.close()


def test_revoked_warm_identity_has_no_reattach_or_fallback(delivery):
    clients, factory = factory_log()
    store = consumer(delivery, factory)
    try:
        store.read("first")
        clients[0].denied = True
        for _ in range(2):
            with pytest.raises(SecretStoreError):
                store.read("denied")
        assert len(clients) == 1
    finally:
        store.close()


def test_failed_retirement_revokes_candidate_and_serves_neither_identity(delivery):
    clients, factory = factory_log()
    store = consumer(delivery, factory)
    try:
        store.read("first")
        clients[0].fail_revoke = True
        publish(delivery, record("synthetic-replacement"))
        with pytest.raises(SecretStoreError):
            store.read("refused")
        assert all(c.revoked and c.closed for c in clients)
        assert clients[1].reads == 0
    finally:
        store.close()


def test_atomic_publish_failure_retains_previous_and_cleans_temp(delivery, monkeypatch):
    original = read_record(delivery / NAME)
    monkeypatch.setattr(os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError()))
    with pytest.raises(OSError):
        publish(delivery, record("synthetic-replacement"))
    assert read_record(delivery / NAME) == original
    assert sorted(p.name for p in delivery.iterdir()) == [NAME, "consumer.lock", "issuer.lock"]


def test_concurrent_reads_share_one_verified_client(delivery):
    clients, factory = factory_log()
    store = consumer(delivery, factory)
    try:
        with ThreadPoolExecutor(max_workers=2) as threads:
            assert list(threads.map(store.read, ["one", "two"])) == ["one", "two"]
        assert len(clients) == 1 and clients[0].reads == 2
    finally:
        store.close()


def test_unsafe_directory_and_lock_rejected_before_store(delivery):
    clients, factory = factory_log()
    delivery.chmod(0o755)
    with pytest.raises(SecretStoreError):
        consumer(delivery, factory)
    delivery.chmod(0o700)
    (delivery / "consumer.lock").chmod(0o644)
    with pytest.raises(SecretStoreError):
        consumer(delivery, factory)
    assert clients == []


def test_issuer_ensure_reuses_valid_delivery_without_grant(delivery, monkeypatch):
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
    import f03_application_issue as issuer

    clients, factory = factory_log()
    monkeypatch.setattr(issuer, "ApplicationSecretStore", factory)
    day = SimpleNamespace(_request=lambda *a, **k: pytest.fail("unexpected grant"))
    assert issuer.ensure(day, delivery)["created"] is False
    assert len(clients) == 1 and clients[0].closed and not clients[0].revoked
