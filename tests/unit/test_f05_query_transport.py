"""Real Unix IPC and offline SQL authorization, with an explicit fixture provider."""

import logging
import socket
from dataclasses import replace
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from test_f05_embedding_worker import setup  # noqa: F401

from rag_platform.control.identity_models import Membership
from rag_platform.documents.errors import DocumentError
from rag_platform.documents.repositories import RepositoryService
from rag_platform.embeddings import query_wire as wire
from rag_platform.embeddings.contracts import EmbeddingError
from rag_platform.embeddings.inference_gate import GatedProvider, InferenceGate
from rag_platform.embeddings.query_backend import QueryBackend
from rag_platform.embeddings.query_client import QueryClient
from rag_platform.embeddings.query_server import QueryServer


@pytest.fixture
def endpoint(setup, tmp_path):  # noqa: F811
    s = setup
    s.runtime.repositories.connections.authority = s.runtime.authority
    s.runtime.repositories = RepositoryService(
        s.runtime.repositories.connections, s.control, b"k" * 32, profile="embedding_publication"
    )
    gate = InferenceGate(lambda: True)
    provider = GatedProvider(s.provider, gate, index=False)
    backend = QueryBackend(s.runtime, provider, lambda: True)
    root = tmp_path / "rpc"
    root.mkdir(mode=0o700)
    path = root / "q.sock"
    server = QueryServer(path, backend)
    server.start()
    trace = uuid4()
    context = s.runtime.authority.authorize(s.actor, s.tenant, trace)
    space = UUID(hex=s.vector.name.removeprefix("embeddings_"))
    client = QueryClient(
        path, s.runtime.authority, context, trace, (s.repo,), space, profile=s.provider.profile
    )
    try:
        yield SimpleNamespace(
            s=s,
            gate=gate,
            backend=backend,
            server=server,
            client=client,
            path=path,
            context=context,
            space=space,
            trace=trace,
        )
    finally:
        gate.close()
        server.close()
    assert not path.exists()


def message(e, *, operation="embed"):
    return dict(
        v=1,
        operation=operation,
        context=wire.context_payload(e.context),
        repositories=[str(e.s.repo)],
        space=str(e.space),
        profile=e.s.provider.profile.fingerprint(),
        query="RPC_PRIVATE_MARKER",
    )


def raw(e, value):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.connect(str(e.path))
        wire.send(sock, value)
        return wire.receive(sock, seconds=5)


def test_real_unix_count_does_not_infer_and_embed_validates_usage(endpoint, caplog):
    e = endpoint
    caplog.set_level(logging.INFO, logger="rag_platform.embeddings")
    assert e.s.provider.profile.provider == "fixture"
    count = e.client.count_tokens("RPC_PRIVATE_MARKER", "query")
    assert e.s.provider.calls == []
    batch = e.client.embed(("RPC_PRIVATE_MARKER",), "query")
    assert batch.total_tokens == count and len(e.s.provider.calls) == 1
    assert e.s.provider.profile.fingerprint() == batch.profile_fingerprint
    assert "query_embedding" in caplog.text and str(e.trace) in caplog.text
    assert "RPC_PRIVATE_MARKER" not in caplog.text
    assert e.context._proof not in repr(e.client) + repr(e.backend) + repr(e.server)


@pytest.mark.parametrize("fault", ["proof", "tenant", "repo", "space", "profile", "extra", "kind"])
def test_invalid_or_unauthorized_rpc_cannot_infer(endpoint, fault):
    e, value = endpoint, message(endpoint)
    if fault == "proof":
        value["context"]["proof"] = "0" * 64
    elif fault == "tenant":
        value["context"]["tenant"] = str(uuid4())
    elif fault == "repo":
        value["repositories"].append(str(uuid4()))
    elif fault == "space":
        value["space"] = str(uuid4())
    elif fault == "profile":
        value["profile"] = "0" * 64
    elif fault == "extra":
        value["table"] = "knowledge.PRIVATE_MARKER"
    else:
        value["operation"] = "passage"
    response = raw(e, value)
    assert set(response) == {"v", "trace", "error"}
    assert e.s.provider.calls == []
    assert "PRIVATE_MARKER" not in str(response)


def test_acl_revoked_during_inference_returns_only_denial(endpoint):
    e = endpoint

    def revoke(_texts):
        with e.s.engine.begin() as c:
            c.execute(e.s.md.tables["security.repository_acl"].delete())

    e.s.provider.callback = revoke
    with pytest.raises(DocumentError, match="ROLE_DENIED"):
        e.client.embed(("RPC_PRIVATE_MARKER",), "query")
    assert len(e.s.provider.calls) == 1


def test_client_refreshes_context_between_rpc_calls(endpoint, monkeypatch):
    import rag_platform.tenancy.authorization as authorization

    e = endpoint
    now = authorization.time.time()
    original_count = e.s.provider.count_tokens

    def slow_count(text, kind):
        monkeypatch.setattr(authorization.time, "time", lambda: now + 40)
        return original_count(text, kind)

    monkeypatch.setattr(e.s.provider, "count_tokens", slow_count)
    e.client.count_tokens("RPC_PRIVATE_MARKER", "query")
    assert e.client.embed(("RPC_PRIVATE_MARKER",), "query").total_tokens > 0


def test_invalid_model_output_is_not_transmitted(endpoint):
    e = endpoint
    e.s.provider.callback = lambda _texts: {"PRIVATE_PROVIDER_BODY": 1}
    with pytest.raises(EmbeddingError):
        e.client.embed(("RPC_PRIVATE_MARKER",), "query")


def test_over_token_limit_never_runs_model(endpoint):
    e = endpoint
    with pytest.raises(EmbeddingError, match="INPUT_TOO_LONG"):
        e.client.count_tokens("word " * 100, "query")
    assert e.s.provider.calls == []


def test_profile_drift_during_count_stops_before_model(endpoint, monkeypatch):
    e = endpoint
    original = e.s.provider.count_tokens

    def drift(text, kind):
        e.backend.provider.profile = replace(e.backend.provider.profile, model="other-model")
        return original(text, kind)

    monkeypatch.setattr(e.s.provider, "count_tokens", drift)
    with pytest.raises(EmbeddingError, match="PROFILE_MISMATCH"):
        e.client.embed(("RPC_PRIVATE_MARKER",), "query")
    assert e.s.provider.calls == []


def test_missing_listener_fails_closed_after_shutdown(endpoint):
    e = endpoint
    e.server.close()
    with pytest.raises(EmbeddingError, match="DEPENDENCY_UNAVAILABLE"):
        e.client.count_tokens("RPC_PRIVATE_MARKER", "query")


def test_foreign_file_is_never_removed(endpoint):
    e = endpoint
    e.path.unlink()
    e.path.write_text("PRESERVE_THIS_FILE")
    e.server.close()
    assert e.path.read_text() == "PRESERVE_THIS_FILE"
    e.path.unlink()  # Only this test's own temporary marker, not production cleanup.


def test_active_listener_not_replaced(endpoint):
    e = endpoint
    with pytest.raises(EmbeddingError):
        QueryServer(e.path, e.backend)
    assert e.client.count_tokens("RPC_PRIVATE_MARKER", "query") > 0


def test_inactive_private_socket_can_be_replaced(tmp_path):
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    path = root / "q.sock"
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(str(path))
    path.chmod(0o600)
    sock.close()
    server = QueryServer(path, SimpleNamespace(response=lambda message: {"ok": True}))
    try:
        server.start()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.connect(str(path))
            wire.send(client, {"v": 1})
            assert wire.receive(client) == {"ok": True}
    finally:
        server.close()
    assert not path.exists()


def test_listener_limits_handlers_before_processing_third_request(tmp_path):
    from threading import Event, Lock

    root = tmp_path / "bounded"
    root.mkdir(mode=0o700)
    path = root / "q.sock"
    both, release, lock = Event(), Event(), Lock()
    counts = {"active": 0, "maximum": 0, "total": 0}

    class Backend:
        def response(self, _message):
            with lock:
                counts["active"] += 1
                counts["total"] += 1
                counts["maximum"] = max(counts["maximum"], counts["active"])
                if counts["active"] == 2:
                    both.set()
            try:
                assert release.wait(4)
                return {"ok": True}
            finally:
                with lock:
                    counts["active"] -= 1

    server = QueryServer(path, Backend())
    clients = []
    try:
        server.start()
        for _ in range(2):
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.settimeout(2)
            client.connect(str(path))
            wire.send(client, {"v": 1})
            clients.append(client)
        assert both.wait(2)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as third:
            third.settimeout(2)
            third.connect(str(path))
            with pytest.raises(EmbeddingError):
                # Rejection can arrive before send or while waiting for the reply.
                wire.send(third, {"v": 1})
                wire.receive(third)
        release.set()
        assert all(wire.receive(client) == {"ok": True} for client in clients)
        assert counts["maximum"] == counts["total"] == 2
    finally:
        release.set()
        for client in clients:
            client.close()
        server.close()


def test_query_directory_preparation_preserves_inode_and_refuses_symlink(tmp_path, monkeypatch):
    import importlib
    from pathlib import Path

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    host = importlib.import_module("f05_query_host")
    path = tmp_path / "query"
    host.prepare(path)
    before = path.stat().st_ino
    host.prepare(path)
    assert path.stat().st_ino == before
    assert host.status(path) == {"prepared": True, "socket_present": False}
    alias = tmp_path / "alias"
    alias.symlink_to(path, target_is_directory=True)
    with pytest.raises(EmbeddingError):
        host.prepare(alias)
    assert path.stat().st_ino == before


def test_revoked_membership_rejects_previously_signed_context_at_worker(endpoint):
    e = endpoint
    with e.s.control.begin() as c:
        c.execute(sa.update(Membership).values(state="REVOKED"))
    response = raw(e, message(e))
    assert response == {"v": 1, "trace": str(e.trace), "error": "ROLE_DENIED"}
    assert e.s.provider.calls == []
