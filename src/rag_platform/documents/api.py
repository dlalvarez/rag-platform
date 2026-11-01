"""F03 HTTP adapter: bounded raw uploads, explicit ACL and verified original proxy."""

import json
import threading
from functools import partial
from pathlib import Path
from urllib.parse import quote
from uuid import UUID

import anyio
from fastapi import Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from rag_platform.documents.content import DocumentService
from rag_platform.documents.errors import DocumentError
from rag_platform.documents.receipt import ReceiptService, valid_key
from rag_platform.documents.repositories import RepositoryService
from rag_platform.documents.storage import ObjectGateway
from rag_platform.documents.validation import MAX_BYTES, UploadSpool
from rag_platform.providers.application_handoff import FileApplicationStore
from rag_platform.tenancy.authorization import AuthorizedConnections, TenantAuthorizer
from rag_platform.tenancy.registry import ConnectionRegistry
from rag_platform.tenancy.resolver import CatalogResolver

BASE = "/api/v1/tenants/{tenant_id}/repositories"


async def blocking(function, *args, **kwargs):
    return await anyio.to_thread.run_sync(partial(function, *args, **kwargs))


def single(request, name, *, required=False):
    values = request.headers.getlist(name)
    if len(values) > 1 or (required and len(values) != 1):
        raise DocumentError("INPUT_INVALID")
    return values[0] if values else None


def framing(request, maximum):
    encoding = single(request, "content-encoding")
    length = single(request, "content-length")
    transfer = single(request, "transfer-encoding")
    if encoding not in (None, "identity") or (length is not None and transfer is not None):
        raise DocumentError("INPUT_INVALID")
    if length is not None:
        if not length.isascii() or not length.isdecimal() or len(length) > 9:
            raise DocumentError("INPUT_INVALID")
        if int(length) > maximum:
            raise DocumentError("TOO_LARGE")
    return int(length) if length is not None else None


def parameters(request, allowed):
    if set(request.query_params) - set(allowed) or any(
        len(request.query_params.getlist(name)) > 1 for name in allowed
    ):
        raise DocumentError("INPUT_INVALID")


def page(request):
    parameters(request, ("limit", "cursor"))
    value = request.query_params.get("limit", "50")
    if not value.isascii() or not value.isdecimal() or len(value) > 3:
        raise DocumentError("INPUT_INVALID")
    return {"limit": int(value), "cursor": request.query_params.get("cursor")}


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError()
        result[key] = value
    return result


async def body_json(request):
    parameters(request, ())
    if single(request, "content-type", required=True) not in (
        "application/json",
        "application/json; charset=utf-8",
    ):
        raise DocumentError("INPUT_INVALID")
    expected, data = framing(request, 4096), bytearray()
    try:
        with anyio.fail_after(20):
            async for chunk in request.stream():
                if len(data) + len(chunk) > 4096:
                    raise DocumentError("TOO_LARGE")
                data.extend(chunk)
        if expected is not None and len(data) != expected:
            raise ValueError()
        value = json.loads(data.decode("utf-8"), object_pairs_hook=unique_pairs)
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (ValueError, UnicodeError, TimeoutError):
        raise DocumentError("INPUT_INVALID") from None


class OriginalResponse(StreamingResponse):
    def __init__(self, download, release):
        self.download, self.release = download, release
        file = download.file
        headers = {
            "Content-Disposition": "attachment; filename=\"download\"; filename*=UTF-8''"
            + quote(file.filename, safe=""),
            "Content-Length": str(file.byte_size),
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox",
            "Referrer-Policy": "no-referrer",
        }
        super().__init__(download.chunks(), media_type=file.mime, headers=headers)

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            try:
                self.download.close()
            finally:
                self.release()


class Runtime:
    def __init__(self, engine, key, path, endpoint, ca):
        self.store, self.registry = None, None
        try:
            self.store = FileApplicationStore(path, endpoint, ca)
            self.authority = TenantAuthorizer(engine, key, profile="documents")
            self.registry = ConnectionRegistry(
                CatalogResolver(engine, profile="documents"), self.store, ca
            )
            connections = AuthorizedConnections(self.authority, self.registry)
            self.repositories = RepositoryService(connections, engine, key)
            self.gateway = ObjectGateway(self.repositories, self.store, ca)
            self.receipts = ReceiptService(self.repositories, self.gateway)
            self.documents = DocumentService(self.repositories, self.gateway)
        except BaseException:
            self.close()
            raise

    def close(self):
        try:
            if self.registry is not None:
                self.registry.close()
        finally:
            if self.store is not None:
                self.store.close()


def install(app, runtime):
    principal = app.state.principal_dependency
    uploads, downloads = threading.BoundedSemaphore(2), threading.BoundedSemaphore(2)
    app.state.document_runtime = runtime
    app.state.phase = "F03"

    @app.exception_handler(DocumentError)
    async def document_error(request, error):
        return app.state.error_response(request, error.code, error.status)

    async def authorized(tenant_id: UUID, request: Request, actor=Depends(principal)):  # noqa: B008
        trace = request.state.trace_id
        return await blocking(runtime.authority.authorize, actor, tenant_id, trace)

    def reply(request, **fields):
        return {"request_id": str(request.state.trace_id), **fields}

    @app.get(BASE)
    async def repositories(request: Request, ctx=Depends(authorized)):  # noqa: B008
        result = await blocking(
            runtime.repositories.list, ctx, request.state.trace_id, **page(request)
        )
        return reply(request, **result)

    @app.post(BASE)
    async def create_repository(request: Request, ctx=Depends(authorized)):  # noqa: B008
        data = await body_json(request)
        if set(data) - {"name", "config"} or "name" not in data:
            raise DocumentError("INPUT_INVALID")
        result = await blocking(
            runtime.repositories.create,
            ctx,
            request.state.trace_id,
            data["name"],
            data.get("config"),
        )
        return JSONResponse(reply(request, repository=result), status_code=201)

    @app.get(BASE + "/{repo_id}")
    async def repository(repo_id: UUID, request: Request, ctx=Depends(authorized)):  # noqa: B008
        parameters(request, ())
        result = await blocking(runtime.repositories.show, ctx, request.state.trace_id, repo_id)
        return reply(request, repository=result)

    @app.put(BASE + "/{repo_id}")
    async def update_repository(repo_id: UUID, request: Request, ctx=Depends(authorized)):  # noqa: B008
        data = await body_json(request)
        if set(data) - {"name", "config"} or "name" not in data:
            raise DocumentError("INPUT_INVALID")
        result = await blocking(
            runtime.repositories.update,
            ctx,
            request.state.trace_id,
            repo_id,
            data["name"],
            data.get("config"),
        )
        return reply(request, repository=result)

    @app.delete(BASE + "/{repo_id}")
    async def delete_repository(repo_id: UUID, request: Request, ctx=Depends(authorized)):  # noqa: B008
        parameters(request, ())
        result = await blocking(runtime.repositories.delete, ctx, request.state.trace_id, repo_id)
        return reply(request, repository=result)

    @app.get(BASE + "/{repo_id}/acl")
    async def acl(repo_id: UUID, request: Request, ctx=Depends(authorized)):  # noqa: B008
        result = await blocking(
            runtime.repositories.acl, ctx, request.state.trace_id, repo_id, **page(request)
        )
        return reply(request, **result)

    @app.put(BASE + "/{repo_id}/acl/{target_id}")
    async def set_acl(repo_id: UUID, target_id: UUID, request: Request, ctx=Depends(authorized)):  # noqa: B008
        data = await body_json(request)
        if set(data) != {"role"} or data["role"] is None:
            raise DocumentError("INPUT_INVALID")
        result = await blocking(
            runtime.repositories.set_acl,
            ctx,
            request.state.trace_id,
            repo_id,
            target_id,
            data["role"],
        )
        return reply(request, acl=result)

    @app.delete(BASE + "/{repo_id}/acl/{target_id}")
    async def remove_acl(repo_id: UUID, target_id: UUID, request: Request, ctx=Depends(authorized)):  # noqa: B008
        parameters(request, ())
        result = await blocking(
            runtime.repositories.set_acl, ctx, request.state.trace_id, repo_id, target_id, None
        )
        return reply(request, acl=result)

    @app.get(BASE + "/{repo_id}/documents")
    async def documents(repo_id: UUID, request: Request, ctx=Depends(authorized)):  # noqa: B008
        result = await blocking(
            runtime.documents.list, ctx, request.state.trace_id, repo_id, **page(request)
        )
        return reply(request, **result)

    @app.get(BASE + "/{repo_id}/documents/{document_id}")
    async def document(repo_id: UUID, document_id: UUID, request: Request, ctx=Depends(authorized)):  # noqa: B008
        parameters(request, ())
        result = await blocking(
            runtime.documents.show, ctx, request.state.trace_id, repo_id, document_id
        )
        return reply(request, document=result)

    @app.post(BASE + "/{repo_id}/documents")
    async def upload(repo_id: UUID, request: Request, ctx=Depends(authorized)):  # noqa: B008
        trace = request.state.trace_id
        # ACL before reading body, allocating spool or opening S3.
        await blocking(runtime.receipts.preflight, ctx, trace, repo_id)
        parameters(request, ("filename",))
        name = request.query_params.get("filename")
        mime = single(request, "content-type", required=True)
        key = single(request, "idempotency-key", required=True)
        if not valid_key(key):
            raise DocumentError("INPUT_INVALID")
        expected = framing(request, MAX_BYTES)
        if not uploads.acquire(blocking=False):
            raise DocumentError("QUOTA_EXCEEDED")
        try:
            with UploadSpool(name, mime) as spool:
                try:
                    with anyio.fail_after(20):
                        async for chunk in request.stream():
                            await blocking(spool.accept, chunk)
                except TimeoutError:
                    raise DocumentError("INPUT_INVALID") from None
                file = await blocking(spool.finish)
                if expected is not None and file.byte_size != expected:
                    raise DocumentError("INPUT_INVALID")
                result = await blocking(runtime.receipts.receive, ctx, trace, repo_id, key, file)
                return JSONResponse(
                    reply(request, document=result.document),
                    status_code=201 if result.created else 200,
                )
        finally:
            uploads.release()

    @app.get(BASE + "/{repo_id}/documents/{document_id}/original")
    async def original(repo_id: UUID, document_id: UUID, request: Request, ctx=Depends(authorized)):  # noqa: B008
        parameters(request, ())
        if any(name in request.headers for name in ("range", "if-range")):
            raise DocumentError("INPUT_INVALID")
        if not downloads.acquire(blocking=False):
            raise DocumentError("QUOTA_EXCEEDED")
        prepared = None
        try:
            prepared = await blocking(
                runtime.documents.original, ctx, request.state.trace_id, repo_id, document_id
            )
            return OriginalResponse(prepared, downloads.release)
        except BaseException:
            if prepared is not None:
                prepared.close()
            downloads.release()
            raise


def configure(app, engine, key):
    runtime = Runtime(
        engine, key, Path("/run/f03-application"), "https://openbao:8200", Path("/run/f01-ca.crt")
    )
    try:
        install(app, runtime)
        app.state.resource_closers.append(runtime.close)
    except BaseException:
        runtime.close()
        raise
