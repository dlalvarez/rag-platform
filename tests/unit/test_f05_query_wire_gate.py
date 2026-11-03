"""Offline framing/ownership and process-local model exclusion; no Qwen weights."""

import socket
import struct
from threading import Event, Thread
from uuid import uuid4

import pytest

from rag_platform.embeddings import query_wire as wire
from rag_platform.embeddings.contracts import EmbeddingError
from rag_platform.embeddings.inference_gate import InferenceGate
from rag_platform.tenancy.authorization import AuthorizedTenantContext
from rag_platform.tenancy.contracts import SecretRef


def context():
    return AuthorizedTenantContext(
        uuid4(),
        uuid4(),
        ("reader",),
        SecretRef(uuid4(), 1),
        SecretRef(uuid4(), 2),
        uuid4(),
        1234,
        "a" * 64,
    )


def test_context_roundtrip_is_not_public_configuration():
    original = context()
    assert wire.context_from_payload(wire.context_payload(original)) == original
    assert original._proof not in repr(original)


@pytest.mark.parametrize("fault", ["extra", "zero", "version", "proof", "roles", "expiry"])
def test_context_shape_rejects_untrusted_values(fault):
    value = wire.context_payload(context())
    if fault == "extra":
        value["endpoint"] = "PRIVATE_MARKER"
    elif fault == "zero":
        value["tenant"] = "0" * 32
    elif fault == "version":
        value["db"]["version"] = True
    elif fault == "proof":
        value["proof"] = "PRIVATE_MARKER"
    elif fault == "roles":
        value["roles"] = ["platform_operator"]
    else:
        value["expires"] = True
    with pytest.raises(EmbeddingError, match="INPUT_INVALID"):
        wire.context_from_payload(value)


def test_frame_roundtrip_preserves_max_query_unicode():
    left, right = socket.socketpair()
    try:
        payload = {"query": "🧪" * 8192}
        wire.send(left, payload)
        assert wire.receive(right) == payload
    finally:
        left.close()
        right.close()


@pytest.mark.parametrize(
    "data",
    [
        b'{"x":1,"x":2}',
        b'{"x":NaN}',
        b"[]",
        b'{"x":"\\ud800"}'.replace(b"ud800", b"xZZZZ"),
        b"x",
        b'{"x":Infinity}',
    ],
)
def test_frame_rejects_malformed_json_without_echo(data):
    left, right = socket.socketpair()
    try:
        left.sendall(struct.pack("!I", len(data)) + data)
        with pytest.raises(EmbeddingError, match="DEPENDENCY_UNAVAILABLE") as error:
            wire.receive(right)
        assert "PRIVATE_MARKER" not in str(error.value)
    finally:
        left.close()
        right.close()


@pytest.mark.parametrize("length", [0, wire.MAX_FRAME + 1, 2**32 - 1])
def test_frame_length_rejected_before_reading_body(length):
    left, right = socket.socketpair()
    try:
        left.sendall(struct.pack("!I", length))
        with pytest.raises(EmbeddingError):
            wire.receive(right)
    finally:
        left.close()
        right.close()


def test_frame_partial_body_and_read_deadline_fail_closed():
    left, right = socket.socketpair()
    try:
        left.sendall(struct.pack("!I", 50) + b"{")
        with pytest.raises(EmbeddingError):
            wire.receive(right, seconds=0.03)
        left.close()
        with pytest.raises(EmbeddingError):
            wire.receive(right)
    finally:
        left.close()
        right.close()


def test_frame_oversize_and_nan_responses_never_sent():
    left, right = socket.socketpair()
    try:
        for payload in ({"x": "x" * wire.MAX_FRAME}, {"x": float("nan")}):
            with pytest.raises(EmbeddingError):
                wire.send(left, payload)
    finally:
        left.close()
        right.close()


def test_private_parent_refuses_shared_or_symlink_directory(tmp_path):
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    assert wire.private_parent(private / "q.sock") == private / "q.sock"
    private.chmod(0o755)
    with pytest.raises(EmbeddingError):
        wire.private_parent(private / "q.sock")
    private.chmod(0o700)
    link = tmp_path / "link"
    link.symlink_to(private, target_is_directory=True)
    with pytest.raises(EmbeddingError):
        wire.private_parent(link / "q.sock")


def test_gate_busy_release_and_closed_state():
    gate = InferenceGate(lambda: True, query_wait=0.03)
    errors = []
    with gate.enter(index=True):

        def occupied():
            try:
                with gate.enter():
                    errors.append("UNEXPECTED")
            except EmbeddingError as error:
                errors.append(error.code)

        thread = Thread(target=occupied)
        thread.start()
        thread.join(2)
        assert not thread.is_alive() and errors == ["LIMIT_EXCEEDED"]
    with gate.enter():
        pass
    gate.close()
    with pytest.raises(EmbeddingError, match="DEPENDENCY_UNAVAILABLE"):
        with gate.enter():
            pass


def test_gate_shutdown_wakes_index_waiter():
    gate, started, errors = InferenceGate(lambda: True), Event(), []
    with gate.enter():

        def waiting():
            started.set()
            try:
                with gate.enter(index=True):
                    errors.append("UNEXPECTED")
            except EmbeddingError as error:
                errors.append(error.code)

        thread = Thread(target=waiting)
        thread.start()
        assert started.wait(2)
        gate.close()
        thread.join(2)
        assert not thread.is_alive() and errors == ["DEPENDENCY_UNAVAILABLE"]


def test_gate_denies_expired_access_before_operation():
    gate = InferenceGate(lambda: False)
    with pytest.raises(EmbeddingError, match="DEPENDENCY_UNAVAILABLE"):
        with gate.enter(index=True):
            raise AssertionError("UNEXPECTED_OPERATION")


@pytest.mark.parametrize("operation", ["connect", "connect_ex"])
def test_suite_still_denies_ip_connections(operation):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        with pytest.raises(AssertionError, match="External networking"):
            getattr(sock, operation)(("127.0.0.1", 9))


def test_suite_denies_unix_sockets_outside_test_directory():
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        with pytest.raises(AssertionError, match="External networking"):
            sock.connect("/run/not-a-test.sock")


def test_index_waiter_precedes_another_query():
    gate, entered, release, order = InferenceGate(lambda: True), Event(), Event(), []

    def index():
        with gate.enter(index=True):
            order.append("index")
            entered.set()
            assert release.wait(3)

    def query():
        with gate.enter():
            order.append("query")

    with gate.enter():
        worker = Thread(target=index)
        worker.start()
        with gate.condition:
            assert gate.condition.wait_for(lambda: gate.pending_index == 1, timeout=2)
        caller = Thread(target=query)
        caller.start()
    assert entered.wait(2)
    release.set()
    worker.join(3)
    caller.join(3)
    assert not worker.is_alive() and not caller.is_alive()
    assert order == ["index", "query"]
