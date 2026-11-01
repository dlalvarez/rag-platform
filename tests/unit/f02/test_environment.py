"""F02-T001 negative gates: refused host preparation and untrusted discovery."""

import importlib
import ssl
import urllib.error
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def modules(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    return importlib.import_module("f02_host"), importlib.import_module("f02_idp_check")


def test_existing_data_never_overwritten(modules, monkeypatch, tmp_path):
    host, _ = modules
    data = tmp_path / "data"
    data.mkdir()
    canary = data / "canary"
    canary.write_text("preserve")
    monkeypatch.setattr(host, "DATA", data)
    monkeypatch.setattr(host, "ENV", tmp_path / ".env")
    monkeypatch.setattr(host, "validate", lambda *args: None)
    with pytest.raises(ValueError, match="EXISTS"):
        host.prepare()
    assert canary.read_text() == "preserve"
    assert list(data.iterdir()) == [canary]


def test_symlink_environment_refused(modules, monkeypatch, tmp_path):
    host, _ = modules
    outside = tmp_path / "outside"
    outside.write_text("preserve")
    link = tmp_path / ".env"
    link.symlink_to(outside)
    monkeypatch.setattr(host, "ENV", link)
    monkeypatch.setattr(host, "DATA", tmp_path / "absent")
    monkeypatch.setattr(host, "validate", lambda *args: None)
    with pytest.raises(ValueError, match="EXISTS"):
        host.prepare()
    assert outside.read_text() == "preserve"


@pytest.mark.parametrize("fault", ["issuer", "jwks_uri", "private", "keytype", "empty", "too_many"])
def test_untrusted_discovery_cannot_pass(modules, monkeypatch, fault):
    _, probe = modules
    discovery = {
        "issuer": probe.ISSUER,
        "jwks_uri": probe.ISSUER + "/protocol/openid-connect/certs",
    }
    key = {"use": "sig", "alg": "RS256", "kty": "RSA", "kid": "synthetic"}
    keys = [key]
    if fault in {"issuer", "jwks_uri"}:
        discovery[fault] = "https://attacker.invalid"
    elif fault == "private":
        key["d"] = "synthetic-private-not-a-key"
    elif fault == "keytype":
        key["kty"] = "oct"
    elif fault == "empty":
        keys = []
    else:
        keys = [key] * 33
    calls = []

    def read(url, context):
        calls.append(url)
        return discovery if len(calls) == 1 else {"keys": keys}

    monkeypatch.setattr(probe.ssl, "create_default_context", lambda **kwargs: object())
    monkeypatch.setattr(probe, "read", read)
    with pytest.raises(ValueError):
        probe.check()
    assert all(url.startswith(probe.ISSUER) for url in calls)


def test_trusted_connection_does_not_hide_untrusted_ca_acceptance(modules, monkeypatch):
    _, probe = modules
    responses = iter(
        [
            {"issuer": probe.ISSUER, "jwks_uri": probe.ISSUER + "/protocol/openid-connect/certs"},
            {"keys": [{"use": "sig", "alg": "RS256", "kty": "RSA", "kid": "synthetic"}]},
            {},
        ]
    )
    monkeypatch.setattr(probe.ssl, "create_default_context", lambda **kwargs: object())
    monkeypatch.setattr(probe, "read", lambda *args: next(responses))
    with pytest.raises(ValueError, match="TLS_NEGATIVE"):
        probe.check()


def test_actual_tls_rejection_required_for_negative_pass(modules, monkeypatch, capsys):
    _, probe = modules
    calls = []

    def read(url, context):
        calls.append(url)
        if len(calls) == 1:
            return {
                "issuer": probe.ISSUER,
                "jwks_uri": probe.ISSUER + "/protocol/openid-connect/certs",
            }
        if len(calls) == 2:
            return {"keys": [{"use": "sig", "alg": "RS256", "kty": "RSA", "kid": "synthetic"}]}
        raise urllib.error.URLError(ssl.SSLCertVerificationError("synthetic"))

    monkeypatch.setattr(probe.ssl, "create_default_context", lambda **kwargs: object())
    monkeypatch.setattr(probe, "read", read)
    probe.check()
    assert "PASS T001" in capsys.readouterr().out


def test_discovery_redirect_rejected_before_follow(modules):
    _, probe = modules
    with pytest.raises(ValueError, match="REDIRECT"):
        probe.NoRedirect().redirect_request(
            None, None, 302, "redirect", {}, "https://attacker.invalid"
        )


def test_private_token_fixture_import_name_and_no_overwrite(modules, monkeypatch, tmp_path):
    import json
    import stat

    import yaml

    host, _ = modules
    data = tmp_path / "private"
    data.mkdir(mode=0o700)
    for name in ("config", "secrets"):
        (data / name).mkdir(mode=0o700)
    monkeypatch.setattr(host, "DATA", data)
    monkeypatch.setattr(host, "validate", lambda *args: None)
    host.prepare_tokens()
    metadata = data / "secrets/token-fixture.json"
    original = metadata.read_bytes()
    realm = json.loads((data / "config/token-fixture-realm.json").read_text())
    assert realm["realm"] != "master"
    assert stat.S_IMODE(metadata.stat().st_mode) == 0o600
    assert realm["users"][0]["clientRoles"] == {"realm-management": ["manage-realm"]}
    compose = yaml.safe_load((ROOT / "ops/f02/compose.yaml").read_text())
    targets = [mount["target"] for mount in compose["services"]["idp"]["volumes"]]
    assert "/opt/keycloak/data/import/" + realm["realm"] + "-realm.json" in targets
    with pytest.raises(ValueError, match="EXISTS"):
        host.prepare_tokens()
    assert metadata.read_bytes() == original
