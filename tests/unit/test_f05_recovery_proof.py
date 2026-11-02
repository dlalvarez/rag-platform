"""Bound recovery QA to explicit versions and gate all budgets before any intent."""

import importlib
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from test_f05_embedding_worker import setup  # noqa: F401
from test_f05_real_embedding_selection import fixture_data  # noqa: F401

from rag_platform.embeddings.qwen import qwen_profile


@pytest.fixture
def module(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    return importlib.import_module("f05_recovery_check")


def test_selected_queue_cannot_claim_other_version(module, setup):  # noqa: F811
    s = setup
    record = dict(tenant=str(s.tenant), document=str(s.doc), version=str(s.version))
    queue = module.SelectedQueue(s.control, (s.tenant,), record)
    space = uuid4()
    expected = queue.enqueue(
        s.tenant, s.actor, s.doc, s.version, uuid4(), space, qwen_profile().fingerprint()
    )
    queue.enqueue(s.tenant, s.actor, s.doc, uuid4(), uuid4(), space, qwen_profile().fingerprint())
    claim = queue.claim()
    assert claim.id == expected and claim.version_id == s.version
    assert queue.claim() is None  # Another version remains queued, never claimed here.
    with module.locked_claim(queue, claim) as guard:
        guard.complete()
    module.stale_refused(queue, claim)


def test_positive_selection_explicit_and_atomic_default_unchanged(fixture_data):  # noqa: F811
    module, manifest, actors, scope = fixture_data
    first = module.selection(manifest, actors, scope)
    for fixture in manifest["fixtures"]:
        positive = dict(fixture["documents"][0], case="positive", document=str(uuid4()))
        fixture["documents"].append(positive)
    assert module.selection(manifest, actors, scope) == first
    selected = module.selection(manifest, actors, scope, case="positive")
    assert {r["document"] for r in first}.isdisjoint(r["document"] for r in selected)
    with pytest.raises(ValueError):
        module.selection(manifest, actors, scope, case="scan")


def test_all_budgets_checked_before_any_request(module, monkeypatch):
    @contextmanager
    def connection(*_args):
        yield SimpleNamespace(
            execute=lambda _statement: SimpleNamespace(
                scalars=lambda: SimpleNamespace(all=lambda: ["synthetic"])
            )
        )

    monkeypatch.setattr(module, "connect", connection)
    calls = []
    monkeypatch.setattr(module.processing, "request", lambda *_args: calls.append("request"))
    monkeypatch.setattr(module.f05_adopt, "save", lambda *_args: calls.append("save"))
    provider = SimpleNamespace(profile=qwen_profile(), count_tokens=lambda *_args: 513)
    record = dict(name="same-a", version=str(uuid4()))
    with pytest.raises(AssertionError):
        module.prepare(None, provider, uuid4(), [record] * 4)
    assert calls == []


@pytest.mark.parametrize(
    "stage,published,pointer", [("BATCH_COMMITTED", 0, False), ("RESULT_COMMITTED", 1, True)]
)
def test_hard_exit_requires_durable_checkpoint_and_heartbeats(
    module, monkeypatch, stage, published, pointer
):
    worker = object.__new__(module.FaultWorker)
    worker.record = dict(
        name="same-a" if stage == "BATCH_COMMITTED" else "same-b", version=str(uuid4())
    )
    worker.actor, worker.crash, worker.runtime = uuid4(), True, None
    worker.queue = SimpleNamespace(pulses=7)
    worker.provider = SimpleNamespace(calls=1)
    state = dict(
        job_status="RUNNING",
        attempts=1,
        ledger=[{}],
        published=published,
        processed_pointer=pointer,
    )
    monkeypatch.setattr(module, "snapshot", lambda *_args: dict(state))
    saved = []
    monkeypatch.setattr(module.f05_adopt, "save", lambda name, value: saved.append((name, value)))
    monkeypatch.setattr(module.os, "_exit", lambda code: (_ for _ in ()).throw(SystemExit(code)))
    claim = SimpleNamespace(version_id=module.UUID(worker.record["version"]))
    with pytest.raises(SystemExit) as error:
        worker._stage(stage, claim)
    assert error.value.code == 86 and saved[0][1]["successful_heartbeats"] == 7
    saved.clear()
    worker.queue.pulses = 6
    with pytest.raises(AssertionError):
        worker._stage(stage, claim)
    assert saved == []
