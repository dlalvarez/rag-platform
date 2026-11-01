"""Trusted synthetic driver. Data services receive application-only identities."""

from contextlib import closing, contextmanager
from pathlib import Path
from uuid import uuid4

from f01_operator import CA, ENDPOINT
from f02_common import engine
from f02_identity_admin import settings

from rag_platform.control.identity import register
from rag_platform.documents.receipt import ReceiptService
from rag_platform.documents.repositories import RepositoryService
from rag_platform.documents.storage import ObjectGateway
from rag_platform.identity_api import private_file
from rag_platform.providers.application_secrets import ROLE, ApplicationSecretStore
from rag_platform.providers.identity import OIDCVerifier
from rag_platform.tenancy.authorization import AuthorizedConnections, TenantAuthorizer
from rag_platform.tenancy.registry import ConnectionRegistry
from rag_platform.tenancy.resolver import CatalogResolver


@contextmanager
def application(day):
    role = day._request("GET", f"/v1/auth/approle/role/{ROLE}/role-id")["data"]["role_id"]
    grant = day._request("POST", f"/v1/auth/approle/role/{ROLE}/secret-id", json={})["data"]
    if grant["secret_id_num_uses"] != 1 or grant["secret_id_ttl"] != 600:
        raise RuntimeError("APPLICATION_GRANT_LIMITS")
    with ApplicationSecretStore(ENDPOINT, CA) as store:
        try:
            store.login(role, grant["secret_id"])
            del grant, role
            yield store
        finally:
            store.revoke()


def real_actors(control, humans):
    result = {}
    with closing(OIDCVerifier(settings())) as verifier:
        for name in ("alice", "bob", "carol", "dave"):
            result[name] = register(
                control, verifier.verify(humans.tokens(name)["access_token"]), uuid4()
            )
    return result


class Services:
    def __init__(self, *, store=None, bearer=None, lease_seconds=60):
        if (store is None) == (bearer is None):
            raise ValueError("Exactly one application identity required")
        self.control, self.registry = None, None
        self.owned = bearer is not None
        self.store = store
        try:
            if self.owned:
                self.store = ApplicationSecretStore(ENDPOINT, CA)
                self.store.attach_application(bearer)
            self.control = engine()
            key = private_file("/run/secrets/api_authority_key", 32)
            self.authority = TenantAuthorizer(self.control, key, profile="documents")
            self.registry = ConnectionRegistry(
                CatalogResolver(self.control, profile="documents"), self.store, CA
            )
            self.connections = AuthorizedConnections(self.authority, self.registry)
            self.repositories = RepositoryService(self.connections, self.control, key)
            self.gateway = ObjectGateway(self.repositories, self.store, Path(CA))
            self.receipts = ReceiptService(
                self.repositories, self.gateway, lease_seconds=lease_seconds
            )
        except BaseException:
            self.close()
            raise

    def close(self):
        try:
            if self.registry is not None:
                self.registry.close()
        finally:
            if self.control is not None:
                self.control.dispose()
            if self.owned and self.store is not None:
                # Parent retains ownership/revocation for a deliberately killed worker.
                self.store.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
