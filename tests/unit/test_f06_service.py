"""Real offline authority/ACL with controlled SQL adapter; no model or network."""

from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

import pytest
import sqlalchemy as sa
from test_f05_embedding_worker import setup  # noqa: F401
from test_f05_search_service import case as base_case  # noqa: F401

from rag_platform.control.identity import AccessError
from rag_platform.control.identity_models import Membership, TenantProfile
from rag_platform.documents.errors import DocumentError
from rag_platform.embeddings import processing
from rag_platform.retrieval import service
from rag_platform.retrieval.contracts import CitationRef, Evidence, QueryFilters, RetrievalError
from rag_platform.retrieval.fusion import fuse


@pytest.fixture
def case(base_case, monkeypatch):  # noqa: F811
    base = base_case
    instance = service.HybridService(base.service.repositories, base.s.provider)
    reference = CitationRef(
        base.s.tenant, base.space, base.s.repo, base.s.doc, base.s.version, base.hit.chunk_id
    )
    evidence = Evidence(reference, "PRIVATE_RESULT", 0, 14, None, ("Title",))
    calls, resolutions = [], []

    def hybrid(c, tenant, actor, repos, space, profile, vector, query, top_k, filters):
        assert c.in_transaction() and tenant == base.s.tenant and actor == base.s.actor
        assert repos == (base.s.repo,) and isinstance(filters, QueryFilters)
        calls.append((space, top_k))
        return fuse((evidence,), (evidence,), top_k)

    def resolve(c, tenant, actor, ref, profile):
        assert c.in_transaction() and tenant == base.s.tenant and actor == base.s.actor
        resolutions.append(ref)
        return evidence

    monkeypatch.setattr(service, "hybrid", hybrid)
    monkeypatch.setattr(service, "resolve", resolve)
    return SimpleNamespace(
        base=base,
        service=instance,
        calls=calls,
        resolutions=resolutions,
        reference=reference,
        evidence=evidence,
    )


def run(case, repositories=None, **kwargs):
    base = case.base
    return case.service.search(
        base.context,
        base.trace,
        (base.s.repo,) if repositories is None else repositories,
        base.space,
        kwargs.pop("query", "consulta privada"),
        3,
        **kwargs,
    )


def resolve(case, reference=None):
    base = case.base
    return case.service.resolve_citation(
        base.context, base.trace, case.reference if reference is None else reference
    )


def test_hybrid_releases_connections_during_inference_and_preserves_usage(case):
    def inference(_texts):
        assert case.base.s.control.pool.checkedout() == case.base.s.engine.pool.checkedout() == 0

    case.base.s.provider.callback = inference
    result = run(case, filters=QueryFilters(document_ids=(case.base.s.doc,)))
    assert result.hits[0].evidence == case.evidence
    assert result.hits[0].vector_rank == result.hits[0].lexical_rank == 1
    assert result.embedding_requests == 1 and result.embedding_input_tokens > 0
    assert len(case.calls) == len(case.base.s.provider.calls) == 1
    assert "PRIVATE" not in repr(result)


def test_every_repository_authorized_before_tokenization(case):
    with pytest.raises(DocumentError, match="ROLE_DENIED"):
        run(case, repositories=(case.base.s.repo, uuid4()))
    assert case.base.counts == case.calls == case.base.s.provider.calls == []


def test_invalid_filters_rejected_before_provider(case):
    with pytest.raises(DocumentError, match="INPUT_INVALID"):
        run(case, filters={"document_ids": ["PRIVATE"]})
    assert case.base.counts == case.calls == []


@pytest.mark.parametrize("change", ["acl", "membership", "tenant", "space"])
def test_revocation_during_inference_prevents_hybrid_evidence(case, change):
    s = case.base.s

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


def test_expired_context_is_freshly_authorized_after_inference(case, monkeypatch):
    import rag_platform.tenancy.authorization as authorization

    now = authorization.time.time()
    monkeypatch.setattr(authorization.time, "time", lambda: now)
    case.base.s.provider.callback = lambda _texts: monkeypatch.setattr(
        authorization.time, "time", lambda: now + 40
    )
    assert run(case).hits[0].evidence == case.evidence
    with pytest.raises(AccessError):
        case.base.s.runtime.authority.validate(case.base.context, case.base.trace)


def test_excess_tokens_never_truncated_or_embedded(case):
    with pytest.raises(DocumentError, match="INPUT_INVALID"):
        run(case, query="palabra " * 100)
    assert case.calls == case.base.s.provider.calls == []


def test_citation_requires_no_inference_and_returns_offsets(case):
    value = resolve(case)
    assert value == case.evidence and value.start_offset == 0 and value.end_offset == 14
    assert case.resolutions == [case.reference]
    assert case.base.counts == case.base.s.provider.calls == []


def test_reference_from_another_tenant_denied_before_tenant_sql(case):
    with pytest.raises(DocumentError, match="ROLE_DENIED"):
        resolve(case, replace(case.reference, tenant_id=uuid4()))
    assert case.resolutions == case.base.counts == []


def test_reference_without_repo_acl_denied_before_resolution(case):
    with pytest.raises(DocumentError, match="ROLE_DENIED"):
        resolve(case, replace(case.reference, repository_id=uuid4()))
    assert case.resolutions == []


def test_old_reference_does_not_grant_access_after_acl_revocation(case):
    assert resolve(case) == case.evidence
    with case.base.s.engine.begin() as c:
        c.execute(case.base.s.md.tables["security.repository_acl"].delete())
    with pytest.raises(DocumentError, match="ROLE_DENIED"):
        resolve(case)
    assert len(case.resolutions) == 1


def test_citation_profile_mismatch_is_closed_before_resolution(case):
    with case.base.s.engine.begin() as c:
        c.execute(processing.spaces.update().values(model="other-model"))
    with pytest.raises(DocumentError, match="STATE_CONFLICT"):
        resolve(case)
    assert case.resolutions == []


@pytest.mark.parametrize("code", ["NOT_FOUND", "DEPENDENCY_UNAVAILABLE"])
def test_citation_missing_or_dependency_error_has_closed_vocabulary(case, monkeypatch, code):
    def failed(*_args):
        raise RetrievalError(code)

    monkeypatch.setattr(service, "resolve", failed)
    with pytest.raises(DocumentError, match="^" + code + "$"):
        resolve(case)


def test_forged_trace_cannot_search_or_resolve(case):
    case.base.trace = uuid4()
    with pytest.raises(AccessError):
        run(case)
    with pytest.raises(AccessError):
        resolve(case)
    assert case.resolutions == case.calls == case.base.s.provider.calls == []


def test_raw_backend_failure_does_not_leak_document_or_sql(case, monkeypatch):
    def failed(*_args):
        raise RuntimeError("PRIVATE_BACKEND")

    monkeypatch.setattr(service, "resolve", failed)
    with pytest.raises(DocumentError, match="^DEPENDENCY_UNAVAILABLE$"):
        resolve(case)
