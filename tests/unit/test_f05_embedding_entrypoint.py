"""Startup rejects flags/schema before allocating the optional model."""

from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest

from rag_platform.embeddings import worker_main
from rag_platform.embeddings.qwen import qwen_profile


@pytest.mark.parametrize("foundation,publication", [("0", "0"), ("0", "1"), ("1", "yes")])
def test_invalid_flags_stop_before_secret_or_model_access(monkeypatch, foundation, publication):
    monkeypatch.setenv("RAG_F05_ENABLED", foundation)
    monkeypatch.setenv("RAG_F05_PUBLICATION_ENABLED", publication)
    monkeypatch.setattr(worker_main.resource, "setrlimit", lambda *_: None)
    monkeypatch.setattr(worker_main, "private_file", lambda *_: pytest.fail("secret read"))
    with pytest.raises(ValueError, match="Explicit embedding publication"):
        worker_main.main()


@pytest.mark.parametrize("schema_ready", [False, True])
def test_preflight_precedes_model_and_resources_always_close(monkeypatch, schema_ready):
    seen = []
    tenant = uuid4()
    monkeypatch.setenv("RAG_F05_ENABLED", "1")
    monkeypatch.setenv("RAG_F05_PUBLICATION_ENABLED", "1")
    monkeypatch.setattr(worker_main.resource, "setrlimit", lambda *_: None)
    monkeypatch.setattr(worker_main.signal, "signal", lambda *_: None)
    monkeypatch.setattr(worker_main, "private_file", lambda *_: b"k" * 32)
    monkeypatch.setattr(worker_main, "Target", lambda *_: None)

    class SchemaUnavailable(Exception):
        pass

    @contextmanager
    def connect():
        yield SimpleNamespace(execute=lambda *_: seen.append("queue-shape"))

    engine = SimpleNamespace(connect=connect, dispose=lambda: seen.append("engine-close"))
    monkeypatch.setattr(worker_main, "control_engine", lambda *_: engine)

    class Runtime:
        scope = (tenant,)

        def __init__(self, *_):
            seen.append("runtime")

        def preflight(self):
            seen.append("schema")
            if not schema_ready:
                raise SchemaUnavailable()

        def close(self):
            seen.append("runtime-close")

    monkeypatch.setattr(worker_main, "Runtime", Runtime)
    provider = SimpleNamespace(profile=qwen_profile())
    monkeypatch.setattr(worker_main.LocalQwen, "load", lambda *_: seen.append("model") or provider)
    monkeypatch.setattr(
        worker_main, "EmbeddingQueue", lambda *_args, **kwargs: SimpleNamespace(**kwargs)
    )

    def worker(_runtime, queue, actual_provider, **_):
        assert queue.profile_fingerprint == actual_provider.profile.fingerprint()
        return SimpleNamespace(run=lambda: seen.append("worker"))

    monkeypatch.setattr(worker_main, "Worker", worker)
    if schema_ready:
        worker_main.main()
        assert seen == [
            "runtime",
            "schema",
            "queue-shape",
            "model",
            "worker",
            "runtime-close",
            "engine-close",
        ]
    else:
        with pytest.raises(SchemaUnavailable):
            worker_main.main()
        assert seen == ["runtime", "schema", "runtime-close", "engine-close"]
