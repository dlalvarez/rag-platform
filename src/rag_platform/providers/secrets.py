"""OpenBao KV v2 adapter: exact versions, mandatory CAS, no fallback or secret logging."""

import ssl
import time
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit
from uuid import UUID

import httpx

from rag_platform.tenancy.contracts import SecretRef


class SecretErrorCode(StrEnum):
    UNAVAILABLE = "SECRET_UNAVAILABLE"
    DENIED = "SECRET_DENIED"
    CONFLICT = "SECRET_CONFLICT"
    NOT_FOUND = "SECRET_NOT_FOUND"
    INVALID = "SECRET_INVALID"


class SecretStoreError(RuntimeError):
    def __init__(self, code: SecretErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True, repr=False)
class Credential:
    username: str = field(repr=False)
    password: str = field(repr=False)

    def __post_init__(self) -> None:
        if not all(
            isinstance(v, str) and 0 < len(v) <= 4096 for v in (self.username, self.password)
        ):
            raise SecretStoreError(SecretErrorCode.INVALID)

    def __repr__(self) -> str:
        return "Credential(<redacted>)"


class SecretStore(Protocol):
    def read(self, ref: SecretRef) -> Credential: ...
    def write(self, ref_id: UUID, value: Credential, *, expected_version: int) -> SecretRef: ...


class OpenBaoSecretStore:
    """One AppRole session, no refresh with a consumed SecretID. Caller must close."""

    def __init__(
        self, endpoint: str, ca_file: Path, *, transport: httpx.BaseTransport | None = None
    ) -> None:
        url = urlsplit(endpoint)
        if (
            url.scheme != "https"
            or not url.hostname
            or url.username
            or url.password
            or url.path not in ("", "/")
            or url.query
            or url.fragment
        ):
            raise SecretStoreError(SecretErrorCode.INVALID)
        context = ssl.create_default_context(cafile=str(ca_file))
        self._client = httpx.Client(
            base_url=endpoint,
            verify=context,
            timeout=5.0,
            trust_env=False,
            follow_redirects=False,
            transport=transport,
        )
        self._token: str | None = None
        self._expires_at = 0.0

    def __repr__(self) -> str:
        return "OpenBaoSecretStore(<redacted>)"

    def _request(
        self, method: str, path: str, *, authenticated: bool = True, **kwargs: object
    ) -> dict:
        if authenticated and (not self._token or time.monotonic() >= self._expires_at):
            self._token = None
            raise SecretStoreError(SecretErrorCode.DENIED)
        headers = {"X-Vault-Token": self._token} if authenticated else {}
        try:
            response = self._client.request(method, path, headers=headers, **kwargs)
        except httpx.HTTPError:
            raise SecretStoreError(SecretErrorCode.UNAVAILABLE) from None
        if response.status_code in (401, 403):
            self._token = None
            raise SecretStoreError(SecretErrorCode.DENIED)
        if response.status_code == 404:
            raise SecretStoreError(SecretErrorCode.NOT_FOUND)
        if response.status_code == 400 and method == "POST" and path.startswith("/v1/f01/data/"):
            # CAS write refused. Never echo the server's potentially sensitive error body.
            raise SecretStoreError(SecretErrorCode.CONFLICT)
        if response.status_code >= 500 or 300 <= response.status_code < 400:
            raise SecretStoreError(SecretErrorCode.UNAVAILABLE)
        if response.status_code not in (200, 204):
            raise SecretStoreError(SecretErrorCode.INVALID)
        try:
            return response.json() if response.content else {}
        except ValueError:
            raise SecretStoreError(SecretErrorCode.INVALID) from None

    def login(self, role_id: str, secret_id: str) -> None:
        self._token = None
        self._expires_at = 0.0
        result = self._request(
            "POST",
            "/v1/auth/approle/login",
            authenticated=False,
            json={"role_id": role_id, "secret_id": secret_id},
        )
        try:
            auth = result["auth"]
            policies = set(auth["policies"])
            token = auth["client_token"]
            ttl = auth["lease_duration"]
            if (
                policies != {"default", "f01-provisioner"}
                or not isinstance(token, str)
                or not token
                or type(ttl) is not int
                or not 0 < ttl <= 3600
            ):
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise SecretStoreError(SecretErrorCode.DENIED) from None
        self._token = token
        self._expires_at = time.monotonic() + max(0, ttl - 1)

    def attach_day(self, token: str, expires_at: float) -> None:
        """Validate the dedicated server-issued daily token; never renew it."""
        self._token = None
        self._expires_at = 0.0
        if (
            not isinstance(token, str)
            or not 0 < len(token) <= 4096
            or type(expires_at) not in (int, float)
            or not time.time() < expires_at <= time.time() + 86400
        ):
            raise SecretStoreError(SecretErrorCode.DENIED)
        self._token = token
        self._expires_at = time.monotonic() + 5
        try:
            own = self._request("GET", "/v1/auth/token/lookup-self")["data"]
            ttl = own["ttl"]
            if (
                set(own["policies"]) != {"default", "f01-provisioner"}
                or own["path"] != "auth/approle/login"
                or own["meta"]["role_name"] != "f01-dev-day"
                or own["creation_ttl"] != 86400
                or own["explicit_max_ttl"] != 86400
                or own["num_uses"] != 0
                or type(ttl) is not int
                or not 0 < ttl <= 86400
                or own["creation_time"] + 86400 != expires_at
            ):
                raise SecretStoreError(SecretErrorCode.DENIED)
            self._expires_at = time.monotonic() + max(0, min(ttl, expires_at - time.time()) - 1)
        except (KeyError, TypeError, ValueError):
            self._token = None
            self._expires_at = 0.0
            raise SecretStoreError(SecretErrorCode.DENIED) from None
        except BaseException:
            self._token = None
            self._expires_at = 0.0
            raise

    def read(self, ref: SecretRef) -> Credential:
        if not isinstance(ref, SecretRef):
            raise SecretStoreError(SecretErrorCode.INVALID)
        result = self._request("GET", f"/v1/f01/data/{ref.id}", params={"version": ref.version})
        try:
            body = result["data"]
            metadata, values = body["metadata"], body["data"]
            if (
                metadata["version"] != ref.version
                or metadata.get("destroyed")
                or metadata.get("deletion_time")
                or set(values) != {"username", "password"}
            ):
                raise ValueError
            return Credential(values["username"], values["password"])
        except (KeyError, TypeError, ValueError):
            raise SecretStoreError(SecretErrorCode.INVALID) from None

    def write(self, ref_id: UUID, value: Credential, *, expected_version: int) -> SecretRef:
        if (
            not isinstance(ref_id, UUID)
            or not isinstance(value, Credential)
            or type(expected_version) is not int
            or expected_version < 0
        ):
            raise SecretStoreError(SecretErrorCode.INVALID)
        result = self._request(
            "POST",
            f"/v1/f01/data/{ref_id}",
            json={
                "options": {"cas": expected_version},
                "data": {"username": value.username, "password": value.password},
            },
        )
        try:
            version = result["data"]["version"]
            if type(version) is not int or version != expected_version + 1:
                raise ValueError
            return SecretRef(ref_id, version)
        except (KeyError, TypeError, ValueError):
            raise SecretStoreError(SecretErrorCode.INVALID) from None

    def revoke(self) -> None:
        """Revoke this bearer and verify rejection; always clear local session state."""
        token = self._token
        if token is None:
            return
        try:
            headers = {"X-Vault-Token": token}
            response = self._client.post("/v1/auth/token/revoke-self", headers=headers, json={})
            if response.status_code not in (204, 403):
                raise SecretStoreError(SecretErrorCode.UNAVAILABLE)
            rejected = self._client.get("/v1/auth/token/lookup-self", headers=headers)
            if rejected.status_code != 403:
                raise SecretStoreError(SecretErrorCode.DENIED)
        except httpx.HTTPError:
            raise SecretStoreError(SecretErrorCode.UNAVAILABLE) from None
        finally:
            self._token = None
            self._expires_at = 0.0

    def close(self) -> None:
        self._token = None
        self._expires_at = 0.0
        self._client.close()

    def __enter__(self) -> "OpenBaoSecretStore":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
