"""Authorized query orchestration. Provider wiring and HTTP activation are separate."""

from dataclasses import dataclass

from rag_platform.control.identity import AccessError
from rag_platform.documents.errors import DocumentError
from rag_platform.documents.repositories import RepositoryService
from rag_platform.embeddings.contracts import EmbeddingError, EmbeddingProfile, inputs, validate
from rag_platform.embeddings.processing import ProcessingError, _space
from rag_platform.embeddings.retrieval_sql import Hit, SearchError, exact, identifiers


def failure(code):
    return DocumentError(
        {
            "INPUT_INVALID": "INPUT_INVALID",
            "INPUT_TOO_LONG": "INPUT_INVALID",
            "LIMIT_EXCEEDED": "QUOTA_EXCEEDED",
            "PROFILE_MISMATCH": "STATE_CONFLICT",
        }.get(code, "DEPENDENCY_UNAVAILABLE")
    )


@dataclass(frozen=True, slots=True, repr=False)
class SearchResult:
    hits: tuple[Hit, ...]
    embedding_input_tokens: int
    embedding_requests: int = 1

    def __repr__(self):
        return "SearchResult(<private evidence>)"


class SearchService:
    def __init__(self, repositories, provider):
        if (
            not isinstance(repositories, RepositoryService)
            or repositories.authority.profile != "embedding_publication"
            or not isinstance(provider.profile, EmbeddingProfile)
            or provider.profile.metric != "cosine"
            or provider.profile.normalization != "l2"
        ):
            raise ValueError("Explicit publication authority and cosine provider required")
        self.repositories, self.provider = repositories, provider
        self.authority, self.profile = repositories.authority, provider.profile

    def _read(self, context, trace, repositories, space, top_k, vector=None):
        def operation(c, checked):
            if c.dialect.name == "postgresql":
                c.exec_driver_sql("SET LOCAL lock_timeout='5s'")
                c.exec_driver_sql("SET LOCAL statement_timeout='15s'")
            # Reject the entire request if even one repository lacks permission.
            for repository in repositories:
                self.repositories._row(c, checked, repository, "read")
            try:
                _space(c, space, self.profile)
                hits = (
                    None
                    if vector is None
                    else exact(
                        c, checked.principal_id, repositories, space, self.profile, vector, top_k
                    )
                )
            except (ProcessingError, SearchError) as error:
                raise failure(error.code) from None
            # Recheck control state before returning any private evidence.
            self.authority.validate(checked, trace)
            return hits

        return self.repositories._run(context, trace, "read", operation)

    def search(self, context, trace, repositories, space, query, top_k):
        checked = self.authority.validate(context, trace)
        try:
            identifiers(checked.principal_id, repositories, space, top_k)
            inputs(self.profile, (query,), "query")
        except (EmbeddingError, SearchError) as error:
            # Input shape/character limits are validation errors, not provider saturation.
            raise failure(
                "INPUT_INVALID" if error.code == "LIMIT_EXCEEDED" else error.code
            ) from None
        repositories = tuple(repositories)
        self._read(checked, trace, repositories, space, top_k)

        # No tenant/control connection or transaction is held during tokenization/inference.
        try:
            if self.provider.profile != self.profile:
                raise EmbeddingError("PROFILE_MISMATCH")
            count = self.provider.count_tokens(query, "query")
            if type(count) is not int or count < 1:
                raise EmbeddingError("INPUT_INVALID")
            if count > self.profile.max_tokens:
                raise EmbeddingError("INPUT_TOO_LONG")
            response = validate(
                self.profile, (query,), "query", self.provider.embed((query,), "query")
            )
            if response.input_tokens != (count,):
                raise EmbeddingError("INPUT_INVALID")
            if self.provider.profile != self.profile:
                raise EmbeddingError("PROFILE_MISMATCH")
        except (AccessError, DocumentError):
            raise
        except EmbeddingError as error:
            raise failure(error.code) from None
        except Exception:
            raise DocumentError() from None

        # The previous signed context may have expired during inference. Authorize afresh.
        fresh = self.authority.authorize(checked.principal_id, checked.tenant_id, trace)
        hits = self._read(fresh, trace, repositories, space, top_k, response.vectors[0])
        return SearchResult(hits, response.total_tokens)
