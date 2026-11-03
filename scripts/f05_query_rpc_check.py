"""Opt-in real Qwen over private IPC from a Torch-free application image."""

import importlib.util
import logging
import os
import re
from pathlib import Path
from uuid import UUID, uuid4

import sqlalchemy as sa
from f05_adopt import save
from f05_search_check import selection

from rag_platform.documents.errors import DocumentError
from rag_platform.embeddings import processing
from rag_platform.embeddings.contracts import EmbeddingError
from rag_platform.embeddings.query_client import QueryClient
from rag_platform.embeddings.search import SearchService
from rag_platform.identity_api import private_file
from rag_platform.ingestion.runtime import Runtime
from rag_platform.providers.application_handoff import directory
from rag_platform.providers.secrets import Credential
from rag_platform.provisioning.postgres import Target
from rag_platform.tenancy.resolver import control_engine

PHASE = "START"
SOCKET = Path("/run/f05-query/qwen.sock")


def run():
    global PHASE
    assert importlib.util.find_spec("torch") is None
    output = directory(Path("/run/f05-qa"))
    os.close(output)
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
            Path("/run/f04-worker"),
            "https://openbao:8200",
            ca,
            Path("/app/ops/f03/application-scope.json"),
            profile="embedding_publication",
        )
        runtime.preflight()
        for index, record in enumerate(records):
            PHASE = record["name"]
            tenant, repository, space = (
                UUID(record[key]) for key in ("tenant", "repository", "space")
            )
            denied_trace = uuid4()
            denied_context = runtime.authority.authorize(actor, tenant, denied_trace)
            foreign = UUID(records[(index + 1) % 4]["repository"])
            assert foreign != repository
            # Direct provider call exercises the worker policy, without the API precheck.
            denied_client = QueryClient(
                SOCKET,
                runtime.authority,
                denied_context,
                denied_trace,
                (repository, foreign),
                space,
            )
            try:
                denied_client.embed(("prueba de aislamiento",), "query")
            except DocumentError as error:
                assert error.code == "ROLE_DENIED"
            else:
                raise RuntimeError("FOREIGN_REPOSITORY_ACCEPTED")
            trace = uuid4()
            context = runtime.authority.authorize(actor, tenant, trace)
            client = QueryClient(SOCKET, runtime.authority, context, trace, (repository,), space)
            runtime.repositories.require(context, trace, repository, "read")
            with runtime.repositories.connections.connection(context, trace) as c:
                published = set(
                    c.execute(
                        sa.select(
                            processing.chunks.c.document_id,
                            processing.chunks.c.version_id,
                            processing.chunks.c.id,
                        )
                        .join(
                            processing.publications,
                            processing.publications.c.version_id == processing.chunks.c.version_id,
                        )
                        .where(
                            processing.publications.c.space_id == space,
                            processing.publications.c.repository_id == repository,
                        )
                    ).all()
                )
            assert any(
                doc == UUID(record["document"]) and version == UUID(record["version"])
                for doc, version, _chunk in published
            )
            result = SearchService(runtime.repositories, client).search(
                context, trace, (repository,), space, "documento de prueba", 3
            )
            assert 1 <= len(result.hits) <= 3
            assert all(
                hit.repository_id == repository
                and (hit.document_id, hit.version_id, hit.chunk_id) in published
                for hit in result.hits
            )
            assert result.embedding_requests == 1 and result.embedding_input_tokens > 0
            results.append(
                dict(
                    name=record["name"],
                    success_trace=str(trace),
                    denied_trace=str(denied_trace),
                    hits=len(result.hits),
                    embedding_requests=result.embedding_requests,
                    embedding_input_tokens=result.embedding_input_tokens,
                )
            )
            print(
                "PASS F05 RPC " + PHASE + ": remote Qwen/SQL/provenance/worker ACL; no content.",
                flush=True,
            )
        save("verified.json", {"fixtures": results})
        print("PASS F05 RPC: four fixtures/two instances, Torch absent in application image.")
    finally:
        if runtime is not None:
            runtime.close()
        engine.dispose()


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    try:
        run()
    except (DocumentError, EmbeddingError) as error:
        print("F05 RPC " + PHASE + " " + error.code + "; resources retained.")
        raise SystemExit(1) from None
    except Exception as error:
        state = getattr(getattr(error, "orig", error), "sqlstate", None)
        code = state if isinstance(state, str) and re.fullmatch("[A-Z0-9]{5}", state) else "REFUSED"
        print("F05 RPC " + PHASE + " " + code + "; resources retained.")
        raise SystemExit(1) from None
