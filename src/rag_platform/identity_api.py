"""F02 identity metadata API. No administrative or content endpoints."""

import logging
import os
import stat
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

import anyio
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from rag_platform.control.identity import AccessError, audit, register
from rag_platform.control.identity_queries import IdentityQueries
from rag_platform.providers.identity import IdentityError, OIDCSettings, OIDCVerifier
from rag_platform.providers.secrets import Credential
from rag_platform.provisioning.postgres import Target
from rag_platform.tenancy.authorization import TenantAuthorizer
from rag_platform.tenancy.resolver import control_engine

LOGGER = logging.getLogger("rag_platform.identity")


def private_file(path, max_size):
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        fd = os.open(path, flags)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_nlink != 1
                or not 1 <= info.st_size <= max_size
            ):
                raise ValueError()
            return stream.read(max_size + 1)
    except Exception:
        raise ValueError("Invalid private API configuration") from None


def create_app(engine, verifier, key: bytes, *, close_resources=False):
    queries, authority = IdentityQueries(engine, key), TenantAuthorizer(engine, key)

    @asynccontextmanager
    async def lifespan(app):
        yield
        if close_resources:
            verifier.close()
            engine.dispose()

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.authority, app.state.queries = authority, queries

    def error(request, code, status):
        LOGGER.info(
            "identity_request request_id=%s status=%s code=%s", request.state.trace_id, status, code
        )
        headers = {"Cache-Control": "no-store", "X-Request-ID": str(request.state.trace_id)}
        if status == 401:
            headers["WWW-Authenticate"] = "Bearer"
        return JSONResponse(
            {"error": {"version": "v1", "code": code}, "request_id": str(request.state.trace_id)},
            status_code=status,
            headers=headers,
        )

    def denial(request, reason):
        with engine.begin() as c:
            audit(
                c,
                request_id=request.state.trace_id,
                principal_id=getattr(request.state, "principal", None),
                reason=reason,
            )

    @app.middleware("http")
    async def boundary(request, call_next):
        request.state.trace_id = uuid4()  # Incoming trace headers cannot select another request.
        try:
            response = await call_next(request)
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Request-ID"] = str(request.state.trace_id)
            return response
        except Exception:
            # No raw URL, query, Authorization, exception text or traceback is emitted.
            return error(request, "DEPENDENCY_UNAVAILABLE", 503)

    @app.exception_handler(AccessError)
    async def access_error(request, exception):
        status = (
            503
            if exception.code == "CATALOG_UNAVAILABLE"
            else (422 if exception.code == "INPUT_INVALID" else 403)
        )
        try:
            await anyio.to_thread.run_sync(
                denial, request, "DEPENDENCY_UNAVAILABLE" if status == 503 else exception.code
            )
        except Exception:
            return error(request, "DEPENDENCY_UNAVAILABLE", 503)
        return error(request, exception.code, status)

    @app.exception_handler(IdentityError)
    async def identity_error(request, exception):
        unavailable = exception.code == "IDENTITY_UNAVAILABLE"
        try:
            await anyio.to_thread.run_sync(
                denial, request, "DEPENDENCY_UNAVAILABLE" if unavailable else "TOKEN_INVALID"
            )
        except Exception:
            return error(request, "DEPENDENCY_UNAVAILABLE", 503)
        return error(
            request,
            "IDENTITY_UNAVAILABLE" if unavailable else "TOKEN_INVALID",
            503 if unavailable else 401,
        )

    @app.exception_handler(RequestValidationError)
    async def invalid(request, exception):
        return error(request, "INPUT_INVALID", 422)

    @app.exception_handler(HTTPException)
    async def http_error(request, exception):
        return error(
            request,
            "NOT_FOUND" if exception.status_code == 404 else "INPUT_INVALID",
            exception.status_code,
        )

    def principal(request: Request):
        headers = request.headers.getlist("authorization")
        if len(headers) != 1 or len(headers[0]) > 16400:
            raise IdentityError()
        scheme, separator, bearer = headers[0].partition(" ")
        if scheme.lower() != "bearer" or not separator or not bearer or " " in bearer:
            raise IdentityError()
        identity = verifier.verify(bearer)
        request.state.principal = register(engine, identity, request.state.trace_id)
        return request.state.principal

    app.state.principal_dependency = principal

    @app.get("/healthz")
    def health():
        return {"status": "ok", "phase": "F02"}

    @app.get("/api/v1/me")
    def me(request: Request, actor=Depends(principal)):  # noqa: B008
        return {"request_id": str(request.state.trace_id), **queries.me(actor)}

    @app.get("/api/v1/tenants")
    def tenants(request: Request, actor=Depends(principal)):  # noqa: B008
        # Parse only the documented keys; do not echo a rejected value.
        if set(request.query_params) - {"limit", "cursor"} or any(
            len(request.query_params.getlist(name)) > 1 for name in ("limit", "cursor")
        ):
            raise AccessError("INPUT_INVALID")
        raw = request.query_params.get("limit", "50")
        if not raw.isascii() or not raw.isdecimal() or len(raw) > 3:
            raise AccessError("INPUT_INVALID")
        return {
            "request_id": str(request.state.trace_id),
            **queries.tenants(actor, limit=int(raw), cursor=request.query_params.get("cursor")),
        }

    return app


def create_configured_app():
    settings = OIDCSettings(
        issuer=os.environ["RAG_OIDC_ISSUER"],
        audience=os.environ["RAG_OIDC_AUDIENCE"],
        jwks_url=os.environ["RAG_OIDC_JWKS"],
        ca_file=Path("/tls/ca.crt"),
        leeway=0,
    )
    credential = Credential(
        "f02_identity_app", private_file("/run/secrets/identity_app_password", 4096).decode()
    )
    key = private_file("/run/secrets/api_authority_key", 32)
    if len(key) != 32:
        raise ValueError("Invalid private API configuration")
    engine = control_engine(Target("postgres", 5432, Path("/run/f01-ca.crt")), credential)
    return create_app(engine, OIDCVerifier(settings), key, close_resources=True)
