"""Opt-in lifecycle keeps one model and closes IPC before revoking its runtime."""

from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest

from rag_platform.embeddings import worker_main
from rag_platform.embeddings.fixture import fixture_profile
from rag_platform.embeddings.inference_gate import GatedProvider


@pytest.fixture
def entry(tmp_path, monkeypatch):
    events = []
    model = SimpleNamespace(profile=fixture_profile())
    runtime = SimpleNamespace(
        scope=(uuid4(),),
        preflight=lambda: events.append("preflight"),
        access_ready=lambda: True,
        close=lambda: events.append("runtime-close"),
    )

    @contextmanager
    def connection():
        yield SimpleNamespace(execute=lambda *_args: events.append("ddl-check"))

    engine = SimpleNamespace(connect=connection, dispose=lambda: events.append("engine-close"))
    root = tmp_path / "ipc"
    root.mkdir(mode=0o700)
    for name, value in (
        ("RAG_F05_ENABLED", "1"),
        ("RAG_F05_PUBLICATION_ENABLED", "1"),
        ("RAG_F05_QUERY_ENABLED", "0"),
        ("RAG_F05_QUERY_SOCKET", str(root / "q.sock")),
        ("HF_HUB_OFFLINE", "before"),
        ("TRANSFORMERS_OFFLINE", "before"),
        ("TOKENIZERS_PARALLELISM", "before"),
        ("HF_HUB_DISABLE_PROGRESS_BARS", "before"),
    ):
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(worker_main.resource, "setrlimit", lambda *_args: None)
    monkeypatch.setattr(worker_main.signal, "signal", lambda *_args: None)
    monkeypatch.setattr(
        worker_main, "private_file", lambda _path, n: b"k" * 32 if n == 32 else b"fake"
    )
    monkeypatch.setattr(worker_main, "control_engine", lambda *_args: engine)
    monkeypatch.setattr(worker_main, "Runtime", lambda *_args: runtime)

    def load(_path):
        events.append("model-load")
        return model

    monkeypatch.setattr(worker_main.LocalQwen, "load", load)
    monkeypatch.setattr(worker_main, "EmbeddingQueue", lambda *_args, **_kwargs: object())
    servers, workers = [], []

    def backend(_runtime, provider, ready):
        assert provider.base is model and not provider.index
        return SimpleNamespace(ready=ready)

    monkeypatch.setattr(worker_main, "QueryBackend", backend)

    class Server:
        def __init__(self, path, backend):
            self.backend = backend
            servers.append(self)

        def start(self):
            events.append("server-start")

        def close(self):
            assert not self.backend.ready()
            events.append("server-close")

    monkeypatch.setattr(worker_main, "QueryServer", Server)

    class Worker:
        def __init__(self, _runtime, _queue, provider, **_kwargs):
            workers.append(provider)

        def run(self):
            events.append("worker-run")

    monkeypatch.setattr(worker_main, "Worker", Worker)
    return SimpleNamespace(events=events, model=model, workers=workers, servers=servers)


def test_existing_mode_does_not_create_query_listener(entry):
    worker_main.main()
    assert entry.servers == [] and entry.workers == [entry.model]
    assert entry.events == [
        "preflight",
        "ddl-check",
        "model-load",
        "worker-run",
        "runtime-close",
        "engine-close",
    ]


def test_query_optin_loads_once_and_closes_before_runtime(entry, monkeypatch):
    monkeypatch.setenv("RAG_F05_QUERY_ENABLED", "1")
    worker_main.main()
    assert entry.events.count("model-load") == 1
    assert isinstance(entry.workers[0], GatedProvider) and entry.workers[0].index
    assert entry.workers[0].base is entry.model
    assert entry.events.index("server-start") < entry.events.index("worker-run")
    assert entry.events.index("server-close") < entry.events.index("runtime-close")


def test_bad_optin_refused_before_private_configuration(entry, monkeypatch):
    monkeypatch.setenv("RAG_F05_QUERY_ENABLED", "unexpected")
    with pytest.raises(ValueError):
        worker_main.main()
    assert entry.events == []
