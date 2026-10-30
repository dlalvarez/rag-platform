"""CAS creation only when independently confirmed absent; never repair missing secrets."""

import secrets
from uuid import UUID

from rag_platform.providers.secrets import (
    Credential,
    SecretErrorCode,
    SecretStore,
    SecretStoreError,
)
from rag_platform.tenancy.contracts import SecretRef


def credential_for(store: SecretStore, ref: SecretRef, username: str, *, resource_exists: bool):
    try:
        value = store.read(ref)
    except SecretStoreError as error:
        if error.code != SecretErrorCode.NOT_FOUND or resource_exists or ref.version != 1:
            raise
        value = Credential(username, secrets.token_urlsafe(36))
        store.write(ref.id, value, expected_version=0)
        value = store.read(ref)
    if value.username != username:
        raise SecretStoreError(SecretErrorCode.INVALID)
    return value


def reference(row, kind: str):
    value = row[f"{kind}_secret_ref"]
    return SecretRef(UUID(str(value)), row[f"{kind}_secret_version"])
