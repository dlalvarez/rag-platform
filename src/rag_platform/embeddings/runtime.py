"""SQL-only embedding runtime; no S3 gateway, migrator or daily credentials."""

from functools import partial

import sqlalchemy as sa

from rag_platform.documents.repositories import RepositoryService
from rag_platform.embeddings import processing
from rag_platform.embeddings.access import ExpiringStore
from rag_platform.embeddings.qwen import qwen_profile
from rag_platform.ingestion.runtime import scope
from rag_platform.tenancy.authorization import AuthorizedConnections, TenantAuthorizer
from rag_platform.tenancy.registry import ConnectionRegistry, tenant_engine
from rag_platform.tenancy.resolver import AdministrativeTenant, CatalogResolver


class Runtime:
    def __init__(self, engine, key, path, endpoint, ca, scope_path):
        self.store, self.registry = None, None
        try:
            self.scope = scope(scope_path)
            self.store = ExpiringStore(path, endpoint, ca)
            self.authority = TenantAuthorizer(engine, key, profile="embedding_publication")
            self.registry = ConnectionRegistry(
                CatalogResolver(engine, profile="embedding_publication"),
                self.store,
                ca,
                engine_factory=partial(tenant_engine, pool_size=1),
            )
            self.repositories = RepositoryService(
                AuthorizedConnections(self.authority, self.registry),
                engine,
                key,
                profile="embedding_publication",
            )
        except BaseException:
            self.close()
            raise

    def access_ready(self):
        return self.store is not None and self.store.ready()

    def preflight(self):
        if not self.access_ready():
            raise processing.ProcessingError("DEPENDENCY_UNAVAILABLE")
        profile = qwen_profile()
        for tenant in self.scope:
            with self.registry.connection(AdministrativeTenant(tenant), "app") as c:
                for table in (processing.intents, processing.batches, processing.publications):
                    c.execute(sa.select(table).limit(0))
                space = c.scalar(
                    sa.select(processing.spaces.c.id).where(
                        processing.spaces.c.profile_fingerprint == profile.fingerprint()
                    )
                )
                if space is None:
                    raise processing.ProcessingError("PROFILE_MISMATCH")
                processing._space(c, space, profile)

    def close(self):
        try:
            if self.registry is not None:
                self.registry.close()
        finally:
            if self.store is not None:
                self.store.close()
