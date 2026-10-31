"""ACC-01..05: one-use handoff, no fallback, real provider transport and cleanup."""

import importlib
import json
import multiprocessing
import os
import ssl
import time
from contextlib import contextmanager
from pathlib import Path

import httpx
import pytest

from rag_platform.providers.secrets import OpenBaoSecretStore, SecretStoreError

ROOT = Path(__file__).resolve().parents[3]
MARKER = "synthetic-sensitive-never-display"


@pytest.fixture
def access(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    module = importlib.import_module("f01_access")
    folder = tmp_path / "handoff"
    folder.mkdir(mode=0o700)
    monkeypatch.setattr(module, "DIRECTORY", folder)
    return module


def grant(access, **overrides):
    body = {
        "purpose": "verify",
        "issued_at": time.time() - 1,
        "expires_at": time.time() + 120,
        "role_id": "synthetic-role",
        "secret_id": MARKER,
    }
    body.update(overrides)
    path = access.DIRECTORY / access.NAME
    path.write_text(json.dumps(body))
    path.chmod(0o600)
    return path


def test_grant_is_consumed_once(access):
    path = grant(access)
    assert access.consume("verify") == ("synthetic-role", MARKER)
    assert not path.exists()
    with pytest.raises(FileNotFoundError):
        access.consume("verify")


@pytest.mark.parametrize(
    "changes",
    [
        {"purpose": "cli-check"},
        {"expires_at": time.time() - 20},
        {"expires_at": time.time() + 900},
        {"issued_at": time.time() + 30},
        {"secret_id": ""},
        {"role_id": []},
        {"extra": MARKER},
        {"expires_at": float("nan")},
        {"issued_at": True},
    ],
)
def test_invalid_grant_is_removed_before_authentication(access, changes):
    path = grant(access, **changes)
    with pytest.raises(access.AccessError):
        access.consume("verify")
    assert not path.exists()


def test_bad_json_is_consumed(access):
    path = grant(access)
    path.write_text("{")
    with pytest.raises(ValueError):
        access.consume("verify")
    assert not path.exists()


@pytest.mark.parametrize("kind", ["file_mode", "directory_mode", "symlink", "hardlink", "large"])
def test_unsafe_files_never_read(access, tmp_path, kind):
    path = grant(access)
    if kind == "file_mode":
        path.chmod(0o640)
    elif kind == "directory_mode":
        access.DIRECTORY.chmod(0o750)
    elif kind == "symlink":
        target = tmp_path / "target"
        path.rename(target)
        path.symlink_to(target)
    elif kind == "hardlink":
        os.link(path, tmp_path / "other")
    else:
        path.write_text(MARKER * 1000)
    with pytest.raises((access.AccessError, OSError)):
        access.consume("verify")


def _consume_worker(folder, queue):
    import f01_access

    f01_access.DIRECTORY = Path(folder)
    try:
        f01_access.consume("verify")
        queue.put("consumed")
    except FileNotFoundError:
        queue.put("missing")


def test_two_processes_cannot_consume_same_grant(access):
    grant(access)
    context = multiprocessing.get_context("fork")
    queue = context.Queue()
    processes = [
        context.Process(target=_consume_worker, args=(str(access.DIRECTORY), queue))
        for _ in range(2)
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(5)
        assert process.exitcode == 0
    assert sorted(queue.get(timeout=1) for _ in processes) == ["consumed", "missing"]


def test_entrypoint_failure_does_not_prompt_or_echo(access, monkeypatch, capsys):
    monkeypatch.setattr(access, "login_operator", lambda _: pytest.fail("fallback login"))
    with pytest.raises(SystemExit) as error:
        access.main(["verify"])
    assert MARKER not in str(error.value) + capsys.readouterr().out
    assert "sin detalles sensibles" in str(error.value)


def test_existing_grant_does_not_authenticate_or_overwrite(access, monkeypatch):
    path = grant(access)
    before = path.read_bytes()
    monkeypatch.setattr(access, "tty_required", lambda: None)
    monkeypatch.setattr(access, "client", lambda: pytest.fail("existing grant authenticated"))
    with pytest.raises(access.AccessError):
        access.issue("verify")
    assert path.read_bytes() == before


def test_issuance_uses_operator_only_in_terminal_and_revokes(access, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(access, "tty_required", lambda: calls.append("tty"))
    monkeypatch.setattr(access, "client", lambda: _client())
    monkeypatch.setattr(access, "require_unsealed", lambda _: None)
    monkeypatch.setattr(access, "login_operator", lambda _: "operator-synthetic")

    def call(_http, _method, path, token=None, payload=None):
        calls.append(path)
        if path.endswith("lookup-self"):
            return {"data": {"policies": ["default", "f01-operator"]}}
        if path.endswith("role-id"):
            return {"data": {"role_id": "role"}}
        if path.endswith("secret-id"):
            return {
                "data": {
                    "secret_id": MARKER,
                    "secret_id_ttl": 600,
                    "secret_id_num_uses": 1,
                }
            }
        assert path.endswith("revoke-self")
        return {}

    monkeypatch.setattr(access, "call", call)
    access.issue("verify")
    assert calls[0] == "tty" and calls[-1] == "auth/token/revoke-self"
    assert access.consume("verify") == ("role", MARKER)
    assert MARKER not in capsys.readouterr().out


@contextmanager
def _client():
    yield object()


@pytest.mark.parametrize("fail", [False, True])
def test_delegated_session_revokes_on_success_and_exception(access, monkeypatch, fail):
    grant(access)
    events = []

    class Store:
        def __init__(self, *_):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            events.append("closed")

        def login(self, role, secret):
            assert role == "synthetic-role" and secret == MARKER
            events.append("login")

        def revoke(self):
            events.append("revoked")

    monkeypatch.setattr(access, "OpenBaoSecretStore", Store)
    try:
        with access.session("verify"):
            if fail:
                raise RuntimeError("simulated battery failure")
    except RuntimeError:
        assert fail
    assert events == ["login", "revoked", "closed"]


@pytest.mark.parametrize("lookup_status", [403, 200])
def test_revoke_verifies_server_rejection_and_clears_bearer(lookup_status):
    seen = []

    def handler(request):
        seen.append(request.url.path)
        if request.url.path.endswith("/login"):
            return httpx.Response(
                200,
                json={
                    "auth": {
                        "client_token": MARKER,
                        "lease_duration": 900,
                        "policies": ["default", "f01-provisioner"],
                    }
                },
            )
        assert request.headers["X-Vault-Token"] == MARKER
        return httpx.Response(204 if request.url.path.endswith("revoke-self") else lookup_status)

    with OpenBaoSecretStore(
        "https://openbao:8200",
        Path(ssl.get_default_verify_paths().cafile),
        transport=httpx.MockTransport(handler),
    ) as store:
        store.login("role", "used")
        if lookup_status == 403:
            store.revoke()
        else:
            with pytest.raises(SecretStoreError):
                store.revoke()
        assert store._token is None
        assert store._expires_at == 0
    assert seen[-2:] == ["/v1/auth/token/revoke-self", "/v1/auth/token/lookup-self"]


def test_missing_grant_never_opens_store(access, monkeypatch):
    monkeypatch.setattr(access, "OpenBaoSecretStore", lambda *_: pytest.fail("store opened"))
    with pytest.raises(FileNotFoundError), access.session("verify"):
        pass


def test_delegated_service_uses_distinct_actor_and_never_operator_login(access, monkeypatch):
    import f01_admin

    events = []

    class Resource:
        def dispose(self):
            events.append("disposed")

        def close(self):
            events.append("closed")

    @contextmanager
    def delegated_session(purpose):
        assert purpose == "cli-check"
        events.append("session")
        try:
            yield "store", "role", "used"
        finally:
            events.append("revoked")

    monkeypatch.setattr(access, "session", delegated_session)
    monkeypatch.setattr(f01_admin, "client", _client)
    monkeypatch.setattr(f01_admin, "require_unsealed", lambda _: None)
    monkeypatch.setattr(f01_admin, "catalog", Resource)
    monkeypatch.setattr(f01_admin, "StorageTarget", lambda *_: Resource())
    monkeypatch.setattr(f01_admin, "login_operator", lambda _: pytest.fail("operator fallback"))
    monkeypatch.setattr(f01_admin, "Administration", lambda *args, **kwargs: args)
    with pytest.raises(RuntimeError, match="battery failure"):
        with f01_admin.operator_service("check", delegated=True) as arguments:
            assert arguments[1] == f01_admin.DELEGATED_ACTOR != f01_admin.ACTOR
            assert arguments[2] == "store"
            raise RuntimeError("battery failure")
    assert events == ["session", "revoked", "disposed", "closed"]


def test_input_errors_do_not_echo_values(access, capsys):
    with pytest.raises(SystemExit):
        access.main(["verify", MARKER])
    assert MARKER not in capsys.readouterr().err


def test_handoff_profile_has_no_sql_or_iam_bootstrap_mounts():
    import yaml

    services = yaml.safe_load((ROOT / "ops/f01/compose.yaml").read_text())["services"]
    assert not services["tools"].get("secrets")
    assert not services["access"].get("secrets")
    assert set(services["access-cli"]["secrets"]) == {
        "control_migrator_password",
        "storage_admin_user",
        "storage_admin_password",
    }
    assert "postgres_password" not in services["access-cli"]["secrets"]
    assert "postgres2_password" not in services["access-cli"]["secrets"]
