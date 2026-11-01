"""Bounded OIDC resource-server verification; no token retained in identity/errors."""

import json
import ssl
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey


class IdentityError(RuntimeError):
    def __init__(self, unavailable=False):
        self.code = "IDENTITY_UNAVAILABLE" if unavailable else "INVALID_TOKEN"
        super().__init__(self.code)


@dataclass(frozen=True, slots=True)
class Identity:
    issuer: str = field(repr=False)
    subject: str = field(repr=False)
    expires_at: int


@dataclass(frozen=True, slots=True)
class OIDCSettings:
    issuer: str
    audience: str
    jwks_url: str
    ca_file: Path
    profile: str = "keycloak"
    cache_seconds: int = 300
    refresh_seconds: int = 30
    leeway: int = 30

    def __post_init__(self):
        issuer, keys = urlsplit(self.issuer), urlsplit(self.jwks_url)
        if (
            issuer.scheme != "https"
            or keys.scheme != "https"
            or not issuer.hostname
            or issuer.netloc != keys.netloc
            or issuer.username
            or issuer.password
            or issuer.query
            or issuer.fragment
            or keys.username
            or keys.password
            or keys.query
            or keys.fragment
            or self.issuer.endswith("/")
            or not self.audience
            or len(self.audience) > 255
            or self.profile not in {"keycloak", "rfc9068"}
            or not 1 <= self.cache_seconds <= 300
            or not 1 <= self.refresh_seconds <= self.cache_seconds
            or not 0 <= self.leeway <= 30
        ):
            raise ValueError("OIDC_CONFIG")


class OIDCVerifier:
    def __init__(self, settings: OIDCSettings, *, transport=None):
        self.settings = settings
        self.http = httpx.Client(
            verify=ssl.create_default_context(cafile=str(settings.ca_file)),
            transport=transport,
            timeout=5,
            trust_env=False,
            follow_redirects=False,
            headers={"Accept-Encoding": "identity"},
        )
        self._keys = {}
        self._deadline = 0.0
        self._last_refresh = float("-inf")
        self._lock = threading.RLock()
        self._closed = False

    def close(self):
        with self._lock:
            self._closed = True
            self.http.close()
            self._keys.clear()

    def _json(self, url):
        try:
            with self.http.stream("GET", url) as response:
                if (
                    response.status_code != 200
                    or response.headers.get("content-encoding", "identity") != "identity"
                ):
                    raise IdentityError(True)
                payload = bytearray()
                for chunk in response.iter_bytes():
                    payload.extend(chunk)
                    if len(payload) > 65536:
                        raise IdentityError(True)
                result = json.loads(payload)
                if not isinstance(result, dict):
                    raise IdentityError(True)
                return result
        except IdentityError:
            raise
        except Exception:
            raise IdentityError(True) from None

    def _refresh(self, now):
        # Rate limit attempts, including failed fetches and unknown-kid bursts.
        self._last_refresh = now
        discovery = self._json(self.settings.issuer + "/.well-known/openid-configuration")
        if (
            discovery.get("issuer") != self.settings.issuer
            or discovery.get("jwks_uri") != self.settings.jwks_url
        ):
            raise IdentityError(True)
        entries = self._json(self.settings.jwks_url).get("keys")
        if not isinstance(entries, list) or not 1 <= len(entries) <= 32:
            raise IdentityError(True)
        keys = {}
        try:
            for entry in entries:
                if not isinstance(entry, dict) or any(
                    field in entry for field in ("d", "p", "q", "dp", "dq", "qi", "oth", "k")
                ):
                    raise IdentityError(True)
                if entry.get("use", "sig") != "sig":
                    continue
                if entry.get("alg", "RS256") != "RS256" or entry.get("kty") != "RSA":
                    continue
                kid = entry.get("kid")
                if (
                    not isinstance(kid, str)
                    or not 1 <= len(kid) <= 128
                    or kid in keys
                    or ("key_ops" in entry and entry["key_ops"] != ["verify"])
                ):
                    raise IdentityError(True)
                key = jwt.PyJWK.from_dict(entry, algorithm="RS256").key
                if not isinstance(key, RSAPublicKey) or key.key_size < 2048:
                    raise IdentityError(True)
                keys[kid] = key
            if not keys:
                raise IdentityError(True)
        except IdentityError:
            raise
        except Exception:
            raise IdentityError(True) from None
        self._keys = keys
        self._deadline = now + self.settings.cache_seconds

    def verify(self, token: str) -> Identity:
        try:
            if not isinstance(token, str) or not 1 <= len(token) <= 16384:
                raise IdentityError()
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            expected_type = "JWT" if self.settings.profile == "keycloak" else "at+jwt"
            if (
                header.get("alg") != "RS256"
                or header.get("typ") != expected_type
                or not isinstance(kid, str)
                or not 1 <= len(kid) <= 128
                or any(field in header for field in ("jku", "x5u", "crit"))
            ):
                raise IdentityError()
            with self._lock:
                if self._closed:
                    raise IdentityError(True)
                now = time.monotonic()
                expired = now >= self._deadline
                if expired or kid not in self._keys:
                    if now - self._last_refresh < self.settings.refresh_seconds:
                        raise IdentityError(expired)
                    self._refresh(now)
                key = self._keys.get(kid)
                if key is None:
                    raise IdentityError()
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=self.settings.issuer,
                audience=self.settings.audience,
                leeway=self.settings.leeway,
                options={"require": ["iss", "sub", "aud", "exp", "iat"]},
            )
            if (
                not isinstance(claims["sub"], str)
                or not 1 <= len(claims["sub"]) <= 255
                or any(type(claims[x]) is not int for x in ("exp", "iat"))
                or ("nbf" in claims and type(claims["nbf"]) is not int)
                or claims["exp"] <= claims["iat"]
                or (self.settings.profile == "keycloak" and claims.get("typ") != "Bearer")
            ):
                raise IdentityError()
            return Identity(self.settings.issuer, claims["sub"], claims["exp"])
        except IdentityError:
            raise
        except Exception:
            raise IdentityError() from None
