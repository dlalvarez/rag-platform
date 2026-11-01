"""F03-T002: application identity, exact reads, fixed policy and safe recovery."""

import copy
import importlib
import json
import ssl
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from rag_platform.providers.application_secrets import ApplicationSecretStore
from rag_platform.providers.secrets import SecretStoreError
from rag_platform.tenancy.contracts import SecretRef

ROOT = Path(__file__).resolve().parents[3]
CA = Path(ssl.get_default_verify_paths().cafile)
TOKEN = "synthetic-application-token-never-log"


def own(**changes):
    data = {
        "policies": ["f03-application"],
        "path": "auth/approle/login",
        "meta": {"role_name": "f03-application"},
        "creation_ttl": 3600,
        "explicit_max_ttl": 3600,
        "num_uses": 0,
        "ttl": 3599,
    }
    data.update(changes)
    return data


def make_store(*, changes=None, policies=None, ttl=3600, deny=False):
    calls = []
    revoked = [False]

    def handler(request):
        calls.append(request)
        path = request.url.path
        if path.endswith("/login"):
            return httpx.Response(
                200,
                json={
                    "auth": {
                        "client_token": TOKEN,
                        "lease_duration": ttl,
                        "policies": ["f03-application"] if policies is None else policies,
                    }
                },
            )
        assert request.headers["X-Vault-Token"] == TOKEN
        if path.endswith("/revoke-self"):
            revoked[0] = True
            return httpx.Response(204)
        if path.endswith("/lookup-self"):
            return (
                httpx.Response(403)
                if revoked[0]
                else httpx.Response(200, json={"data": own(**(changes or {}))})
            )
        assert request.method == "GET" and path.startswith("/v1/f01/data/")
        if deny:
            return httpx.Response(403, json={"errors": [TOKEN]})
        assert request.url.params["version"] == "7"
        return httpx.Response(
            200,
            json={
                "data": {
                    "metadata": {"version": 7, "destroyed": False, "deletion_time": ""},
                    "data": {"username": "synthetic", "password": TOKEN},
                }
            },
        )

    store = ApplicationSecretStore(
        "https://openbao:8200", CA, transport=httpx.MockTransport(handler)
    )
    return store, calls, revoked


def test_read_exact_version_and_no_infrastructure_interface():
    store, calls, revoked = make_store()
    with store:
        store.login("role", "one-use-secret")
        assert not hasattr(store, "write") and not hasattr(store, "attach_day")
        value = store.read(SecretRef(uuid4(), 7))
        assert value.username == "synthetic"
        assert TOKEN not in repr(store) + repr(value)
        store.revoke()
        assert revoked[0]
        before = len(calls)
        with pytest.raises(SecretStoreError):
            store.read(SecretRef(uuid4(), 7))
        assert len(calls) == before


@pytest.mark.parametrize(
    "policies",
    [
        ["root"],
        ["default", "f01-provisioner"],
        ["default", "f03-application"],
        ["f03-application", "extra"],
        [],
    ],
)
def test_wrong_policy_revoked_without_kv_read(policies, caplog):
    store, calls, revoked = make_store(policies=policies)
    with store, pytest.raises(SecretStoreError) as error:
        store.login("role", "id")
    assert revoked[0]
    assert not any("/f01/data/" in str(c.url) for c in calls)
    assert TOKEN not in str(error.value) + caplog.text


@pytest.mark.parametrize(
    "changes",
    [
        {"meta": {"role_name": "f01-dev-day"}},
        {"path": "auth/token/create"},
        {"explicit_max_ttl": 86400},
        {"creation_ttl": 900},
        {"num_uses": 1},
        {"ttl": 0},
        {"ttl": True},
        {"ttl": 3601},
        {"policies": ["root"]},
        {"meta": None},
    ],
)
def test_wrong_origin_or_limits_revoked(changes):
    store, calls, revoked = make_store(changes=changes)
    with store, pytest.raises(SecretStoreError):
        store.login("role", "id")
    assert revoked[0] and not any("/f01/data/" in str(c.url) for c in calls)


@pytest.mark.parametrize("ttl", [0, True, 3601])
def test_invalid_login_ttl_revoked(ttl):
    store, _, revoked = make_store(ttl=ttl)
    with store, pytest.raises(SecretStoreError):
        store.login("role", "id")
    assert revoked[0]


def test_server_denial_invalidates_warm_session_without_login_retry():
    store, calls, _ = make_store(deny=True)
    with store:
        store.login("role", "id")
        with pytest.raises(SecretStoreError):
            store.read(SecretRef(uuid4(), 7))
        before = len(calls)
        with pytest.raises(SecretStoreError):
            store.read(SecretRef(uuid4(), 7))
        assert len(calls) == before


def test_expiry_does_not_reuse_secret_id(monkeypatch):
    now = [100.0]
    monkeypatch.setattr("rag_platform.providers.application_secrets.time.monotonic", lambda: now[0])
    store, calls, _ = make_store()
    with store:
        store.login("role", "id")
        now[0] += 3600
        before = len(calls)
        with pytest.raises(SecretStoreError):
            store.read(SecretRef(uuid4(), 7))
        assert len(calls) == before


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    return importlib.import_module("f03_application_setup")


def scope():
    return {
        "version": 1,
        "fixtures": [
            {"name": name, "tenant": str(uuid4()), "refs": [str(uuid4()) for _ in range(3)]}
            for name in ("same-a", "same-b", "two-a", "two-b")
        ],
    }


def test_policy_has_only_twelve_exact_reads_and_self_lifecycle(setup):
    value = scope()
    paths = json.loads(setup.scope_policy(value))["path"]
    assert len(paths) == 14
    refs = {ref for f in value["fixtures"] for ref in f["refs"]}
    assert {p.removeprefix("f01/data/") for p in paths if p.startswith("f01/")} == refs
    for path, grants in paths.items():
        assert "*" not in path and ".." not in path
        assert grants == {"capabilities": ["update" if path.endswith("revoke-self") else "read"]}


@pytest.mark.parametrize(
    "kind",
    [
        "wildcard",
        "path",
        "duplicate_ref",
        "duplicate_tenant",
        "duplicate_name",
        "fifth",
        "bool_version",
        "extra",
    ],
)
def test_scope_rejects_widening_or_ambiguous_input(setup, kind):
    value = scope()
    if kind == "wildcard":
        value["fixtures"][0]["refs"][0] = "*"
    elif kind == "path":
        value["fixtures"][0]["refs"][0] = "../metadata/root"
    elif kind == "duplicate_ref":
        value["fixtures"][1]["refs"][0] = value["fixtures"][0]["refs"][0]
    elif kind == "duplicate_tenant":
        value["fixtures"][1]["tenant"] = value["fixtures"][0]["tenant"]
    elif kind == "duplicate_name":
        value["fixtures"][1]["name"] = value["fixtures"][0]["name"]
    elif kind == "fifth":
        value["fixtures"].append(copy.deepcopy(value["fixtures"][0]))
    elif kind == "bool_version":
        value["version"] = True
    else:
        value["extra"] = "ignored?"
    with pytest.raises((RuntimeError, ValueError)):
        setup.scope_policy(value)


def setup_http(setup, *, conflict=None):
    baseline = (ROOT / "ops/f01/provisioner.hcl").read_text().strip()
    data = {
        "sys/policies/acl/f01-provisioner": {"policy": baseline},
        "auth/approle/role/f01-cli": {"preserved": "short"},
        "auth/approle/role/f01-dev-day": {"preserved": "daily"},
        "sys/policies/acl/f01-operator": {"policy": "operator-unchanged"},
    }
    if conflict == "role":
        data["auth/approle/role/f03-application"] = {"token_policies": ["root"]}
    elif conflict == "policy":
        data["sys/policies/acl/f03-application"] = {"policy": '{"path":{"*":{}}}'}
    elif conflict == "provisioner":
        data["sys/policies/acl/f01-provisioner"]["policy"] += "\nforeign"
    mutations = []

    def handler(request):
        path = request.url.path.removeprefix("/v1/")
        if path == "auth/token/lookup-self":
            return httpx.Response(200, json={"data": {"policies": ["root"]}})
        if request.method in {"POST", "PUT"}:
            mutations.append(path)
            data[path] = json.loads(request.content)
            return httpx.Response(204)
        return (
            httpx.Response(404)
            if path not in data
            else httpx.Response(200, json={"data": data[path]})
        )

    return httpx.Client(
        base_url="https://openbao:8200", transport=httpx.MockTransport(handler)
    ), mutations


def test_bootstrap_idempotent_and_preserves_existing_roles(setup):
    http, mutations = setup_http(setup)
    with http:
        setup.configure(http, TOKEN)
        setup.configure(http, TOKEN)
    assert mutations == [
        "sys/policies/acl/f03-application",
        "auth/approle/role/f03-application",
        "sys/policies/acl/f01-provisioner",
    ]


@pytest.mark.parametrize("conflict", ["role", "policy", "provisioner"])
def test_bootstrap_conflict_prevents_all_writes(setup, conflict):
    http, mutations = setup_http(setup, conflict=conflict)
    with http, pytest.raises(RuntimeError):
        setup.configure(http, TOKEN)
    assert mutations == []


def test_host_failure_restores_config_and_preserves_daily_session(setup, monkeypatch, tmp_path):
    host = importlib.import_module("f03_application_host")
    original = b'listener "tcp" {\n  tls_min_version = "tls13"\n}\n'
    config, expected = tmp_path / "live", tmp_path / "expected"
    config.write_bytes(original)
    expected.write_bytes(original)
    daily = tmp_path / "day.json"
    daily.write_text("synthetic-session-retained")
    monkeypatch.setattr(host.base, "CONFIG", config)
    monkeypatch.setattr(host.base, "EXPECTED", expected)
    events = []
    monkeypatch.setattr(host.base, "restart", lambda: events.append("restart"))

    def rpc(action, **_):
        events.append(action)
        if action == "recover":
            assert b"disable_unauthed_generate_root_endpoints = false" in config.read_bytes()
            raise host.SetupError("SIMULATED")
        assert config.read_bytes() == original
        return {"ok": True}

    monkeypatch.setattr(host, "rpc", rpc)
    with pytest.raises(RuntimeError):
        host.maintenance("synthetic-unseal-share")
    assert events == ["restart", "recover", "restart", "restore"]
    assert daily.read_text() == "synthetic-session-retained"


def test_noninteractive_setup_refused_before_key_read(setup, monkeypatch):
    host = importlib.import_module("f03_application_host")
    monkeypatch.setattr(host.sys, "argv", ["f03_application_host.py", "configure"])
    monkeypatch.setattr(host.sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(host.getpass, "getpass", lambda *_: pytest.fail("secret read"))
    with pytest.raises(SystemExit, match="TTY_REQUIRED"):
        host.main()
