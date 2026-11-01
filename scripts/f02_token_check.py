"""Real Keycloak token verification/rotation/expiry; no secret output."""

import json
import logging
import ssl
import time
from pathlib import Path
from uuid import uuid4

import httpx
import jwt

from rag_platform.providers.identity import IdentityError, OIDCSettings, OIDCVerifier

REALM = "rag-dev-token-fixture"
ISSUER = "https://idp:8443/realms/" + REALM
ADMIN = "https://idp:8443/admin/realms/" + REALM
PHASE = "START"


def request(http, method, url, expected=200, **kwargs):
    response = http.request(method, url, **kwargs)
    if response.status_code != expected:
        raise RuntimeError("HTTP")
    return response


def access(http, client, secret):
    return request(
        http,
        "POST",
        ISSUER + "/protocol/openid-connect/token",
        auth=httpx.BasicAuth(client, secret),
        data={"grant_type": "client_credentials"},
    ).json()["access_token"]


def rejected(verifier, token):
    try:
        verifier.verify(token)
    except IdentityError:
        return
    raise RuntimeError("WRONG_ACCEPT")


def run():
    global PHASE
    credentials = json.loads(Path("/run/secrets/token-fixture.json").read_text())
    tls = ssl.create_default_context(cafile="/tls/ca.crt")
    created = None
    cleanup_ok = False
    with httpx.Client(verify=tls, timeout=5, trust_env=False, follow_redirects=False) as http:
        PHASE = "READINESS"
        deadline = time.monotonic() + 180
        while True:
            try:
                response = http.get(ISSUER + "/.well-known/openid-configuration")
                if response.status_code == 200 and response.json()["issuer"] == ISSUER:
                    break
            except httpx.HTTPError:
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError("READINESS")
            time.sleep(2)
        settings = OIDCSettings(
            ISSUER,
            "rag-api",
            ISSUER + "/protocol/openid-connect/certs",
            Path("/tls/ca.crt"),
            refresh_seconds=1,
            leeway=0,
        )
        verifier = OIDCVerifier(settings)
        try:
            PHASE = "VALIDATE"
            original = access(http, "f02-probe", credentials["probe"])
            identity = verifier.verify(original)
            assert identity.subject and "roles" not in identity.__slots__
            pieces = original.split(".")
            pieces[2] = ("A" if pieces[2][0] != "A" else "B") + pieces[2][1:]
            rejected(verifier, ".".join(pieces))
            wrong = OIDCVerifier(
                OIDCSettings(ISSUER, "another-api", settings.jwks_url, settings.ca_file, leeway=0)
            )
            try:
                rejected(wrong, original)
            finally:
                wrong.close()
            PHASE = "ROTATE"
            controller = access(http, "f02-fixture-controller", credentials["controller"])
            auth = {"Authorization": "Bearer " + controller}
            realm_id = request(http, "GET", ADMIN, headers=auth).json()["id"]
            marker = "f02-t002-" + uuid4().hex
            response = request(
                http,
                "POST",
                ADMIN + "/components",
                expected=201,
                headers=auth,
                json={
                    "name": marker,
                    "parentId": realm_id,
                    "providerType": "org.keycloak.keys.KeyProvider",
                    "providerId": "rsa-generated",
                    "config": {
                        "priority": ["1000"],
                        "enabled": ["true"],
                        "active": ["true"],
                        "keySize": ["2048"],
                        "algorithm": ["RS256"],
                    },
                },
            )
            location = response.headers["Location"]
            prefix = ADMIN + "/components/"
            if not location.startswith(prefix) or "/" in location[len(prefix) :]:
                raise RuntimeError("LOCATION")
            created = location
            component = request(http, "GET", created, headers=auth).json()
            if component.get("name") != marker or component.get("parentId") != realm_id:
                raise RuntimeError("OWNERSHIP")
            new = access(http, "f02-probe", credentials["probe"])
            if jwt.get_unverified_header(new)["kid"] == jwt.get_unverified_header(original)["kid"]:
                raise RuntimeError("NO_ROTATION")
            time.sleep(1.1)
            assert verifier.verify(new).subject == identity.subject
            assert verifier.verify(original).subject == identity.subject
            PHASE = "EXPIRY"
            short = access(http, "f02-short", credentials["short"])
            short_identity = verifier.verify(short)
            delay = max(0, short_identity.expires_at - time.time() + 1)
            if delay > 8:
                raise RuntimeError("SHORT_TTL")
            time.sleep(delay)
            rejected(verifier, short)
            PHASE = "RESTORE"
            request(http, "DELETE", created, expected=204, headers=auth)
            created = None
            restored = access(http, "f02-probe", credentials["probe"])
            if (
                jwt.get_unverified_header(restored)["kid"]
                != jwt.get_unverified_header(original)["kid"]
            ):
                raise RuntimeError("RESTORE")
            cleanup_ok = True
        finally:
            verifier.close()
            if created is not None:
                request(http, "DELETE", created, expected=204, headers=auth)
    if not cleanup_ok:
        raise RuntimeError("CLEANUP")
    print("PASS T002: real Keycloak access token; signature/audience tampering rejected.")
    print("PASS T002: real signing-key rotation; old/new keys verified; original key restored.")
    print("PASS T002: actual short-lived token expired and rejected; no token values exposed.")
    print("T002: identity/memberships/API and full F02 acceptance still pending.")


if __name__ == "__main__":
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    try:
        run()
    except Exception:
        print("F02-T002 " + PHASE + ": stopped; no sensitive details.")
        raise SystemExit(1) from None
