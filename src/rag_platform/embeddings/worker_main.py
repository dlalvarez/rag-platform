"""Opt-in development embedding process. Qwen dependencies stay outside the API."""

import logging
import os
import resource
import signal
from pathlib import Path
from threading import Event

import sqlalchemy as sa

from rag_platform.embeddings.inference_gate import GatedProvider, InferenceGate
from rag_platform.embeddings.query_backend import QueryBackend
from rag_platform.embeddings.query_server import QueryServer
from rag_platform.embeddings.query_wire import private_parent
from rag_platform.embeddings.queue import EmbeddingQueue
from rag_platform.embeddings.queue_schema_f05_0007 import jobs
from rag_platform.embeddings.qwen import REVISION, LocalQwen
from rag_platform.embeddings.runtime import Runtime
from rag_platform.embeddings.worker import Worker
from rag_platform.identity_api import private_file
from rag_platform.providers.secrets import Credential
from rag_platform.provisioning.postgres import Target
from rag_platform.tenancy.resolver import control_engine


def main():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    if (
        os.environ.get("RAG_F05_ENABLED", "0") != "1"
        or os.environ.get("RAG_F05_PUBLICATION_ENABLED", "0") != "1"
    ):
        raise ValueError("Explicit embedding publication profile required")
    query_enabled = os.environ.get("RAG_F05_QUERY_ENABLED", "0")
    if query_enabled not in ("0", "1"):
        raise ValueError("Explicit private query opt-in required")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
    stop = Event()
    for value in (signal.SIGTERM, signal.SIGINT):
        signal.signal(value, lambda _number, _frame: stop.set())
    ca = Path("/run/f01-ca.crt")
    credential = Credential(
        "f02_identity_app", private_file("/run/secrets/identity_app_password", 4096).decode()
    )
    key = private_file("/run/secrets/api_authority_key", 32)
    if len(key) != 32:
        raise ValueError("Invalid private worker configuration")
    engine = control_engine(Target("postgres", 5432, ca), credential)
    runtime, query_server, gate = None, None, None
    try:
        runtime = Runtime(
            engine,
            key,
            Path("/run/f05-worker"),
            "https://openbao:8200",
            ca,
            Path("/app/ops/f03/application-scope.json"),
        )
        runtime.preflight()
        # Reject missing EMBED DDL before allocating the model's memory.
        with engine.connect() as c:
            c.execute(sa.select(jobs).limit(0))
        model = Path(
            os.environ.get("RAG_F05_MODEL_PATH", "/models/qwen3-embedding-0.6b/" + REVISION)
        )
        query_path = None
        if query_enabled == "1":
            query_path = private_parent(
                Path(os.environ.get("RAG_F05_QUERY_SOCKET", "/run/f05-query/qwen.sock"))
            )
        provider = LocalQwen.load(model)
        if query_path is not None:

            def ready():
                return not stop.is_set() and runtime.access_ready()

            gate = InferenceGate(ready)
            backend = QueryBackend(runtime, GatedProvider(provider, gate, index=False), ready)
            query_server = QueryServer(query_path, backend)
            query_server.start()
            provider = GatedProvider(provider, gate, index=True)
        queue = EmbeddingQueue(
            engine,
            lease_seconds=180,
            max_attempts=3,
            tenant_scope=runtime.scope,
            profile_fingerprint=provider.profile.fingerprint(),
        )
        Worker(runtime, queue, provider, stop=stop).run()
    finally:
        stop.set()
        try:
            if gate is not None:
                gate.close()
            if query_server is not None:
                query_server.close()
        finally:
            try:
                if runtime is not None:
                    runtime.close()
            finally:
                engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for name in (
        "httpx",
        "httpcore",
        "sqlalchemy",
        "urllib3",
        "torch",
        "transformers",
        "huggingface_hub",
        "tokenizers",
    ):
        logging.getLogger(name).setLevel(logging.CRITICAL)
    try:
        main()
    except (Exception, KeyboardInterrupt):
        logging.getLogger("rag_platform.embeddings").error(
            "embedding_start code=DEPENDENCY_UNAVAILABLE"
        )
        raise SystemExit(1) from None
