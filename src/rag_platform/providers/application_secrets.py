"""Read-only application AppRole; fixed-profile bearer handoff, no infrastructure tokens."""

import time

from rag_platform.providers.secrets import (
    OpenBaoSecretStore,
    SecretErrorCode,
    SecretStoreError,
)

ROLE = "f03-application"
POLICY = "f03-application"


class ApplicationSecretStore:
    """Exact-version reads only. Expiry/revocation fails closed, with no fallback."""

    def __init__(self, endpoint, ca_file, *, transport=None):
        self._store = OpenBaoSecretStore(endpoint, ca_file, transport=transport)

    def __repr__(self):
        return "ApplicationSecretStore(<redacted>)"

    def _empty(self):
        if self._store._token is not None:
            # Explicit revoke before replacement; do not orphan an older session.
            raise SecretStoreError(SecretErrorCode.INVALID)

    def _verify(self, maximum):
        store = self._store
        try:
            own = store._request("GET", "/v1/auth/token/lookup-self")["data"]
            if (
                set(own["policies"]) != {POLICY}
                or own["path"] != "auth/approle/login"
                or own["meta"]["role_name"] != ROLE
                or own["explicit_max_ttl"] != 3600
                or own["creation_ttl"] != 3600
                or type(own["num_uses"]) is not int
                or own["num_uses"] != 0
                or type(own["ttl"]) is not int
                or not 0 < own["ttl"] <= maximum
                or own.get("identity_policies", []) != []
            ):
                raise SecretStoreError(SecretErrorCode.DENIED)
            store._expires_at = time.monotonic() + max(0, own["ttl"] - 1)
        except (KeyError, TypeError, ValueError):
            raise SecretStoreError(SecretErrorCode.DENIED) from None

    def login(self, role_id, secret_id):
        self._empty()
        store = self._store
        if not all(isinstance(v, str) and 0 < len(v) <= 4096 for v in (role_id, secret_id)):
            raise SecretStoreError(SecretErrorCode.INVALID)
        try:
            result = store._request(
                "POST",
                "/v1/auth/approle/login",
                authenticated=False,
                json={"role_id": role_id, "secret_id": secret_id},
            )
            auth = result["auth"]
            token = auth["client_token"]
            if not isinstance(token, str) or not token or len(token) > 4096:
                raise SecretStoreError(SecretErrorCode.DENIED)
            # A freshly minted token belongs to this login and is revoked on bad profile.
            store._token, store._expires_at = token, time.monotonic() + 5
            ttl = auth["lease_duration"]
            if (
                set(auth["policies"]) != {POLICY}
                or auth.get("identity_policies", []) != []
                or type(ttl) is not int
                or not 0 < ttl <= 3600
            ):
                raise SecretStoreError(SecretErrorCode.DENIED)
            self._verify(ttl)
        except BaseException as error:
            try:
                store.revoke()
            finally:
                store._token, store._expires_at = None, 0.0
            if isinstance(error, (KeyError, TypeError, ValueError)):
                raise SecretStoreError(SecretErrorCode.DENIED) from None
            raise

    def attach_application(self, token):
        """Private application-only handoff; root/day/extra policies are rejected.

        A rejected supplied bearer is never revoked: it might be an operator's token.
        This method neither attaches nor renews the infrastructure daily session.
        """
        self._empty()
        store = self._store
        if (
            not isinstance(token, str)
            or not 0 < len(token) <= 4096
            or any(not 33 <= ord(char) <= 126 for char in token)
        ):
            raise SecretStoreError(SecretErrorCode.INVALID)
        store._token, store._expires_at = token, time.monotonic() + 5
        try:
            self._verify(3600)
        except BaseException:
            store._token, store._expires_at = None, 0.0
            raise

    def read(self, ref):
        return self._store.read(ref)

    def revoke(self):
        self._store.revoke()

    def close(self):
        self._store.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
