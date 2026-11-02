"""Opt-in real Qwen/SQL query proof. No HTTP endpoint, jobs or corpus mutation."""

import logging
import math
import os
import re
from pathlib import Path
from uuid import UUID, uuid4

import sqlalchemy as sa

from rag_platform.documents.errors import DocumentError
from rag_platform.embeddings import processing
from rag_platform.embeddings.qwen import REVISION, LocalQwen, qwen_profile
from rag_platform.embeddings.runtime import Runtime
from rag_platform.embeddings.search import SearchService
from rag_platform.identity_api import private_file
from rag_platform.providers.secrets import Credential
from rag_platform.provisioning.postgres import Target
from rag_platform.tenancy.resolver import control_engine

PHASE = "START"


def selection():
    import json

    manifest = json.loads(private_file("/run/f04-qa/manifest.json", 512 * 1024))
    proof = json.loads(private_file("/run/f05-proof/selection.json", 512 * 1024))
    scope = json.loads(Path("/app/ops/f03/application-scope.json").read_text())["fixtures"]
    assert proof["profile"] == qwen_profile().fingerprint()
    records = proof["records"]
    assert len(records) == 4
    assert [(r["name"], r["tenant"]) for r in records] == [(r["name"], r["tenant"]) for r in scope]
    assert len({r["document"] for r in records}) == 4
    for record, fixture in zip(records, manifest["fixtures"], strict=True):
        assert (record["name"], record["tenant"], record["repository"]) == (
            fixture["name"],
            fixture["tenant"],
            fixture["repository"],
        )
        original = [r for r in fixture["documents"] if r["case"] == "atomic"]
        assert len(original) == 1 and original[0]["document"] == record["document"]
        for key in ("tenant", "repository", "document", "version", "space"):
            assert UUID(record[key]).int != 0
    actor = UUID(manifest["actors"]["alice"])
    assert actor.int != 0
    return actor, records


class CountingProvider:
    def __init__(self, provider):
        self.base, self.profile, self.calls = provider, provider.profile, 0

    def count_tokens(self, text, kind):
        return self.base.count_tokens(text, kind)

    def embed(self, texts, kind):
        self.calls += 1
        return self.base.embed(texts, kind)


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
    runtime = None
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
        provider = CountingProvider(LocalQwen.load(Path("/models/qwen3-embedding-0.6b") / REVISION))
        service = SearchService(runtime.repositories, provider)
        for index, record in enumerate(records):
            PHASE = record["name"]
            trace = uuid4()
            context = runtime.authority.authorize(actor, UUID(record["tenant"]), trace)
            repository, space = UUID(record["repository"]), UUID(record["space"])
            before = provider.calls
            foreign = UUID(records[(index + 1) % 4]["repository"])
            assert foreign != repository
            try:
                service.search(context, trace, (repository, foreign), space, "prueba", 3)
            except DocumentError as error:
                assert error.code == "ROLE_DENIED"
            else:
                raise RuntimeError("FOREIGN_REPOSITORY_ACCEPTED")
            assert provider.calls == before

            context = runtime.authority.authorize(actor, UUID(record["tenant"]), trace)
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
            result = service.search(context, trace, (repository,), space, "documento de prueba", 3)
            assert provider.calls == before + 1
            assert result.embedding_requests == 1 and result.embedding_input_tokens > 0
            assert 1 <= len(result.hits) <= 3
            assert all(
                hit.repository_id == repository
                and (hit.document_id, hit.version_id, hit.chunk_id) in published
                and math.isfinite(hit.score)
                and -1 <= hit.score <= 1
                for hit in result.hits
            )
            print(
                "PASS F05 SEARCH " + PHASE + ": Qwen/SQL/provenance/foreign ACL; no content.",
                flush=True,
            )
        print("PASS F05 SEARCH: four fixtures/two instances; HTTP/ANN/quality not assessed.")
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
        print("F05 SEARCH " + PHASE + " " + code + "; resources retained.")
        raise SystemExit(1) from None
