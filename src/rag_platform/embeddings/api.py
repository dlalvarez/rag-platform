"""Opt-in F05 HTTP fragments; signed identity and private provider stay server-side."""

import json
import threading
from pathlib import Path
from uuid import UUID

import anyio
from fastapi import Depends, Request
from fastapi.responses import JSONResponse

from rag_platform.documents.api import blocking, framing, parameters, single, unique_pairs
from rag_platform.documents.errors import DocumentError
from rag_platform.embeddings.contracts import EmbeddingError, inputs
from rag_platform.embeddings.query_client import QueryClient
from rag_platform.embeddings.qwen import qwen_profile
from rag_platform.embeddings.retrieval_sql import SearchError, identifiers
from rag_platform.embeddings.search import SearchService

MAX_BODY = 65536
MAX_RESPONSE = 262144


def invalid_constant(_value):
    raise ValueError()


async def body(request):
    parameters(request, ())
    if single(request, "content-type", required=True) not in (
        "application/json",
        "application/json; charset=utf-8",
    ):
        raise DocumentError("INPUT_INVALID")
    expected, data = framing(request, MAX_BODY), bytearray()
    try:
        with anyio.fail_after(20):
            async for chunk in request.stream():
                if len(data) + len(chunk) > MAX_BODY:
                    raise DocumentError("TOO_LARGE")
                data.extend(chunk)
        if expected is not None and len(data) != expected:
            raise ValueError()
        value = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=unique_pairs,
            parse_constant=invalid_constant,
        )
        if not isinstance(value, dict) or set(value) != {
            "repository_ids",
            "space_id",
            "query",
            "top_k",
        }:
            raise ValueError()
        return value
    except (ValueError, UnicodeError, TimeoutError):
        raise DocumentError("INPUT_INVALID") from None


def selection(data, actor):
    try:
        raw, space = data["repository_ids"], data["space_id"]
        if not isinstance(raw, list) or not 1 <= len(raw) <= 16:
            raise ValueError()
        if not isinstance(space, str) or any(not isinstance(v, str) for v in raw):
            raise ValueError()
        repos, space = tuple(UUID(v) for v in raw), UUID(space)
        identifiers(actor, repos, space, data["top_k"])
        inputs(qwen_profile(), (data["query"],), "query")
        return repos, space, data["query"], data["top_k"]
    except (ValueError, TypeError, EmbeddingError, SearchError):
        raise DocumentError("INPUT_INVALID") from None


def install(app, runtime, path):
    if runtime.authority.profile != "embedding_publication":
        raise ValueError("Publication profile required")
    path, slots = Path(path), threading.BoundedSemaphore(2)
    principal = app.state.principal_dependency

    async def authorized(tenant_id: UUID, request: Request, actor=Depends(principal)):  # noqa: B008
        return await blocking(runtime.authority.authorize, actor, tenant_id, request.state.trace_id)

    @app.post("/api/v1/tenants/{tenant_id}/search")
    async def search(request: Request, ctx=Depends(authorized)):  # noqa: B008
        # Identity and tenant membership precede reading the bounded body.
        data = await body(request)
        repos, space, query, top_k = selection(data, ctx.principal_id)
        if not slots.acquire(blocking=False):
            raise DocumentError("QUOTA_EXCEEDED")
        try:

            def execute():
                trace = request.state.trace_id
                provider = QueryClient(path, runtime.authority, ctx, trace, repos, space)
                return SearchService(runtime.repositories, provider).search(
                    ctx, trace, repos, space, query, top_k
                )

            result = await blocking(execute)
            payload = {
                "request_id": str(request.state.trace_id),
                "space_id": str(space),
                "hits": [
                    {
                        "repository_id": str(hit.repository_id),
                        "document_id": str(hit.document_id),
                        "version_id": str(hit.version_id),
                        "chunk_id": str(hit.chunk_id),
                        "score": hit.score,
                        "excerpt": hit.excerpt,
                        "page": hit.page,
                        "section": list(hit.section) if hit.section is not None else None,
                    }
                    for hit in result.hits
                ],
                "usage": {
                    "embedding_input_tokens": result.embedding_input_tokens,
                    "embedding_requests": result.embedding_requests,
                },
            }
            response = JSONResponse(payload)
            if len(response.body) > MAX_RESPONSE:
                raise DocumentError("DEPENDENCY_UNAVAILABLE")
            return response
        finally:
            slots.release()
