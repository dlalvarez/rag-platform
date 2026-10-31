"""T004: durable transitions, recovery gates and non-destructive compensation."""

from contextlib import contextmanager, nullcontext
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from rag_platform.control.migrations import upgrade_control
from rag_platform.control.models import (
    Instance,
    ProvisioningOperation,
    ProvisioningPending,
    ProvisioningStep,
    Tenant,
)
from rag_platform.provisioning.saga import RESOURCES, VERSION, Saga, SagaError

ROOT = Path(__file__).resolve().parents[3]


class Crash(BaseException):
    pass


class Backend:
    def __init__(self):
        self.effects = {}
        self.calls = []

    def __getattr__(self, step):
        if step not in {"secrets", "database", "migrate", "storage", "probes"}:
            raise AttributeError(step)

        def effect():
            self.calls.append(step)
            self.effects.setdefault(step, uuid4())
            return VERSION if step == "migrate" else None

        return effect

    def compensate(self):
        return dict.fromkeys(RESOURCES, "ACCESS_REVOKED")


@pytest.fixture
def fixture(tmp_path):
    engine = sa.create_engine("sqlite:///" + str(tmp_path / "control.db"), hide_parameters=True)
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        upgrade_control(connection, ROOT)
    instance, key, actor = uuid4(), uuid4(), uuid4()
    with Session(engine) as session, session.begin():
        session.add(
            Instance(
                id=instance,
                host="postgres",
                port=5432,
                admin_secret_ref=uuid4(),
                admin_secret_version=1,
            )
        )
    backend = Backend()
    saga = Saga(engine, lambda snap: backend, locks=lambda *args: nullcontext())
    yield engine, saga, backend, (key, instance, "https://minio:9000", actor)
    engine.dispose()


def states(engine, snap):
    with Session(engine) as session:
        return (
            session.get(Tenant, snap.tenant).state,
            session.get(ProvisioningOperation, snap.operation).state,
        )


def test_complete_and_repeat_do_not_repeat_effects(fixture):
    engine, saga, backend, args = fixture
    snap = saga.run(*args)
    calls = list(backend.calls)
    assert states(engine, snap) == ("READY", "SUCCEEDED")
    assert saga.run(*args) == snap
    assert backend.calls == calls
    with Session(engine) as session:
        assert session.query(Tenant).count() == session.query(ProvisioningOperation).count() == 1
        assert session.query(ProvisioningStep).count() == 6


def test_changed_binding_is_rejected(fixture):
    _, saga, _, args = fixture
    saga.reserve(*args)
    with pytest.raises(SagaError, match="REQUEST_CONFLICT"):
        saga.reserve(args[0], args[1], "https://another:9000", args[3])


@pytest.mark.parametrize("phase", ["SECRETS", "DATABASE", "MIGRATE", "STORAGE", "PROBES"])
def test_failure_never_ready_and_retry_preserves_identity(fixture, phase):
    engine, saga, backend, args = fixture
    snap = saga.reserve(*args)

    def fail(step, when, _):
        if step == phase and when == "after":
            raise RuntimeError("secret-bearing exception must not persist")

    with pytest.raises(SagaError) as failure:
        saga.run(*args, hook=fail)
    assert "secret-bearing" not in str(failure.value)
    assert states(engine, snap) == ("FAILED", "FAILED")
    effects = dict(backend.effects)
    with Session(engine) as session:
        assert session.query(ProvisioningPending).count() == 4
    assert saga.run(*args) == snap
    assert all(backend.effects[k] == v for k, v in effects.items())
    assert states(engine, snap) == ("READY", "SUCCEEDED")


def test_crash_after_effect_leaves_journal_for_reconciliation(fixture):
    engine, saga, backend, args = fixture

    def crash(step, when, _):
        if step == "DATABASE" and when == "after":
            raise Crash()

    with pytest.raises(Crash):
        saga.run(*args, hook=crash)
    snap = saga.reserve(*args)
    assert states(engine, snap) == ("PROVISIONING", "RUNNING")
    identity = backend.effects["database"]
    assert saga.run(*args) == snap
    assert backend.effects["database"] == identity


def test_incompatible_migration_blocks_ready(fixture):
    engine, saga, backend, args = fixture
    backend.migrate = lambda: "wrong_version"
    with pytest.raises(SagaError, match="MIGRATION_FAILED"):
        saga.run(*args)
    snap = saga.reserve(*args)
    assert states(engine, snap) == ("FAILED", "FAILED")
    assert "storage" not in backend.calls


def test_unknown_compensation_requires_review(fixture):
    engine, saga, backend, args = fixture
    backend.compensate = lambda: {"SQL_DATABASE": "arbitrary text"}

    def fail(*_):
        raise RuntimeError()

    with pytest.raises(SagaError):
        saga.run(*args, hook=fail)
    snap = saga.reserve(*args)
    with Session(engine) as session:
        assert session.get(ProvisioningOperation, snap.operation).compensation_state == "REVIEW"
        assert {p.disposition for p in session.query(ProvisioningPending)} == {"REVIEW"}


def test_tenant_lock_refuses_concurrent_effect_before_attempt_increment(fixture):
    engine, saga, backend, args = fixture
    snap = saga.reserve(*args)

    @contextmanager
    def locks(namespace, identity):
        if namespace == "f01-saga-tenant:":
            raise SagaError("LOCK_BUSY")
        yield

    saga.locks = locks
    with pytest.raises(SagaError, match="LOCK_BUSY"):
        saga.run(*args)
    assert backend.calls == []
    with Session(engine) as session:
        assert session.get(ProvisioningOperation, snap.operation).attempts == 0


def test_stale_success_is_not_silently_ready(fixture):
    engine, saga, _, args = fixture
    snap = saga.run(*args)
    with Session(engine) as session, session.begin():
        session.get(Tenant, snap.tenant).migration_state = "NEEDS_MIGRATION"
    with pytest.raises(SagaError, match="REQUEST_CONFLICT"):
        saga.run(*args)


def test_lost_final_commit_response_does_not_revoke_ready_resources(fixture):
    engine, saga, backend, args = fixture
    revocations = []
    backend.compensate = lambda: revocations.append("revoked")
    publication = {"pending": False, "raised": False}

    def before_commit(session):
        if publication["raised"]:
            return
        values = list(session.identity_map.values())
        publication["pending"] = any(
            isinstance(v, Tenant) and v.state == "READY" for v in values
        ) and any(isinstance(v, ProvisioningOperation) and v.state == "SUCCEEDED" for v in values)

    def after_commit(session):
        if publication["pending"] and not publication["raised"]:
            publication["raised"] = True
            raise RuntimeError("simulated lost final COMMIT response")

    sa.event.listen(Session, "before_commit", before_commit)
    sa.event.listen(Session, "after_commit", after_commit)
    try:
        with pytest.raises(RuntimeError, match="lost final COMMIT"):
            saga.run(*args)
    finally:
        sa.event.remove(Session, "before_commit", before_commit)
        sa.event.remove(Session, "after_commit", after_commit)
    snap = saga.reserve(*args)
    assert states(engine, snap) == ("READY", "SUCCEEDED")
    calls = list(backend.calls)
    assert saga.run(*args) == snap
    assert calls == backend.calls and revocations == []
