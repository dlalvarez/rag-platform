"""Request-bound Unix provider. No model, query cache, bearer or SQL credential in IPC."""

import socket
from dataclasses import dataclass, field
from pathlib import Path

from rag_platform.control.identity import AccessError
from rag_platform.documents.errors import DocumentError
from rag_platform.embeddings import query_wire as wire
from rag_platform.embeddings.contracts import (
    EmbeddingBatch,
    EmbeddingError,
    EmbeddingProfile,
    inputs,
    validate,
)
from rag_platform.embeddings.qwen import qwen_profile
from rag_platform.embeddings.retrieval_sql import identifiers


@dataclass(frozen=True, slots=True, repr=False)
class QueryClient:
    path: Path
    authority: object
    context: object
    trace: object
    repositories: tuple
    space: object
    profile: object = field(default_factory=qwen_profile)

    def __post_init__(self):
        if (
            self.authority.profile != "embedding_publication"
            or not isinstance(self.profile, EmbeddingProfile)
            or self.profile.metric != "cosine"
            or self.profile.normalization != "l2"
        ):
            raise ValueError("Publication authority required")
        checked = self.authority.validate(self.context, self.trace)
        identifiers(checked.principal_id, self.repositories, self.space, 1)
        object.__setattr__(self, "context", checked)
        object.__setattr__(self, "repositories", tuple(self.repositories))
        object.__setattr__(self, "path", Path(self.path))

    def _call(self, operation, text):
        try:
            # Refresh the signed context for each RPC, including after a slow token count.
            context = self.authority.authorize(
                self.context.principal_id, self.context.tenant_id, self.trace
            )
            message = dict(
                v=1,
                operation=operation,
                context=wire.context_payload(context),
                repositories=[str(value) for value in self.repositories],
                space=str(self.space),
                profile=self.profile.fingerprint(),
                query=text,
            )
            wire.private_socket(self.path)
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(2)
                sock.connect(str(self.path))
                wire.peer(sock)
                wire.send(sock, message)
                response = wire.receive(sock, seconds=5 if operation == "count" else 30)
            if type(response.get("v")) is not int or response["v"] != 1:
                raise ValueError()
            if response.get("trace") != str(self.trace):
                raise ValueError()
            if "error" in response:
                wire.shape(response, ("v", "trace", "error"))
                code = response["error"]
                if isinstance(code, str) and code in DocumentError.STATUS:
                    raise DocumentError(code)
                raise EmbeddingError(code)
            if response.get("profile") != self.profile.fingerprint():
                raise EmbeddingError("PROFILE_MISMATCH")
            if operation == "count":
                wire.shape(response, ("v", "trace", "profile", "count"))
                count = response["count"]
                if type(count) is not int or not 1 <= count <= self.profile.max_tokens:
                    raise ValueError()
                return count
            wire.shape(response, ("v", "trace", "profile", "counts", "vectors"))
            batch = EmbeddingBatch(
                response["profile"],
                tuple(tuple(v) for v in response["vectors"]),
                tuple(response["counts"]),
            )
            return validate(self.profile, (text,), "query", batch)
        except (AccessError, DocumentError, EmbeddingError):
            raise
        except Exception:
            raise EmbeddingError("DEPENDENCY_UNAVAILABLE") from None

    def count_tokens(self, text, kind):
        inputs(self.profile, (text,), kind)
        if kind != "query":
            raise EmbeddingError("INPUT_INVALID")
        return self._call("count", text)

    def embed(self, texts, kind):
        inputs(self.profile, texts, kind)
        if kind != "query" or len(texts) != 1:
            raise EmbeddingError("INPUT_INVALID")
        return self._call("embed", texts[0])

    def __repr__(self):
        return "QueryClient(<private request context>)"
