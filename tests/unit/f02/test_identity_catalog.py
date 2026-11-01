"""Additive identity invariants; baseline F01 migration remains phase-bounded."""

import time
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

from rag_platform.control.identity import AccessError, register
from rag_platform.control.identity_models import IdentityBase, Membership, User
from rag_platform.control.migrations import upgrade_control, upgrade_identity
from rag_platform.control.models import Base, Tenant
from rag_platform.providers.identity import Identity

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def engine():
    e = sa.create_engine("sqlite://", poolclass=StaticPool, hide_parameters=True)
    with e.begin() as c:
        c.exec_driver_sql("PRAGMA foreign_keys=ON")
        upgrade_identity(c, ROOT)
    yield e
    e.dispose()


def test_legacy_migration_target_is_bounded_and_later_metadata_preserved(engine):
    with engine.begin() as c:
        upgrade_identity(c, ROOT)
        upgrade_control(c, ROOT)
        assert (
            c.scalar(sa.text("SELECT version_num FROM alembic_version_control"))
            == "f02_control_0005"
        )
        assert set(sa.inspect(c).get_table_names()) == (
            set(Base.metadata.tables)
            | set(IdentityBase.metadata.tables)
            | {"alembic_version_control"}
        )
    # Identity metadata stays out of the frozen F01 declarative base.
    assert "users" not in Base.metadata.tables


def test_identity_pair_uuid_and_no_implicit_membership(engine):
    identity = Identity("https://synthetic.invalid/one", "subject", int(time.time()) + 60)
    first = register(engine, identity, uuid4())
    assert register(engine, identity, uuid4()) == first
    second = register(
        engine, Identity("https://synthetic.invalid/two", "subject", int(time.time()) + 60), uuid4()
    )
    assert first != second
    with engine.connect() as c:
        assert c.scalar(sa.select(sa.func.count()).select_from(Membership)) == 0
        assert c.scalar(sa.text("SELECT count(*) FROM platform_roles")) == 0


def test_suspended_identity_not_reactivated_and_denial_persisted(engine):
    identity = Identity("https://synthetic.invalid/one", "subject", int(time.time()) + 60)
    user = register(engine, identity, uuid4())
    with engine.begin() as c:
        c.execute(sa.update(User).where(User.id == user).values(state="SUSPENDED"))
    with pytest.raises(AccessError, match="IDENTITY_SUSPENDED"):
        register(engine, identity, uuid4())
    with engine.connect() as c:
        assert c.scalar(sa.select(User.state).where(User.id == user)) == "SUSPENDED"
        assert (
            c.scalar(
                sa.text("SELECT count(*) FROM identity_audit WHERE reason='IDENTITY_SUSPENDED'")
            )
            == 1
        )


@pytest.mark.parametrize(
    "table,values",
    [
        ("users", {"issuer": "", "oidc_subject": "s"}),
        ("users", {"issuer": "https://x", "oidc_subject": "s", "state": "ADMIN"}),
        ("tenant_profiles", {"kind": "EVERYONE"}),
        ("memberships", {"role": "superuser"}),
        ("memberships", {"role": "reader", "state": "MAGIC"}),
        ("platform_roles", {"role": "root"}),
        ("identity_audit", {"event_code": "jwt=private"}),
    ],
)
def test_constraints_cannot_carry_freeform_authority_or_payload(engine, table, values):
    user, tenant = uuid4(), uuid4()
    with engine.begin() as c:
        c.execute(sa.insert(User).values(id=user, issuer="https://fixture", oidc_subject="subject"))
        c.execute(sa.insert(Tenant).values(id=tenant, desired_version="f01_tenant_0001"))
        if table == "users":
            record = {"id": uuid4()}
        elif table == "tenant_profiles":
            record = {"tenant_id": tenant}
        elif table in ("memberships", "platform_roles"):
            record = {"user_id": user}
            if table == "memberships":
                record["tenant_id"] = tenant
        else:
            record = {"id": uuid4(), "request_id": uuid4(), "outcome": "DENIED", "reason": "NONE"}
        with pytest.raises(IntegrityError), c.begin_nested():
            c.execute(IdentityBase.metadata.tables[table].insert().values(record | values))


def test_no_secret_or_arbitrary_content_columns(engine):
    forbidden = {"password", "token", "payload", "email", "content", "document", "prompt", "claims"}
    assert not forbidden & {
        col.name for table in IdentityBase.metadata.tables.values() for col in table.columns
    }
    assert not any(
        isinstance(col.type, (sa.JSON, sa.Text, sa.LargeBinary))
        for table in IdentityBase.metadata.tables.values()
        for col in table.columns
    )
