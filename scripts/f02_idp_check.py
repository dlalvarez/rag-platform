"""Actual TLS/discovery/JWKS probes. No token, password or admin access."""

import json
import ssl
import time
import urllib.error
import urllib.request

ISSUER = "https://idp:8443/realms/rag-dev"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("REDIRECT")


def read(url, context):
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=context), NoRedirect()
    )
    with opener.open(url, timeout=5) as result:
        if result.status != 200:
            raise ValueError("STATUS")
        payload = result.read(65537)
        if len(payload) > 65536:
            raise ValueError("SIZE")
        return json.loads(payload)


def check():
    context = ssl.create_default_context(cafile="/tls/ca.crt")
    deadline = time.monotonic() + 180
    while True:
        try:
            discovery = read(ISSUER + "/.well-known/openid-configuration", context)
            break
        except (OSError, ValueError):
            if time.monotonic() >= deadline:
                raise ValueError("READINESS") from None
            time.sleep(2)
    expected_jwks = ISSUER + "/protocol/openid-connect/certs"
    if discovery.get("issuer") != ISSUER or discovery.get("jwks_uri") != expected_jwks:
        raise ValueError("DISCOVERY")
    keys = read(expected_jwks, context).get("keys")
    if not isinstance(keys, list) or not keys or len(keys) > 32:
        raise ValueError("JWKS")
    signing = [k for k in keys if k.get("use") == "sig" and k.get("alg") == "RS256"]
    if not signing or any(k.get("kty") != "RSA" or not k.get("kid") for k in signing):
        raise ValueError("KEY")
    if any(k.get("d") or k.get("p") or k.get("q") for k in keys):
        raise ValueError("PRIVATE_KEY")
    try:
        read(expected_jwks, ssl.create_default_context())
    except urllib.error.URLError as error:
        if not isinstance(error.reason, ssl.SSLCertVerificationError):
            raise ValueError("TLS_NEGATIVE") from None
    else:
        raise ValueError("TLS_NEGATIVE")
    print("PASS T001: real IdP TLS/discovery/JWKS; exact issuer and signing keys.")
    print("PASS T001: untrusted CA rejected; no password/token/users in this probe.")
    print("T001 only: API identity/memberships/authorization and F02 acceptance pending.")


if __name__ == "__main__":
    try:
        check()
    except Exception:
        print("F02-T001 IDP: probe stopped; no sensitive details.")
        raise SystemExit(1) from None
