"""T006 loopback-only harness. These routes are never installed in the product API."""

import logging
import os
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
from threading import RLock
from uuid import UUID

import sqlalchemy as sa
from f01_daily import session as daily_session
from f02_common import engine
from fastapi import Depends, Request

from rag_platform.control.identity import AccessError
from rag_platform.control.models import StorageLocation
from rag_platform.identity_api import create_app, private_file
from rag_platform.providers.identity import OIDCSettings, OIDCVerifier
from rag_platform.provisioning.postgres import Target
from rag_platform.provisioning.storage import StorageNames, StorageTarget
from rag_platform.tenancy.authorization import AuthorizedConnections
from rag_platform.tenancy.registry import ConnectionRegistry, tenant_engine
from rag_platform.tenancy.resolver import CatalogResolver

CA = Path("/run/f01-ca.crt")


def factory():
    resources = []
    try:
        control = engine()
        resources.append(control.dispose)
        day = daily_session()
        store, _role, _used = day.__enter__()
        resources.append(lambda: day.__exit__(None, None, None))
        settings = OIDCSettings(
            os.environ["RAG_OIDC_ISSUER"],
            os.environ["RAG_OIDC_AUDIENCE"],
            os.environ["RAG_OIDC_JWKS"],
            Path("/tls/ca.crt"),
            leeway=0,
        )
        verifier = OIDCVerifier(settings)
        resources.append(verifier.close)
        app = create_app(control, verifier, private_file("/run/secrets/api_authority_key", 32))
        counts = {"secrets": 0, "connections": 0, "queries": 0, "s3": 0}
        lock = RLock()

        def increment(name):
            with lock:
                counts[name] += 1

        class CountedStore:
            def read(self, ref):
                increment("secrets")
                return store.read(ref)

        counted = CountedStore()

        original_connect = Target.connect

        def counted_connect(target, database, credential, **options):
            if database.startswith("rag_t_"):
                increment("connections")  # Count attempts, including rejected connections.
            return original_connect(target, database, credential, **options)

        Target.connect = counted_connect
        resources.append(lambda: setattr(Target, "connect", original_connect))

        def counted_engine(destination, secret_store, ca):
            result = tenant_engine(destination, secret_store, ca)

            @sa.event.listens_for(result, "before_cursor_execute")
            def query(connection, cursor, statement, parameters, context, executemany):
                increment("queries")

            return result

        registry = ConnectionRegistry(
            CatalogResolver(control), counted, CA, engine_factory=counted_engine
        )
        resources.append(registry.close)
        connections = AuthorizedConnections(app.state.authority, registry)
        principal = app.state.principal_dependency
        probe = {"stage": "IDLE", "failure": "NONE", "sqlstate": "NONE"}

        @asynccontextmanager
        async def lifespan(application):
            try:
                yield
            finally:
                for close in reversed(resources):
                    close()

        app.router.lifespan_context = lifespan

        @app.get("/__test/counters")
        def counters():
            with lock:
                return dict(counts)

        @app.get("/__test/status")
        def status():
            return dict(probe)

        @app.get("/__test/context/{tenant}")
        def context(tenant: UUID, request: Request, actor=Depends(principal)):  # noqa: B008
            try:
                probe["stage"] = "AUTHORIZATION"
                authorized = app.state.authority.authorize(actor, tenant, request.state.trace_id)
                forge = request.query_params.get("forge")
                trace = request.state.trace_id
                if forge:
                    try:
                        authorized = replace(authorized, tenant_id=UUID(forge))
                    except ValueError:
                        raise AccessError("INPUT_INVALID") from None
                if request.query_params.get("other_request"):
                    from uuid import uuid4

                    trace = uuid4()
                probe["stage"] = "CONNECTION"
                with connections.connection(authorized, trace) as c:
                    probe["stage"] = "SQL_IDENTITY"
                    row = c.execute(
                        sa.text(
                            "SELECT current_database(),current_user,ssl FROM pg_stat_ssl "
                            "WHERE pid=pg_backend_pid()"
                        )
                    ).one()
                    expected_db = "rag_t_" + tenant.hex
                    expected_role = "readonly" if authorized.roles == ("reader",) else "app"
                    if (row[0], row[1], row[2]) != (
                        expected_db,
                        expected_db + "_" + expected_role,
                        True,
                    ):
                        raise AccessError("STATE_CONFLICT")
                    # F01 deliberately restricts operational identity/version tables.
                    # Exercise actual tenant SQL without creating F03 content or widening grants.
                    probe["stage"] = "SQL_READ"
                    if (
                        c.scalar(
                            sa.text(
                                "SELECT has_table_privilege(current_user,"
                                "'public.ops_identity','SELECT')"
                            )
                        )
                        is not False
                    ):
                        raise AccessError("STATE_CONFLICT")
                    if c.scalar(sa.text("SELECT '[1,2,3]'::public.vector")) is None:
                        raise AccessError("STATE_CONFLICT")
                probe["stage"] = "STORAGE_CATALOG"
                with control.connect() as c:
                    location = c.execute(
                        sa.select(StorageLocation.endpoint, StorageLocation.bucket).where(
                            StorageLocation.tenant_id == tenant
                        )
                    ).one()
                if (
                    location.endpoint != "https://minio:9000"
                    or location.bucket != StorageNames(tenant).bucket
                ):
                    raise AccessError("TENANT_UNAVAILABLE")
                probe["stage"] = "STORAGE_CONTEXT"
                app.state.authority.validate(authorized, trace)
                probe["stage"] = "STORAGE_SECRET"
                credential = counted.read(authorized.storage_ref)
                if credential.username != StorageNames(tenant).user:
                    raise AccessError("TENANT_UNAVAILABLE")
                storage = StorageTarget(location.endpoint, CA)
                try:
                    increment("s3")
                    probe["stage"] = "STORAGE_LIST"
                    list(storage.s3(credential).list_objects(location.bucket))
                finally:
                    storage.close()
                return {
                    "tenant_id": str(tenant),
                    "role": authorized.roles[0],
                    "sql": True,
                    "s3": True,
                }
            except Exception as error:
                name = type(error).__name__
                probe["failure"] = (
                    name
                    if name
                    in {
                        "AccessError",
                        "TenantAccessError",
                        "SecretStoreError",
                        "ProgrammingError",
                        "OperationalError",
                        "S3Error",
                        "TypeError",
                        "AttributeError",
                        "AssertionError",
                    }
                    else "OTHER"
                )
                state = getattr(getattr(error, "orig", error), "sqlstate", None)
                probe["sqlstate"] = (
                    state if state in {"42501", "42P01", "28000", "28P01"} else "NONE"
                )
                raise

        return app
    except Exception:
        for close in reversed(resources):
            try:
                close()
            except Exception:
                pass
        raise SystemExit("F02-T006 FIXTURE_START: stopped; no sensitive details.") from None


logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
