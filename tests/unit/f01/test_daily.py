"""DAY-01..06: hard deadline, reusable bearer, guarded root setup and restoration."""

import base64
import importlib
import json
import ssl
import time
from pathlib import Path

import httpx
import pytest

from rag_platform.providers.secrets import OpenBaoSecretStore, SecretStoreError

ROOT = Path(__file__).resolve().parents[3]
TOKEN = "synthetic-daily-token-never-print"
KEY = "synthetic-unseal-share"
ROOT_TOKEN = "synthetic-root-token"


@pytest.fixture
def modules(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    access = importlib.import_module("f01_access")
    daily = importlib.import_module("f01_daily")
    setup = importlib.import_module("f01_daily_setup")
    host = importlib.import_module("f01_daily_host")
    folder = tmp_path / "private"
    folder.mkdir(mode=0o700)
    monkeypatch.setattr(access, "DIRECTORY", folder)
    return daily, setup, host, folder


def metadata(**changes):
    created = int(time.time()) - 10
    result = {
        "id": TOKEN,
        "policies": ["default", "f01-provisioner"],
        "path": "auth/approle/login",
        "meta": {"role_name": "f01-dev-day"},
        "creation_ttl": 86400,
        "explicit_max_ttl": 86400,
        "num_uses": 0,
        "creation_time": created,
        "ttl": 86390,
    }
    result.update(changes)
    return result


def store_with(data):
    def handler(request):
        assert request.url.path == "/v1/auth/token/lookup-self"
        assert request.headers["X-Vault-Token"] == TOKEN
        return httpx.Response(200, json={"data": data})

    return OpenBaoSecretStore(
        "https://openbao:8200",
        Path(ssl.get_default_verify_paths().cafile),
        transport=httpx.MockTransport(handler),
    )


def test_daily_bearer_attaches_in_independent_clients_without_login_or_revoke():
    data = metadata()
    for _ in range(2):
        with store_with(data) as store:
            store.attach_day(TOKEN, data["creation_time"] + 86400)
            assert store._token == TOKEN
            assert 86380 < store._expires_at - time.monotonic() < 86400
        assert store._token is None


@pytest.mark.parametrize(
    "changes",
    [
        {"meta": {"role_name": "f01-cli"}},
        {"policies": ["root"]},
        {"path": "auth/userpass/login/diego"},
        {"creation_ttl": 3600},
        {"explicit_max_ttl": 0},
        {"num_uses": 1},
        {"ttl": 0},
        {"ttl": 86401},
        {"ttl": True},
        {"meta": None},
    ],
)
def test_daily_attachment_rejects_wrong_origin_limits_or_permissions(changes):
    data = metadata(**changes)
    with store_with(data) as store:
        with pytest.raises(SecretStoreError):
            store.attach_day(TOKEN, data["creation_time"] + 86400)
        assert store._token is None and store._expires_at == 0


def test_local_deadline_cannot_be_extended():
    data = metadata()
    with store_with(data) as store:
        with pytest.raises(SecretStoreError):
            store.attach_day(TOKEN, data["creation_time"] + 86400 + 1)
        with pytest.raises(SecretStoreError):
            store.attach_day(TOKEN, time.time() - 1)


def write_day(daily, folder, **changes):
    body = {"token": TOKEN, "expires_at": time.time() + 600}
    body.update(changes)
    path = folder / daily.NAME
    path.write_text(json.dumps(body))
    path.chmod(0o600)
    return path


def test_day_read_is_reusable_but_expiry_fails(modules):
    daily, _, _, folder = modules
    path = write_day(daily, folder)
    with importlib.import_module("f01_access").directory() as fd:
        assert daily.read_day(fd) == daily.read_day(fd)
        assert path.exists()
        path.write_text(json.dumps({"token": TOKEN, "expires_at": time.time() - 1}))
        with pytest.raises(RuntimeError):
            daily.read_day(fd)


@pytest.mark.parametrize("kind", ["mode", "symlink", "hardlink"])
def test_daily_file_safety(modules, kind, tmp_path):
    daily, _, _, folder = modules
    path = write_day(daily, folder)
    if kind == "mode":
        path.chmod(0o644)
    elif kind == "symlink":
        target = tmp_path / "target"
        path.rename(target)
        path.symlink_to(target)
    else:
        import os

        os.link(path, tmp_path / "alias")
    with importlib.import_module("f01_access").directory() as fd:
        with pytest.raises((RuntimeError, OSError)):
            daily.read_day(fd)


def test_recovery_host_restores_config_and_restarts_only_openbao_on_failure(
    modules, monkeypatch, tmp_path
):
    _, _, host, _ = modules
    path = tmp_path / "openbao.hcl"
    original = b'ui = false\nlistener "tcp" {\n  tls_min_version = "tls13"\n}\n'
    path.write_bytes(original)
    expected = tmp_path / "expected"
    expected.write_bytes(original)
    monkeypatch.setattr(host, "CONFIG", path)
    monkeypatch.setattr(host, "EXPECTED", expected)
    events = []
    monkeypatch.setattr(host, "restart", lambda: events.append("restart"))

    def rpc(action, **_):
        events.append(action)
        if action == "recover":
            assert b"disable_unauthed_generate_root_endpoints = false" in path.read_bytes()
            raise host.RecoveryError("SIMULATED_FAILURE")
        assert path.read_bytes() == original
        return {"ok": True}

    monkeypatch.setattr(host, "rpc", rpc)
    with pytest.raises(host.RecoveryError):
        host.maintenance(KEY)
    assert path.read_bytes() == original
    assert events == ["restart", "recover", "restart", "restore"]


def test_recovery_refuses_configuration_foreign_change(modules, monkeypatch, tmp_path):
    _, _, host, _ = modules
    path = tmp_path / "live"
    expected = tmp_path / "expected"
    path.write_text("foreign")
    expected.write_text('listener "tcp" {\n}\n')
    monkeypatch.setattr(host, "CONFIG", path)
    monkeypatch.setattr(host, "EXPECTED", expected)
    monkeypatch.setattr(host, "restart", lambda: pytest.fail("restart on conflicting config"))
    with pytest.raises(host.RecoveryError, match="CONFIG_CONFLICT"):
        host.maintenance(KEY)
    assert path.read_text() == "foreign"


def test_recovery_own_ceremony_revokes_root_even_when_configuration_fails(modules, monkeypatch):
    _, setup, _, _ = modules
    otp = "x" * len(ROOT_TOKEN)
    encoded = base64.b64encode(
        bytes(a ^ b for a, b in zip(ROOT_TOKEN.encode(), otp.encode(), strict=True))
    ).decode()
    calls = []
    states = iter([{"started": False}, {"started": True, "nonce": "ours"}])

    def call(_http, method, path, token=None, payload=None):
        calls.append((method, path, token))
        if path == "sys/seal-status":
            return {"n": 1, "t": 1, "sealed": False}
        if method == "GET" and path.endswith("/attempt"):
            return next(states)
        if method == "POST" and path.endswith("/attempt"):
            return {"nonce": "ours", "otp": otp, "required": 1}
        if path.endswith("/update"):
            assert payload == {"nonce": "ours", "key": KEY}
            return {"nonce": "ours", "complete": True, "encoded_token": encoded}
        return {}

    class HTTP:
        def get(self, path, **kwargs):
            if path == "/v1/sys/health":
                return httpx.Response(200)
            assert kwargs["headers"]["X-Vault-Token"] == ROOT_TOKEN
            return httpx.Response(403)

    monkeypatch.setattr(setup, "call", call)
    monkeypatch.setattr(
        setup, "configure", lambda *_: (_ for _ in ()).throw(RuntimeError("failed"))
    )
    with pytest.raises(RuntimeError):
        setup.recover(HTTP(), KEY)
    assert ("POST", "auth/token/revoke-self", ROOT_TOKEN) in calls
    assert calls[-1] == ("DELETE", "sys/generate-root/attempt", None)


def test_recovery_does_not_adopt_existing_ceremony(modules, monkeypatch):
    _, setup, _, _ = modules
    calls = []

    def call(_http, method, path, *_, **__):
        calls.append((method, path))
        return {"n": 1, "t": 1, "sealed": False} if path == "sys/seal-status" else {"started": True}

    monkeypatch.setattr(setup, "call", call)
    monkeypatch.setattr(setup, "wait_active", lambda _: None)
    with pytest.raises(RuntimeError):
        setup.recover(None, KEY)
    assert all(method == "GET" for method, _ in calls)


def test_noninteractive_maintenance_refused_before_secret_read(modules, monkeypatch):
    _, _, host, _ = modules
    monkeypatch.setattr(host.sys, "argv", ["f01_daily_host.py", "configure"])
    monkeypatch.setattr(host.sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(host.getpass, "getpass", lambda *_: pytest.fail("password read"))
    with pytest.raises(SystemExit, match="TTY_REQUIRED"):
        host.main()


def test_daily_role_keeps_short_role_unchanged_and_adds_only_issuance_paths(modules):
    daily, _, _, _ = modules
    assert daily.ROLE_SETTINGS["token_explicit_max_ttl"] == 86400
    assert daily.ROLE_SETTINGS["secret_id_num_uses"] == 1
    baseline = (ROOT / "ops/f01/operator.hcl").read_text()
    updated = (ROOT / "ops/f01/operator-day.hcl").read_text()
    assert updated.startswith(baseline)
    suffix = updated[len(baseline) :]
    assert suffix.count('path "') == 2
    assert '"sudo"' not in suffix and '"delete"' not in suffix
    assert '"auth/approle/role/f01-dev-day"' not in suffix


def test_setup_is_idempotent_and_never_writes_short_role(modules):
    daily, setup, _, _ = modules
    baseline = (ROOT / "ops/f01/operator.hcl").read_text()
    current = {"policy": baseline, "role": None}
    mutations = []
    short = {"token_ttl": 900, "token_max_ttl": 3600, "secret_id_num_uses": 1}

    def handler(request):
        path = request.url.path
        if request.method in ("POST", "PUT"):
            mutations.append(path)
            body = json.loads(request.content)
            if path == "/v1/auth/approle/role/f01-dev-day":
                current["role"] = body
            elif path == "/v1/sys/policies/acl/f01-operator":
                current["policy"] = body["policy"]
            else:
                pytest.fail("Unexpected administrative mutation")
            return httpx.Response(204)
        if path.endswith("lookup-self"):
            data = {"policies": ["root"]}
        elif path.endswith("role/f01-cli"):
            data = short
        elif path.endswith("role/f01-dev-day"):
            if current["role"] is None:
                return httpx.Response(404)
            data = current["role"]
        elif path.endswith("sys/auth/approle/tune"):
            data = {"max_lease_ttl": 2764800}
        else:
            assert path.endswith("sys/policies/acl/f01-operator")
            data = {"policy": current["policy"]}
        return httpx.Response(200, json={"data": data})

    with httpx.Client(
        base_url="https://openbao:8200", transport=httpx.MockTransport(handler)
    ) as http:
        setup.configure(http, ROOT_TOKEN)
        setup.configure(http, ROOT_TOKEN)
    assert mutations == ["/v1/auth/approle/role/f01-dev-day", "/v1/sys/policies/acl/f01-operator"]
    assert current["role"] == daily.ROLE_SETTINGS


def test_daily_sessions_reuse_file_without_revocation(modules, monkeypatch):
    daily, _, _, folder = modules
    path = write_day(daily, folder)
    events = []

    class Store:
        def __init__(self, *_):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            events.append("closed")

        def attach_day(self, token, expiry):
            assert token == TOKEN and expiry > time.time()
            events.append("attached")

        def revoke(self):
            pytest.fail("Closing a battery revoked the daily authorization")

    monkeypatch.setattr(daily, "OpenBaoSecretStore", Store)
    for _ in range(2):
        with daily.session():
            assert path.exists()
    assert events == ["attached", "closed", "attached", "closed"]
    assert path.exists()


def test_start_day_revokes_trial_and_operator_but_preserves_operational_token(modules, monkeypatch):
    from contextlib import nullcontext

    daily, _, _, folder = modules
    events = []
    tokens = iter(["trial", TOKEN])
    monkeypatch.setattr(daily, "client", lambda: nullcontext(object()))
    monkeypatch.setattr(daily, "require_unsealed", lambda _: None)

    def call(_http, method, path, token=None, payload=None):
        if path == "auth/userpass/login/diego":
            assert payload == {"password": "synthetic-password"}
            return {"auth": {"client_token": "operator"}}
        return {"data": {"policies": ["default", "f01-operator"]}}

    monkeypatch.setattr(daily, "call", call)
    monkeypatch.setattr(
        daily, "mint", lambda *_: {"token": next(tokens), "expires_at": time.time() + 86399}
    )
    monkeypatch.setattr(daily, "revoke_token", lambda _h, token: events.append(token))
    result = daily.start(password="synthetic-password", trial=True)
    assert events == ["trial", "operator"]
    assert result["state"] == "ACTIVE" and 86390 < result["remaining_seconds"] <= 86400
    assert TOKEN not in json.dumps(result)
    assert json.loads((folder / daily.NAME).read_text())["token"] == TOKEN


def test_server_internal_id_need_not_equal_presented_ssc_bearer():
    # OpenBao 2.7.2 lookup-self returns TokenEntry.ID, not its ExternalID bearer.
    data = metadata(id="internal-storage-token-id")
    with store_with(data) as store:
        store.attach_day(TOKEN, data["creation_time"] + 86400)
        assert store._token == TOKEN


def test_wait_active_retries_unsealed_standby_before_recovery(modules, monkeypatch):
    from types import SimpleNamespace

    _, setup, _, _ = modules
    clock = SimpleNamespace(value=0)
    responses = iter([429, 503, 200])
    waits = []
    monkeypatch.setattr(
        setup,
        "time",
        SimpleNamespace(monotonic=lambda: clock.value, sleep=lambda value: waits.append(value)),
    )

    class HTTP:
        def get(self, path, **kwargs):
            assert path == "/v1/sys/health"
            return httpx.Response(next(responses))

    setup.wait_active(HTTP())
    assert len(waits) == 2


def test_wait_active_has_bounded_deadline(modules, monkeypatch):
    from types import SimpleNamespace

    _, setup, _, _ = modules
    clock = SimpleNamespace(value=0)

    def sleep(value):
        clock.value += value

    monkeypatch.setattr(setup, "time", SimpleNamespace(monotonic=lambda: clock.value, sleep=sleep))

    class HTTP:
        def get(self, path, **kwargs):
            return httpx.Response(429)

    with pytest.raises(RuntimeError):
        setup.wait_active(HTTP())
    assert clock.value == 45


@pytest.mark.parametrize(
    "child_code,expected",
    [
        ("F01-DAY-RECOVER_ACTIVE", "RECOVER_ACTIVE"),
        (TOKEN, "BRIDGE_RECOVER"),
    ],
)
def test_host_preserves_only_allowlisted_closed_stage_codes(
    modules, monkeypatch, child_code, expected
):
    from types import SimpleNamespace

    _, _, host, _ = modules
    monkeypatch.setattr(
        host.subprocess,
        "run",
        lambda *_, **__: SimpleNamespace(
            returncode=1,
            stdout=json.dumps({"ok": False, "code": child_code, "detail": TOKEN}),
            stderr=TOKEN,
        ),
    )
    with pytest.raises(host.RecoveryError) as error:
        host.rpc("recover", key=KEY)
    assert error.value.code == expected
    assert TOKEN not in str(error.value) and KEY not in str(error.value)
