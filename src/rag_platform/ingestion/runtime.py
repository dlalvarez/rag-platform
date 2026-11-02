"""Limited F04 worker runtime: no daily/admin/migrator credentials or implicit migrations."""

import json
from functools import partial
from pathlib import Path
from uuid import UUID

from rag_platform.documents.content import DocumentService
from rag_platform.documents.repositories import RepositoryService
from rag_platform.documents.storage import ObjectGateway
from rag_platform.providers.application_handoff import FileApplicationStore
from rag_platform.tenancy.authorization import AuthorizedConnections, TenantAuthorizer
from rag_platform.tenancy.registry import ConnectionRegistry, tenant_engine
from rag_platform.tenancy.resolver import AdministrativeTenant, CatalogResolver


def scope(path):
    try:
        value = json.loads(Path(path).read_text())
        if set(value) != {"version", "fixtures"} or type(value["version"]) is not int:
            raise ValueError()
        if value["version"] != 1 or not isinstance(value["fixtures"], list):
            raise ValueError()
        fixtures = value["fixtures"]
        if len(fixtures) != 4 or {r["name"] for r in fixtures} != {
            "same-a",
            "same-b",
            "two-a",
            "two-b",
        }:
            raise ValueError()
        tenants, refs = [], []
        for row in fixtures:
            if set(row) != {"name", "tenant", "refs"} or len(row["refs"]) != 3:
                raise ValueError()
            tenants.append(UUID(row["tenant"]))
            refs.extend(UUID(item) for item in row["refs"])
        if (
            len(set(tenants)) != 4
            or len(set(refs)) != 12
            or any(item.int == 0 for item in tenants + refs)
        ):
            raise ValueError()
        return tuple(tenants)
    except Exception:
        raise ValueError("Invalid fixed development scope") from None


class Runtime:
    def __init__(self, engine, key, path, endpoint, ca, scope_path, *, profile="ingestion"):
        if profile not in ("ingestion", "embeddings"):
            raise ValueError("Known ingestion profile required")
        self.store, self.registry = None, None
        try:
            self.scope = scope(scope_path)
            self.store = FileApplicationStore(path, endpoint, ca)
            self.authority = TenantAuthorizer(engine, key, profile=profile)
            self.registry = ConnectionRegistry(
                CatalogResolver(engine, profile=profile),
                self.store,
                ca,
                engine_factory=partial(tenant_engine, pool_size=1),
            )
            connections = AuthorizedConnections(self.authority, self.registry)
            self.repositories = RepositoryService(connections, engine, key, profile=profile)
            self.gateway = ObjectGateway(self.repositories, self.store, ca)
            self.documents = DocumentService(self.repositories, self.gateway)
        except BaseException:
            self.close()
            raise

    def preflight(self):
        for tenant in self.scope:
            self.registry.resolver.resolve(AdministrativeTenant(tenant), "app")

    def close(self):
        try:
            if self.registry is not None:
                self.registry.close()
        finally:
            if self.store is not None:
                self.store.close()
