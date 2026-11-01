"""Product authorization matrix, explicit bootstrap and last-owner guard."""

import time
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa

from rag_platform.control.identity import AccessError, register
from rag_platform.control.identity_admin import IdentityAdministration
from rag_platform.control.identity_models import Membership
from rag_platform.control.migrations import upgrade_identity
from rag_platform.control.models import Tenant
from rag_platform.providers.identity import Identity

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def context():
    e = sa.create_engine("sqlite://", hide_parameters=True)
    with e.begin() as c:
        c.exec_driver_sql("PRAGMA foreign_keys=ON")
        upgrade_identity(c, ROOT)
    users = [
        register(e, Identity("https://synthetic.invalid", name, int(time.time()) + 300), uuid4())
        for name in ("alice", "bob", "carol", "dave")
    ]
    tenants = [uuid4(), uuid4()]
    with e.begin() as c:
        for t in tenants:
            c.execute(
                sa.insert(Tenant).values(
                    id=t,
                    state="READY",
                    migration_state="READY",
                    desired_version="f01_tenant_0001",
                    observed_version="f01_tenant_0001",
                )
            )

    def service(index):
        return IdentityAdministration(e, users[index], uuid4())

    service(0).bootstrap_operator(infrastructure_authorized=True)
    service(0).bootstrap_owner(tenants[0], users[0], "PERSONAL")
    service(0).bootstrap_owner(tenants[1], users[1], "ORG")
    yield e, users, tenants, service
    e.dispose()


def denied(call, code="ROLE_DENIED"):
    with pytest.raises(AccessError, match=code):
        call()


def test_operator_no_implicit_tenant_authority_and_bootstrap_not_takeover(context):
    e, u, t, s = context
    denied(lambda: s(0).membership(t[1], u[2], "reader"))
    denied(lambda: s(0).bootstrap_owner(t[1], u[0], "ORG"), "STATE_CONFLICT")
    denied(lambda: s(1).bootstrap_operator(infrastructure_authorized=True))
    denied(lambda: s(2).bootstrap_operator())
    assert s(0).bootstrap_operator(infrastructure_authorized=True)["state"] == "ACTIVE"
    assert not s(2).me()["memberships"]


def test_owner_admin_editor_reader_matrix(context):
    e, u, t, s = context
    s(0).membership(t[0], u[1], "admin")
    s(1).membership(t[0], u[2], "editor")
    denied(lambda: s(1).membership(t[0], u[2], "owner"))
    denied(lambda: s(1).membership(t[0], u[0], "reader"))
    denied(lambda: s(2).membership(t[0], u[3], "reader"))
    s(0).membership(t[0], u[2], "reader")
    denied(lambda: s(2).membership(t[0], u[3], "reader"))
    s(0).membership(t[0], u[1], "admin")
    with e.connect() as c:
        assert (
            c.scalar(
                sa.select(sa.func.count())
                .select_from(Membership)
                .where(Membership.tenant_id == t[0], Membership.user_id == u[1])
            )
            == 1
        )


def test_last_owner_cannot_be_removed(context):
    e, u, t, s = context
    denied(lambda: s(0).membership(t[0], u[0], "reader"), "LAST_OWNER")
    denied(lambda: s(0).membership(t[0], u[0], "owner", "REVOKED"), "LAST_OWNER")
    s(0).membership(t[0], u[1], "owner")
    s(0).membership(t[0], u[0], "reader")
    denied(lambda: s(1).membership(t[0], u[1], "reader"), "LAST_OWNER")
    denied(lambda: s(0).membership(t[0], u[2], "reader"))


def test_support_and_suspended_users_cannot_administer(context):
    e, u, t, s = context
    s(0).platform_role(u[2], "platform_support")
    denied(lambda: s(2).bootstrap_owner(t[1], u[2], "ORG"))
    s(0).membership(t[0], u[1], "admin")
    s(0).principal_state(u[1], "SUSPENDED")
    denied(lambda: s(1).membership(t[0], u[2], "reader"), "IDENTITY_SUSPENDED")
    with e.connect() as c:
        assert c.scalar(sa.text("SELECT count(*) FROM identity_audit WHERE outcome='DENIED'")) >= 2


def test_last_operator_guard_and_identity_immutable(context):
    e, u, t, s = context
    denied(lambda: s(0).platform_role(u[0], "platform_operator", "REVOKED"), "LAST_OWNER")
    denied(lambda: s(0).principal_state(u[0], "SUSPENDED"), "LAST_OWNER")
    s(0).platform_role(u[1], "platform_operator")
    s(0).principal_state(u[0], "SUSPENDED")
    denied(lambda: s(0).membership(t[0], u[2], "reader"), "IDENTITY_SUSPENDED")
    s(1).principal_state(u[0], "ACTIVE")
    assert s(0).me()["principal_id"] == str(u[0])


def test_inactive_owner_removal_does_not_remove_last_active_owner(context):
    e, u, t, s = context
    s(0).membership(t[0], u[1], "owner")
    s(0).principal_state(u[1], "SUSPENDED")
    s(0).membership(t[0], u[1], "reader", "REVOKED")
    denied(lambda: s(0).membership(t[0], u[0], "reader"), "LAST_OWNER")


@pytest.fixture
def cli_module(monkeypatch):
    import importlib

    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    return importlib.import_module("f02_identity_admin")


def test_cli_private_token_file_and_no_symlinks(cli_module, tmp_path):
    p = tmp_path / "token"
    p.write_text("synthetic-not-a-jwt")
    p.chmod(0o600)
    assert cli_module.read_token(p) == "synthetic-not-a-jwt"
    link = tmp_path / "link"
    link.symlink_to(p)
    with pytest.raises(AccessError, match="INPUT_INVALID"):
        cli_module.read_token(link)
    p.chmod(0o644)
    with pytest.raises(AccessError, match="INPUT_INVALID"):
        cli_module.read_token(p)


def test_cli_error_never_echoes_input_and_no_abbreviation(cli_module, capsys):
    fake = "synthetic-private-token-marker"
    with pytest.raises(SystemExit) as error:
        cli_module.parser().parse_args(["--token-file", "/private", "membership", "--tenant", fake])
    assert error.value.code == 2
    assert fake not in capsys.readouterr().err
    with pytest.raises(SystemExit):
        cli_module.parser().parse_args(
            [
                "--token-file",
                "/private",
                "membership",
                "--ten",
                str(uuid4()),
                "--user",
                str(uuid4()),
                "--role",
                "reader",
            ]
        )
