"""Worker failure boundaries and fixed resource/scope constraints, offline."""

import json
from contextlib import contextmanager
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from uuid import uuid4

import pytest
import sqlalchemy as sa

from rag_platform.control.identity import AccessError
from rag_platform.ingestion import processing
from rag_platform.ingestion.extraction import ExtractionError
from rag_platform.ingestion.queue import DurableQueue
from rag_platform.ingestion.queue_schema import jobs
from rag_platform.ingestion.runtime import scope
from rag_platform.ingestion.worker import Worker
from rag_platform.tenancy.registry import tenant_engine

MANIFEST = Path(__file__).resolve().parents[2] / "ops/f03/application-scope.json"


@pytest.fixture
def fixture():
    e = sa.create_engine("sqlite://")
    jobs.create(e)
    tenant, actor = uuid4(), uuid4()
    q = DurableQueue(e, tenant_scope=(tenant,), lease_seconds=180)
    q.enqueue(tenant, actor, uuid4(), uuid4(), uuid4())
    calls = []

    def denied(*_):
        calls.append("content")
        raise AssertionError("Unexpected content access")

    authority = SimpleNamespace(profile="ingestion", engine=e)
    runtime = SimpleNamespace(
        authority=authority,
        scope=(tenant,),
        documents=SimpleNamespace(original=denied),
    )
    yield q, runtime, calls
    e.dispose()


def state(q):
    with q.engine.connect() as c:
        return c.execute(sa.select(jobs)).mappings().one()


def test_scope_is_fixed_explicit_and_nonduplicated(tmp_path):
    assert len(scope(MANIFEST)) == 4
    value = json.loads(MANIFEST.read_text())
    value["fixtures"][1]["tenant"] = value["fixtures"][0]["tenant"]
    p = tmp_path / "scope.json"
    p.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="Invalid fixed development scope"):
        scope(p)


@pytest.mark.parametrize(
    "change",
    [
        {"version": True},
        {"version": 2},
        {"fixtures": []},
        {"private": "untrusted"},
    ],
)
def test_scope_malformed_rejected_closed(tmp_path, change):
    value = json.loads(MANIFEST.read_text()) | change
    p = tmp_path / "scope.json"
    p.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="Invalid fixed development scope"):
        scope(p)


@pytest.mark.parametrize("value", [0, 3, True, "1"])
def test_pool_expansion_rejected_before_connection(value):
    with pytest.raises(ValueError, match="Invalid tenant pool size"):
        tenant_engine(None, None, None, pool_size=value)


def test_worker_pool_has_one_socket_and_no_overflow():
    e = tenant_engine(None, None, None, pool_size=1)
    try:
        assert e.pool.size() == 1 and e.pool._max_overflow == 0
    finally:
        e.dispose()


def test_worker_rejects_broader_scope(fixture):
    q, runtime, _calls = fixture
    runtime.scope = (uuid4(),)
    with pytest.raises(ValueError, match="Explicit ingestion runtime"):
        Worker(runtime, q)


def test_stop_prevents_claim_and_io(fixture):
    q, runtime, calls = fixture
    stopped = Event()
    stopped.set()
    worker = Worker(runtime, q, stop=stopped)
    assert worker.step() is False
    assert state(q)["status"] == "PENDING" and state(q)["attempts"] == 0
    assert calls == []


@pytest.mark.parametrize(
    "code,status,error",
    [
        ("MEMBERSHIP_REQUIRED", "FAILED", "AUTHORIZATION_CHANGED"),
        ("IDENTITY_SUSPENDED", "FAILED", "AUTHORIZATION_CHANGED"),
        ("CATALOG_UNAVAILABLE", "RETRY", "DEPENDENCY_UNAVAILABLE"),
        ("TENANT_UNAVAILABLE", "RETRY", "DEPENDENCY_UNAVAILABLE"),
    ],
)
def test_denied_or_unavailable_authority_never_reads_content(
    fixture, monkeypatch, code, status, error
):
    q, runtime, calls = fixture

    def authorize(*_):
        raise AccessError(code)

    runtime.authority.authorize = authorize
    worker = Worker(runtime, q)
    monkeypatch.setattr(worker, "_reconcile", lambda _: False)
    assert worker.step()
    assert (state(q)["status"], state(q)["error_code"]) == (status, error)
    assert calls == []


def test_committed_result_ack_uses_only_outcome_metadata(fixture, monkeypatch):
    q, runtime, calls = fixture

    @contextmanager
    def connection(*_):
        calls.append("outcome")
        yield None

    def no_authorize(*_):
        raise AssertionError("No new content execution")

    runtime.registry = SimpleNamespace(connection=connection)
    runtime.authority.authorize = no_authorize
    monkeypatch.setattr(
        processing,
        "inspect",
        lambda *_: SimpleNamespace(state="READY_FOR_EMBEDDING", error_code="NONE"),
    )
    worker = Worker(runtime, q)
    assert worker.step()
    assert state(q)["status"] == "SUCCEEDED"
    assert calls == ["outcome"]


@pytest.mark.parametrize(
    "failure,expected,retry",
    [
        (ExtractionError("PARSER_INVALID"), "PARSER_INVALID", False),
        (RuntimeError("private provider body, never log"), "DEPENDENCY_UNAVAILABLE", True),
    ],
)
def test_parser_failure_always_closes_spool_without_partial_commit(
    fixture, monkeypatch, failure, expected, retry
):
    q, runtime, calls = fixture
    plan = SimpleNamespace(repository_id=uuid4(), document_id=uuid4())
    original = SimpleNamespace(content_hash="a" * 64, byte_size=10, mime="text/plain")
    task = SimpleNamespace(plan=plan, original=original, version=SimpleNamespace(state="RECEIVED"))
    runtime.authority.authorize = lambda *_: SimpleNamespace(roles=("editor",))
    download = SimpleNamespace(
        file=SimpleNamespace(content_hash="a" * 64, file=object()),
        close=lambda: calls.append("closed"),
    )
    runtime.documents.original = lambda *_: download

    def parser(*_, **_kwargs):
        raise failure

    worker = Worker(runtime, q, extractor=parser)
    monkeypatch.setattr(worker, "_reconcile", lambda _: False)

    @contextmanager
    def transaction(*_, **_kwargs):
        yield None, None, None

    monkeypatch.setattr(worker, "_transaction", transaction)
    monkeypatch.setattr(processing, "start", lambda *_: task)
    monkeypatch.setattr(processing, "complete", lambda *_: calls.append("partial"))
    failures = []
    monkeypatch.setattr(
        worker,
        "_record_failure",
        lambda _claim, _trace, code, recoverable: failures.append((code, recoverable)),
    )
    assert worker.step()
    assert calls == ["closed"] and failures == [(expected, retry)]


def test_publication_profile_reconciles_ingest_ack_without_reading_content(fixture, monkeypatch):
    from contextlib import nullcontext

    q, runtime, calls = fixture
    runtime.authority.profile = "embedding_publication"
    runtime.registry = SimpleNamespace(connection=lambda *_: nullcontext(None))
    monkeypatch.setattr(
        processing, "inspect", lambda *_: SimpleNamespace(state="PUBLISHED", error_code="NONE")
    )
    claim = q.claim()
    assert Worker(runtime, q)._reconcile(claim)
    assert state(q)["status"] == "SUCCEEDED"
    assert calls == []
