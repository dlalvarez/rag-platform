"""Fence lifecycle and real authority decisions offline; live locking is separate."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from rag_platform.control.identity import AccessError
from rag_platform.control.identity_models import IdentityBase, Membership, TenantProfile, User
from rag_platform.control.models import Base, DbLocation, Instance, StorageLocation, Tenant
from rag_platform.ingestion.claims import ClaimExpired, locked_claim
from rag_platform.ingestion.queue import DurableQueue
from rag_platform.ingestion.queue_schema import jobs
from rag_platform.ingestion.worker_policy import StopRequested, before_commit, policy_guard
from rag_platform.tenancy.authorization import TenantAuthorizer


@pytest.fixture
def runtime(tmp_path):
    engine = sa.create_engine("sqlite:///" + str(tmp_path / "control.db"))
    with engine.connect() as c:
        c.exec_driver_sql("PRAGMA journal_mode=WAL")
    Base.metadata.create_all(engine)
    IdentityBase.metadata.create_all(engine)
    jobs.create(engine)
    tenant, actor, instance, trace = (uuid4() for _ in range(4))
    with Session(engine) as s, s.begin():
        s.add(
            Instance(
                id=instance,
                host="postgres",
                port=5432,
                admin_secret_ref=uuid4(),
                admin_secret_version=1,
            )
        )
        s.add(
            Tenant(
                id=tenant,
                state="READY",
                migration_state="READY",
                desired_version="f04_tenant_0003",
                observed_version="f04_tenant_0003",
            )
        )
        s.add(User(id=actor, issuer="https://synthetic.invalid", oidc_subject=str(actor)))
        s.flush()
        s.add(TenantProfile(tenant_id=tenant, kind="ORG"))
        s.add(Membership(user_id=actor, tenant_id=tenant, role="editor"))
        s.add(
            DbLocation(
                tenant_id=tenant,
                instance_id=instance,
                db_name="rag_t_" + tenant.hex,
                app_secret_ref=uuid4(),
                app_secret_version=1,
                readonly_secret_ref=uuid4(),
                readonly_secret_version=1,
                migrator_secret_ref=uuid4(),
                migrator_secret_version=1,
            )
        )
        s.add(
            StorageLocation(
                tenant_id=tenant,
                endpoint="https://synthetic.invalid",
                bucket="synthetic-" + tenant.hex,
                credential_ref=uuid4(),
                credential_version=1,
            )
        )
    queue = DurableQueue(engine, tenant_scope=(tenant,), lease_seconds=60)
    queue.enqueue(tenant, actor, uuid4(), uuid4(), uuid4())
    claim = queue.claim()
    authority = TenantAuthorizer(engine, b"k" * 32, profile="ingestion")
    context = authority.authorize(actor, tenant, trace)
    yield queue, claim, authority, context, trace
    engine.dispose()


def test_fence_complete_and_no_lifetime_escape(runtime):
    queue, claim, _authority, context, _trace = runtime
    with locked_claim(queue, claim) as guard:
        assert guard.check()
        before_commit(guard, context, lambda: False)
        guard.complete()
        with pytest.raises(ClaimExpired):
            guard.complete()
    assert not guard.active
    with pytest.raises(ClaimExpired):
        guard.check()
    assert queue.claim() is None


def test_control_transaction_rollback_leaves_claim_recoverable(runtime):
    queue, claim, *_ = runtime
    with pytest.raises(RuntimeError, match="synthetic interruption"):
        with locked_claim(queue, claim) as guard:
            guard.complete()
            raise RuntimeError("synthetic interruption")
    assert queue.complete(claim)


def test_expired_before_lock_and_forged_token_rejected(runtime):
    queue, claim, *_ = runtime
    with pytest.raises(ClaimExpired), locked_claim(queue, replace(claim, token=uuid4())):
        pytest.fail("stale claim entered")
    with queue.engine.begin() as c:
        c.execute(sa.update(jobs).values(lease_until=datetime.now(UTC) - timedelta(seconds=5)))
    with pytest.raises(ClaimExpired), locked_claim(queue, claim):
        pytest.fail("expired claim entered")
    fresh = queue.claim()
    assert fresh.attempt == 2 and fresh.token != claim.token


def test_expiry_while_guard_held_is_not_revived(runtime):
    queue, claim, *_ = runtime
    with locked_claim(queue, claim) as guard:
        guard.connection.execute(
            sa.update(jobs).values(lease_until=datetime.now(UTC) - timedelta(seconds=5))
        )
        with pytest.raises(ClaimExpired):
            guard.complete()
    assert queue.claim().attempt == 2


def test_stop_blocks_commit(runtime):
    queue, claim, _authority, context, _trace = runtime
    with locked_claim(queue, claim) as guard:
        with pytest.raises(StopRequested):
            before_commit(guard, context, lambda: True)
    assert queue.complete(claim)


def test_current_policy_accepts_only_validated_current_actor(runtime):
    queue, claim, authority, context, trace = runtime
    with locked_claim(queue, claim) as guard:
        checked = policy_guard(guard, authority, context, trace)
        assert checked.principal_id == claim.actor_id
        with pytest.raises(AccessError, match="INPUT_INVALID"):
            policy_guard(guard, authority, replace(context, principal_id=uuid4()), trace)
        with pytest.raises(AccessError, match="INPUT_INVALID"):
            policy_guard(guard, authority, replace(context, _proof="forged"), trace)


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("membership", "MEMBERSHIP_REQUIRED"),
        ("user", "IDENTITY_SUSPENDED"),
        ("reference", "STATE_CONFLICT"),
        ("schema", "TENANT_UNAVAILABLE"),
    ],
)
def test_policy_revalidated_after_claim_before_commit(runtime, kind, expected):
    queue, claim, authority, context, trace = runtime
    with Session(queue.engine) as s, s.begin():
        if kind == "membership":
            s.get(Membership, (context.principal_id, context.tenant_id)).state = "REVOKED"
        elif kind == "user":
            s.get(User, context.principal_id).state = "SUSPENDED"
        elif kind == "reference":
            s.get(DbLocation, context.tenant_id).app_secret_version = 2
        else:
            s.get(Tenant, context.tenant_id).observed_version = "future"
    with locked_claim(queue, claim) as guard:
        with pytest.raises(AccessError, match=expected):
            policy_guard(guard, authority, context, trace)


def test_reader_membership_never_runs_ingestion(runtime):
    queue, claim, authority, context, trace = runtime
    with Session(queue.engine) as s, s.begin():
        s.get(Membership, (context.principal_id, context.tenant_id)).role = "reader"
    reader = authority.authorize(context.principal_id, context.tenant_id, trace)
    with locked_claim(queue, claim) as guard:
        with pytest.raises(AccessError, match="ROLE_DENIED"):
            policy_guard(guard, authority, reader, trace)
