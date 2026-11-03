"""Authorized internal hybrid search and citation resolution; F05 HTTP stays exact."""

from dataclasses import dataclass

from rag_platform.documents.errors import DocumentError
from rag_platform.embeddings.contracts import EmbeddingError, inputs
from rag_platform.embeddings.processing import ProcessingError, _space
from rag_platform.embeddings.retrieval_sql import SearchError, identifiers
from rag_platform.embeddings.search import SearchService, failure
from rag_platform.retrieval.contracts import (
    RRF_REVISION,
    CitationRef,
    HybridHit,
    QueryFilters,
    RetrievalError,
)
from rag_platform.retrieval.sql import hybrid, resolve

EMPTY_FILTERS = QueryFilters()


def retrieval_failure(error):
    if error.code == "NOT_FOUND":
        return DocumentError("NOT_FOUND")
    return failure(error.code)


@dataclass(frozen=True, slots=True, repr=False)
class HybridResult:
    hits: tuple[HybridHit, ...]
    embedding_input_tokens: int
    embedding_requests: int = 1
    ranking_revision: str = RRF_REVISION

    def __repr__(self):
        return "HybridResult(<private evidence>)"


class HybridService(SearchService):
    def _operation(self, context, trace, repositories, space, operation):
        def read(c, checked):
            if c.dialect.name == "postgresql":
                c.exec_driver_sql("SET LOCAL lock_timeout='5s'")
                c.exec_driver_sql("SET LOCAL statement_timeout='15s'")
            for repository in repositories:
                self.repositories._row(c, checked, repository, "read")
            try:
                _space(c, space, self.profile)
                result = operation(c, checked)
            except (ProcessingError, SearchError, RetrievalError) as error:
                raise retrieval_failure(error) from None
            self.authority.validate(checked, trace)
            return result

        return self.repositories._run(context, trace, "read", read)

    def search(self, context, trace, repositories, space, query, top_k, filters=EMPTY_FILTERS):
        checked = self.authority.validate(context, trace)
        if not isinstance(filters, QueryFilters):
            raise DocumentError("INPUT_INVALID")
        try:
            identifiers(checked.principal_id, repositories, space, top_k)
            inputs(self.profile, (query,), "query")
        except (EmbeddingError, SearchError) as error:
            raise failure(
                "INPUT_INVALID" if error.code == "LIMIT_EXCEEDED" else error.code
            ) from None
        repositories = tuple(repositories)
        # Base preflight checks all ACL and space/profile before tokenization/inference.
        self._read(checked, trace, repositories, space, top_k)
        response = self._embed(query)
        fresh = self.authority.authorize(checked.principal_id, checked.tenant_id, trace)
        hits = self._operation(
            fresh,
            trace,
            repositories,
            space,
            lambda c, active: hybrid(
                c,
                active.tenant_id,
                active.principal_id,
                repositories,
                space,
                self.profile,
                response.vectors[0],
                query,
                top_k,
                filters,
            ),
        )
        return HybridResult(hits, response.total_tokens)

    def resolve_citation(self, context, trace, reference):
        checked = self.authority.validate(context, trace)
        if not isinstance(reference, CitationRef):
            raise DocumentError("INPUT_INVALID")
        if reference.tenant_id != checked.tenant_id:
            raise DocumentError("ROLE_DENIED")
        return self._operation(
            checked,
            trace,
            (reference.repository_id,),
            reference.space_id,
            lambda c, active: resolve(
                c, active.tenant_id, active.principal_id, reference, self.profile
            ),
        )
