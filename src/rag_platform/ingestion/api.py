"""Opt-in F04 metadata/tombstone HTTP adapter, using existing F03 authorization."""

from uuid import UUID

import anyio
from fastapi import Depends, Request

from rag_platform.documents.api import blocking, framing, page, parameters
from rag_platform.documents.errors import DocumentError

BASE = "/api/v1/tenants/{tenant_id}"


def install(app, runtime, authorized, reply):
    @app.get(BASE + "/documents/{doc_id}/versions")
    async def versions(doc_id: UUID, request: Request, ctx=Depends(authorized)):  # noqa: B008
        result = await blocking(
            runtime.ingestion.versions, ctx, request.state.trace_id, doc_id, **page(request)
        )
        return reply(request, **result)

    @app.get(BASE + "/jobs/{job_id}")
    async def job(job_id: UUID, request: Request, ctx=Depends(authorized)):  # noqa: B008
        parameters(request, ())
        result = await blocking(runtime.ingestion.job, ctx, request.state.trace_id, job_id)
        return reply(request, job=result)

    @app.delete(BASE + "/documents/{doc_id}")
    async def delete(doc_id: UUID, request: Request, ctx=Depends(authorized)):  # noqa: B008
        parameters(request, ())
        framing(request, 0)
        try:
            with anyio.fail_after(5):
                async for chunk in request.stream():
                    if chunk:
                        raise DocumentError("INPUT_INVALID")
        except TimeoutError:
            raise DocumentError("INPUT_INVALID") from None
        result = await blocking(runtime.document_state.delete, ctx, request.state.trace_id, doc_id)
        return reply(request, document=result)
