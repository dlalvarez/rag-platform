"""Signed-token negatives, key rotation and bounded network behavior for F02-T002."""

import dataclasses
import json
import ssl
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from rag_platform.providers.identity import IdentityError, OIDCSettings, OIDCVerifier

ISSUER = "https://idp.invalid/realms/synthetic"
KEYS = ISSUER + "/protocol/openid-connect/certs"


@pytest.fixture(scope="module")
def signing():
    return [rsa.generate_private_key(public_exponent=65537, key_size=2048) for _ in range(2)]


def jwk(key, kid):
    result = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    return {**result, "kid": kid, "use": "sig", "alg": "RS256"}


def token(key, kid="old", **changes):
    now = int(time.time())
    payload = dict(
        iss=ISSUER, sub="synthetic-subject", aud="rag-api", exp=now + 300, iat=now, typ="Bearer"
    )
    payload.update(changes)
    return jwt.encode(payload, key, algorithm="RS256", headers={"kid": kid})


@pytest.fixture
def setup(signing):
    state = {"keys": [jwk(signing[0], "old")], "calls": [], "fail": False}

    def transport(request):
        state["calls"].append(str(request.url))
        if state["fail"]:
            raise httpx.ConnectError("synthetic failure", request=request)
        if str(request.url).endswith("openid-configuration"):
            return httpx.Response(200, json={"issuer": ISSUER, "jwks_uri": KEYS})
        return httpx.Response(200, json={"keys": state["keys"]})

    settings = OIDCSettings(ISSUER, "rag-api", KEYS, Path(ssl.get_default_verify_paths().cafile))
    verifier = OIDCVerifier(settings, transport=httpx.MockTransport(transport))
    yield verifier, state
    verifier.close()


def test_valid_identity_is_immutable_and_no_token_retained(setup, signing):
    v, _ = setup
    bearer = token(signing[0])
    result = v.verify(bearer)
    assert result.subject == "synthetic-subject"
    assert result.issuer == ISSUER
    assert bearer not in repr(result)
    assert result.subject not in repr(result)
    assert result.issuer not in repr(result)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.subject = "other"


@pytest.mark.parametrize(
    "changes",
    [
        {"iss": "https://attacker.invalid"},
        {"aud": "other-api"},
        {"exp": 1},
        {"iat": 2**40},
        {"nbf": 2**40},
        {"sub": ""},
        {"sub": 123},
        {"typ": "ID"},
        {"exp": True},
        {"iat": True},
        {"nbf": False},
    ],
)
def test_signed_but_invalid_claims_rejected(setup, signing, changes):
    v, _ = setup
    bearer = token(signing[0], **changes)
    with pytest.raises(IdentityError) as error:
        v.verify(bearer)
    assert str(error.value) == "INVALID_TOKEN"
    assert bearer not in str(error.value)


def test_signature_and_header_substitution_rejected(setup, signing):
    v, state = setup
    with pytest.raises(IdentityError):
        v.verify(token(signing[1]))
    before = len(state["calls"])
    for bearer in (
        jwt.encode({"sub": "synthetic"}, "", algorithm="none", headers={"kid": "old"}),
        jwt.encode(
            {"sub": "synthetic"},
            "synthetic-hmac-key-only-for-test-32-bytes",
            algorithm="HS256",
            headers={"kid": "old"},
        ),
        jwt.encode(
            {"sub": "synthetic"},
            signing[0],
            algorithm="RS256",
            headers={"kid": "old", "jku": "https://attacker.invalid/keys"},
        ),
        "not-a-token",
    ):
        with pytest.raises(IdentityError):
            v.verify(bearer)
    assert len(state["calls"]) == before


def test_unknown_kid_refresh_bounded_and_rotation_accepted(setup, signing, monkeypatch):
    v, state = setup
    now = [100.0]
    monkeypatch.setattr("rag_platform.providers.identity.time.monotonic", lambda: now[0])
    v.verify(token(signing[0]))
    state["keys"].append(jwk(signing[1], "new"))
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: rejected(v, token(signing[1], "new")), range(20)))
    assert all(results)
    assert len(state["calls"]) == 2
    now[0] += 31
    assert v.verify(token(signing[1], "new")).subject == "synthetic-subject"
    assert len(state["calls"]) == 4
    assert v.verify(token(signing[0])).subject == "synthetic-subject"


def rejected(verifier, bearer):
    try:
        verifier.verify(bearer)
    except IdentityError:
        return True
    return False


def test_outage_after_cache_expiry_does_not_use_stale_key(setup, signing, monkeypatch):
    v, state = setup
    now = [100.0]
    monkeypatch.setattr("rag_platform.providers.identity.time.monotonic", lambda: now[0])
    v.verify(token(signing[0]))
    state["fail"] = True
    now[0] += 301
    with pytest.raises(IdentityError) as error:
        v.verify(token(signing[0]))
    assert error.value.code == "IDENTITY_UNAVAILABLE"
    calls = len(state["calls"])
    with pytest.raises(IdentityError):
        v.verify(token(signing[0]))
    assert len(state["calls"]) == calls


@pytest.mark.parametrize("fault", ["duplicate", "private", "too_many", "weak", "foreign_discovery"])
def test_untrusted_keys_and_discovery_rejected(setup, signing, fault, monkeypatch):
    v, state = setup
    if fault == "duplicate":
        state["keys"] *= 2
    elif fault == "private":
        state["keys"][0]["d"] = "synthetic-private"
    elif fault == "too_many":
        state["keys"] *= 33
    elif fault == "weak":
        weak = rsa.generate_private_key(public_exponent=65537, key_size=1024)
        state["keys"] = [jwk(weak, "old")]
    else:
        original = v._json
        monkeypatch.setattr(
            v,
            "_json",
            lambda url: (
                {"issuer": ISSUER, "jwks_uri": "https://attacker.invalid"}
                if url.endswith("openid-configuration")
                else original(url)
            ),
        )
    with pytest.raises(IdentityError):
        v.verify(token(signing[0]))
    assert all(url.startswith(ISSUER) for url in state["calls"])


@pytest.mark.parametrize("fault", ["redirect", "oversize", "compressed"])
def test_bounded_http_responses(signing, fault):
    def transport(request):
        if fault == "redirect":
            return httpx.Response(302, headers={"location": "https://attacker.invalid"})
        if fault == "oversize":
            return httpx.Response(200, content=b"x" * 65537)
        return httpx.Response(200, content=b"", headers={"content-encoding": "br"})

    v = OIDCVerifier(
        OIDCSettings(ISSUER, "rag-api", KEYS, Path(ssl.get_default_verify_paths().cafile)),
        transport=httpx.MockTransport(transport),
    )
    try:
        with pytest.raises(IdentityError):
            v.verify(token(signing[0]))
    finally:
        v.close()


def test_closed_verifier_cannot_authenticate(setup, signing):
    v, _ = setup
    bearer = token(signing[0])
    v.verify(bearer)
    v.close()
    with pytest.raises(IdentityError):
        v.verify(bearer)


def test_claims_cannot_grant_product_authority(setup, signing):
    v, _ = setup
    result = v.verify(token(signing[0], roles=["platform_operator"], tenant_id="foreign"))
    assert not hasattr(result, "roles")
    assert not hasattr(result, "tenant_id")


def test_oversized_token_rejected_before_network(setup):
    v, state = setup
    with pytest.raises(IdentityError):
        v.verify("x" * 16385)
    assert not state["calls"]


def test_invalid_token_logs_never_expose_identity_or_bearer(setup, signing, caplog, capsys):
    v, _ = setup
    subject = "synthetic-private-subject"
    bearer = token(signing[0], sub=subject, aud="wrong-api")
    with caplog.at_level("DEBUG"), pytest.raises(IdentityError):
        v.verify(bearer)
    captured = caplog.text + capsys.readouterr().out
    assert bearer not in captured
    assert subject not in captured
