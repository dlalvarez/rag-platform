"""Real authorized HybridService/Qwen/citation probe on retained synthetic originals."""

import logging
import os
import re
from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid4

from f05_adopt import save
from f05_search_check import CountingProvider, selection

from rag_platform.documents.errors import DocumentError
from rag_platform.embeddings.qwen import REVISION, LocalQwen
from rag_platform.embeddings.runtime import Runtime
from rag_platform.embeddings.search import SearchService
from rag_platform.identity_api import private_file
from rag_platform.providers.secrets import Credential
from rag_platform.provisioning.postgres import Target
from rag_platform.retrieval.contracts import RRF_REVISION, CitationRef, QueryFilters
from rag_platform.retrieval.service import HybridService
from rag_platform.tenancy.resolver import control_engine

PHASE = "START"


def denied(operation, code, *arguments):
    try:
        operation(*arguments)
    except DocumentError as error:
        assert error.code == code
    else:
        raise AssertionError("DENIAL_REQUIRED")


def run():
    global PHASE
    actor, records = selection()
    ca = Path("/run/f01-ca.crt")
    engine = control_engine(
        Target("postgres", 5432, ca),
        Credential(
            "f02_identity_app", private_file("/run/secrets/identity_app_password", 4096).decode()
        ),
    )
    runtime, results = None, []
    try:
        runtime = Runtime(
            engine,
            private_file("/run/secrets/api_authority_key", 32),
            Path("/run/f05-worker"),
            "https://openbao:8200",
            ca,
            Path("/app/ops/f03/application-scope.json"),
        )
        runtime.preflight()
        assert tuple(UUID(r["tenant"]) for r in records) == runtime.scope
        PHASE = "MODEL"
        provider = CountingProvider(LocalQwen.load(Path("/models/qwen3-embedding-0.6b") / REVISION))
        service = HybridService(runtime.repositories, provider)
        for index, record in enumerate(records):
            PHASE = record["name"]
            trace = uuid4()
            tenant, repository, space, document, version = (
                UUID(record[key])
                for key in ("tenant", "repository", "space", "document", "version")
            )
            context = runtime.authority.authorize(actor, tenant, trace)
            foreign = UUID(records[(index + 1) % 4]["repository"])
            assert foreign != repository
            before = provider.calls
            denied(
                service.search,
                "ROLE_DENIED",
                context,
                trace,
                (repository, foreign),
                space,
                "prueba",
                3,
            )
            assert provider.calls == before
            context = runtime.authority.authorize(actor, tenant, trace)
            result = service.search(
                context,
                trace,
                (repository,),
                space,
                "documento de prueba",
                3,
                QueryFilters(document_ids=(document,), version_ids=(version,)),
            )
            assert provider.calls == before + 1
            assert result.ranking_revision == RRF_REVISION
            assert result.embedding_requests == 1 and result.embedding_input_tokens > 0
            assert 1 <= len(result.hits) <= 3
            context = runtime.authority.authorize(actor, tenant, trace)
            for hit in result.hits:
                ref = hit.evidence.reference
                assert (
                    ref.tenant_id,
                    ref.space_id,
                    ref.repository_id,
                    ref.document_id,
                    ref.version_id,
                ) == (tenant, space, repository, document, version)
                assert service.resolve_citation(context, trace, ref) == hit.evidence
                denied(
                    service.resolve_citation,
                    "ROLE_DENIED",
                    context,
                    trace,
                    replace(ref, tenant_id=UUID(records[(index + 1) % 4]["tenant"])),
                )
                denied(
                    service.resolve_citation,
                    "NOT_FOUND",
                    context,
                    trace,
                    replace(ref, chunk_id=uuid4()),
                )
            assert provider.calls == before + 1  # No inference for citation resolution/denials.
            context = runtime.authority.authorize(actor, tenant, trace)
            exact_result = SearchService(runtime.repositories, provider).search(
                context, trace, (repository,), space, "documento de prueba", 3
            )
            assert provider.calls == before + 2 and 1 <= len(exact_result.hits) <= 3
            context = runtime.authority.authorize(actor, tenant, trace)
            for exact_hit in exact_result.hits:
                assert exact_hit.repository_id == repository
                ref = CitationRef(
                    tenant,
                    space,
                    repository,
                    exact_hit.document_id,
                    exact_hit.version_id,
                    exact_hit.chunk_id,
                )
                resolved = service.resolve_citation(context, trace, ref)
                assert resolved.reference == ref and resolved.excerpt == exact_hit.excerpt
            results.append(
                dict(
                    name=record["name"],
                    hits=len(result.hits),
                    valid_citations=len(result.hits),
                    embedding_requests=result.embedding_requests + exact_result.embedding_requests,
                    exact_regression_hits=len(exact_result.hits),
                    embedding_input_tokens=(
                        result.embedding_input_tokens + exact_result.embedding_input_tokens
                    ),
                    denied_before_inference=True,
                )
            )
            print(
                "PASS F06 SERVICE " + PHASE + ": Qwen/hybrid/identity/ACL/citations; no content.",
                flush=True,
            )
        assert len(results) == 4 and provider.calls == 8
        save(
            "verified.json",
            dict(
                fixtures=results,
                real_provider_requests=provider.calls,
                real_provider_input_tokens=sum(r["embedding_input_tokens"] for r in results),
                scope="retained published synthetic originals; no corpus mutation",
            ),
        )
        print(
            "PASS F06 SERVICE: four tenants/two instances; "
            "current citations and zero denied inference."
        )
    finally:
        if runtime is not None:
            runtime.close()
        engine.dispose()


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    try:
        run()
    except Exception as error:
        state = getattr(getattr(error, "orig", error), "sqlstate", None)
        code = state if isinstance(state, str) and re.fullmatch("[A-Z0-9]{5}", state) else "REFUSED"
        print("F06 SERVICE " + PHASE + " " + code + "; resources retained.")
        raise SystemExit(1) from None
