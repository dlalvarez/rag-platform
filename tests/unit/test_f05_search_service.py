"""Real offline authority/ACL transactions; exact pgvector has its native SQL probe."""

from dataclasses import replace
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from test_f05_embedding_worker import setup  # noqa: F401

from rag_platform.control.identity import AccessError
from rag_platform.control.identity_models import Membership, TenantProfile
from rag_platform.documents.errors import DocumentError
from rag_platform.documents.repositories import RepositoryService
from rag_platform.embeddings import processing, search
from rag_platform.embeddings.contracts import EmbeddingBatch
from rag_platform.embeddings.retrieval_sql import Hit


@pytest.fixture
def case(setup, monkeypatch):  # noqa: F811
    s = setup
    s.runtime.repositories.connections.authority = s.runtime.authority
    repositories = RepositoryService(
        s.runtime.repositories.connections, s.control, b"k" * 32, profile="embedding_publication"
    )
    service = search.SearchService(repositories, s.provider)
    trace = uuid4()
    context = s.runtime.authority.authorize(s.actor, s.tenant, trace)
    hit = Hit(s.repo, s.doc, s.version, uuid4(), 1.0, "PRIVATE_RESULT", None, ("Title",))
    calls, counts = [], []
    original_count = s.provider.count_tokens

    def count_tokens(text, kind):
        assert s.control.pool.checkedout() == s.engine.pool.checkedout() == 0
        counts.append(kind)
        return original_count(text, kind)

    monkeypatch.setattr(s.provider, "count_tokens", count_tokens)

    def exact(c, actor, repos, space, profile, vector, top_k):
        assert c.in_transaction() and actor == s.actor and repos == (s.repo,)
        calls.append((space, top_k))
        return (hit,)

    monkeypatch.setattr(search, "exact", exact)
    space = s.vector.c.space_id.table.name.removeprefix("embeddings_")
    return SimpleNamespace(
        s=s,
        service=service,
        trace=trace,
        context=context,
        space=UUID(hex=space),
        hit=hit,
        calls=calls,
        counts=counts,
    )


def run(case, *, repositories=None, query="consulta privada"):
    return case.service.search(
        case.context,
        case.trace,
        (case.s.repo,) if repositories is None else repositories,
        case.space,
        query,
        3,
    )


def test_search_releases_connections_and_returns_only_evidence_usage(case):
    def inference(_texts):
        assert case.s.control.pool.checkedout() == 0
        assert case.s.engine.pool.checkedout() == 0

    case.s.provider.callback = inference
    result = run(case)
    assert result.hits == (case.hit,)
    assert result.embedding_requests == 1 and result.embedding_input_tokens > 0
    assert len(case.calls) == len(case.s.provider.calls) == 1
    assert "PRIVATE_RESULT" not in repr(result)


def test_any_unauthorized_repository_refuses_before_provider(case):
    with pytest.raises(DocumentError, match="ROLE_DENIED"):
        run(case, repositories=(case.s.repo, uuid4()))
    assert case.s.provider.calls == case.calls == case.counts == []


@pytest.mark.parametrize("change", ["acl", "membership", "tenant", "space"])
def test_revocation_during_inference_returns_no_evidence(case, change):
    s = case.s

    def revoke(_texts):
        if change == "acl":
            with s.engine.begin() as c:
                c.execute(s.md.tables["security.repository_acl"].delete())
        elif change == "membership":
            with s.control.begin() as c:
                c.execute(sa.update(Membership).values(state="REVOKED"))
        elif change == "tenant":
            with s.control.begin() as c:
                c.execute(sa.delete(TenantProfile))
        else:
            with s.engine.begin() as c:
                c.execute(processing.spaces.update().values(model="other-model"))

    s.provider.callback = revoke
    with pytest.raises((AccessError, DocumentError)):
        run(case)
    assert case.calls == [] and len(s.provider.calls) == 1


def test_context_expiring_during_inference_is_replaced(case, monkeypatch):
    import rag_platform.tenancy.authorization as authorization

    now = authorization.time.time()
    monkeypatch.setattr(authorization.time, "time", lambda: now)
    case.s.provider.callback = lambda _texts: monkeypatch.setattr(
        authorization.time, "time", lambda: now + 40
    )
    assert run(case).hits == (case.hit,)
    with pytest.raises(AccessError, match="INPUT_INVALID"):
        case.s.runtime.authority.validate(case.context, case.trace)


def test_profile_mismatch_refuses_before_tokenization(case):
    with case.s.engine.begin() as c:
        c.execute(processing.spaces.update().values(model="other-model"))
    with pytest.raises(DocumentError, match="STATE_CONFLICT"):
        run(case)
    assert case.s.provider.calls == case.calls == case.counts == []


def test_query_over_token_limit_is_never_truncated_or_embedded(case):
    with pytest.raises(DocumentError, match="INPUT_INVALID"):
        run(case, query="palabra " * 100)
    assert case.s.provider.calls == case.calls == []
    assert case.counts == ["query"]


@pytest.mark.parametrize("query", ["", " ", "x\0y", "x" * 8193])
def test_malformed_query_refused_without_inference(case, query):
    with pytest.raises(DocumentError, match="INPUT_INVALID"):
        run(case, query=query)
    assert case.s.provider.calls == case.calls == case.counts == []


@pytest.mark.parametrize("fault", ["provider-body", "dimension", "usage", "profile"])
def test_bad_provider_response_never_reaches_retrieval(case, fault):
    def corrupt(_texts):
        if fault == "provider-body":
            raise RuntimeError("PRIVATE_PROVIDER_BODY")
        valid = case.s.provider.base.embed(("consulta privada",), "query")
        if fault == "dimension":
            return EmbeddingBatch(valid.profile_fingerprint, ((1.0,),), valid.input_tokens)
        if fault == "usage":
            return EmbeddingBatch(valid.profile_fingerprint, valid.vectors, (1,))
        case.s.provider.profile = replace(case.s.provider.profile, model="other-model")
        return valid

    case.s.provider.callback = corrupt
    with pytest.raises(DocumentError) as error:
        run(case)
    assert "PRIVATE_PROVIDER_BODY" not in str(error.value) and case.calls == []


def test_forged_trace_refused_before_query_or_inference(case):
    case.trace = uuid4()
    with pytest.raises(AccessError, match="INPUT_INVALID"):
        run(case)
    assert case.calls == case.s.provider.calls == []
