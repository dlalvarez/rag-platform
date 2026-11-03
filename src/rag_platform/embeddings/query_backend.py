"""Worker-side query authorization. Returns embeddings only, never retrieved content."""

import logging

from rag_platform.control.identity import AccessError
from rag_platform.documents.errors import DocumentError
from rag_platform.embeddings import query_wire as wire
from rag_platform.embeddings.contracts import EmbeddingError, inputs, validate
from rag_platform.embeddings.retrieval_sql import identifiers
from rag_platform.embeddings.search import SearchService

LOGGER = logging.getLogger("rag_platform.embeddings")


class QueryBackend:
    def __init__(self, runtime, provider, ready):
        self.runtime, self.provider, self.ready = runtime, provider, ready
        self.profile = provider.profile
        self.policy = SearchService(runtime.repositories, provider)

    def execute(self, message):
        wire.shape(
            message, ("v", "operation", "context", "repositories", "space", "profile", "query")
        )
        if type(message["v"]) is not int or message["v"] != 1:
            raise EmbeddingError("INPUT_INVALID")
        if message["operation"] not in ("count", "embed"):
            raise EmbeddingError("INPUT_INVALID")
        context = wire.context_from_payload(message["context"])
        if context.tenant_id not in self.runtime.scope:
            raise DocumentError("ROLE_DENIED")
        if not isinstance(message["repositories"], list):
            raise EmbeddingError("INPUT_INVALID")
        repositories = tuple(wire.identifier(v) for v in message["repositories"])
        space = wire.identifier(message["space"])
        identifiers(context.principal_id, repositories, space, 1)
        text = message["query"]
        inputs(self.profile, (text,), "query")
        if (
            message["profile"] != self.profile.fingerprint()
            or self.provider.profile != self.profile
        ):
            raise EmbeddingError("PROFILE_MISMATCH")
        if not self.ready():
            raise EmbeddingError("DEPENDENCY_UNAVAILABLE")
        # Shared policy checks signature, current membership/catalog, every ACL and space.
        self.policy._read(context, context.trace_id, repositories, space, 1)
        count = self.provider.count_tokens(text, "query")
        if type(count) is not int or count < 1:
            raise EmbeddingError("INPUT_INVALID")
        if count > self.profile.max_tokens:
            raise EmbeddingError("INPUT_TOO_LONG")
        if not self.ready():
            raise EmbeddingError("DEPENDENCY_UNAVAILABLE")
        if self.provider.profile != self.profile:
            raise EmbeddingError("PROFILE_MISMATCH")
        result = dict(v=1, trace=str(context.trace_id), profile=self.profile.fingerprint())
        if message["operation"] == "embed":
            batch = validate(self.profile, (text,), "query", self.provider.embed((text,), "query"))
            if batch.input_tokens != (count,):
                raise EmbeddingError("INPUT_INVALID")
            LOGGER.info(
                "query_embedding request_id=%s input_tokens=%s requests=1",
                str(context.trace_id),
                count,
            )
            result.update(counts=list(batch.input_tokens), vectors=[list(v) for v in batch.vectors])
        else:
            result["count"] = count
        if not self.ready():
            raise EmbeddingError("DEPENDENCY_UNAVAILABLE")
        if self.provider.profile != self.profile:
            raise EmbeddingError("PROFILE_MISMATCH")
        # The initial signed context can expire while the model is running.
        fresh = self.runtime.authority.authorize(
            context.principal_id, context.tenant_id, context.trace_id
        )
        self.policy._read(fresh, context.trace_id, repositories, space, 1)
        return result

    def response(self, message):
        trace = None
        try:
            trace = str(wire.identifier(message.get("context", {}).get("trace")))
        except Exception:
            pass
        try:
            return self.execute(message)
        except AccessError as error:
            code = (
                "DEPENDENCY_UNAVAILABLE"
                if error.code in ("CATALOG_UNAVAILABLE", "TENANT_UNAVAILABLE")
                else "ROLE_DENIED"
            )
        except (DocumentError, EmbeddingError) as error:
            code = error.code
        except Exception:
            code = "DEPENDENCY_UNAVAILABLE"
        return {"v": 1, "trace": trace, "error": code}

    def __repr__(self):
        return "QueryBackend(<private evidence>)"
