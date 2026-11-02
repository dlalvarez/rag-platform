"""Development worker process; credentials stay in private mounted files."""

import logging
import os
import resource
import signal
from pathlib import Path
from threading import Event

from rag_platform.identity_api import private_file
from rag_platform.ingestion.queue import DurableQueue
from rag_platform.ingestion.runtime import Runtime
from rag_platform.ingestion.worker import Worker
from rag_platform.providers.secrets import Credential
from rag_platform.provisioning.postgres import Target
from rag_platform.tenancy.resolver import control_engine


def main():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    enabled = os.environ.get("RAG_F05_ENABLED", "0")
    publication = os.environ.get("RAG_F05_PUBLICATION_ENABLED", "0")
    if (
        enabled not in ("0", "1")
        or publication not in ("0", "1")
        or (publication == "1" and enabled != "1")
    ):
        raise ValueError("Invalid worker profile")
    profile = (
        "embedding_publication"
        if publication == "1"
        else ("embeddings" if enabled == "1" else "ingestion")
    )
    stop = Event()
    for value in (signal.SIGTERM, signal.SIGINT):
        signal.signal(value, lambda _number, _frame: stop.set())
    ca = Path("/run/f01-ca.crt")
    credential = Credential(
        "f02_identity_app", private_file("/run/secrets/identity_app_password", 4096).decode()
    )
    key = private_file("/run/secrets/api_authority_key", 32)
    if len(key) != 32:
        raise ValueError()
    engine = control_engine(Target("postgres", 5432, ca), credential)
    runtime = None
    try:
        runtime = Runtime(
            engine,
            key,
            Path("/run/f04-worker"),
            "https://openbao:8200",
            ca,
            Path("/app/ops/f03/application-scope.json"),
            profile=profile,
        )
        runtime.preflight()
        queue = DurableQueue(engine, lease_seconds=180, tenant_scope=runtime.scope)
        Worker(runtime, queue, stop=stop).run()
    finally:
        try:
            if runtime is not None:
                runtime.close()
        finally:
            engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # No provider SDK/SQL traceback or exception text enters the worker log.
    for name in ("httpx", "httpcore", "sqlalchemy", "urllib3"):
        logging.getLogger(name).setLevel(logging.CRITICAL)
    try:
        main()
    except (Exception, KeyboardInterrupt):
        logging.getLogger("rag_platform.ingestion").error(
            "ingestion_start code=DEPENDENCY_UNAVAILABLE"
        )
        raise SystemExit(1) from None
