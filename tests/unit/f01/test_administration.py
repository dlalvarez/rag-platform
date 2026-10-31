"""T007: dispatch, strict input, safe metadata and retry without new reservations."""

import json
from contextlib import nullcontext
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from rag_platform.control.models import Base, Instance, ProvisioningOperation, Tenant
from rag_platform.provisioning.administration import AdminError, Administration
from rag_platform.provisioning.saga import VERSION, SagaError

ROOT = Path(__file__).resolve().parents[3]


class Storage:
    endpoint = "https://minio:9000"


class Backend:
    broken = False

    def __getattr__(self, step):
        if step not in {"secrets", "database", "migrate", "storage", "probes"}:
            raise AttributeError(step)

        def run():
            if self.broken and step == "storage":
                raise RuntimeError("secret-must-not-leak")
            return VERSION if step == "migrate" else None

        return run

    def compensate(self):
        return {
            k: "ABSENT" for k in ("SQL_DATABASE", "SQL_ROLES", "STORAGE_BUCKET", "STORAGE_USER")
        }


@pytest.fixture
def service():
    engine = sa.create_engine("sqlite://")
    Base.metadata.create_all(engine)
    instance = uuid4()
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
    service = Administration(
        engine,
        uuid4(),
        None,
        Path("/ca"),
        Storage(),
        ROOT,
        backend_factory=lambda _: backend,
        locks=lambda *_: nullcontext(),
    )
    yield service, instance, backend
    engine.dispose()


def test_create_retry_and_show_keep_identity_without_leaking_credentials(service):
    service, instance, backend = service
    key = uuid4()
    backend.broken = True
    with pytest.raises(SagaError, match="STORAGE_FAILED"):
        service.create(instance, key)
    with Session(service.engine) as session:
        tenant = session.scalar(sa.select(Tenant.id))
    before = service.show(tenant)
    assert before["state"] == "FAILED"
    backend.broken = False
    ready = service.retry(tenant)
    assert ready["state"] == "READY"
    repeated = service.create(instance, key)
    assert repeated == ready
    assert before["tenant"] == ready["tenant"]
    assert before["operation"]["id"] == ready["operation"]["id"]
    assert ready["operation"]["attempts"] == 2
    text = json.dumps(ready)
    assert not any(value in text for value in ("password", "client_token", "secret-must-not-leak"))
    with Session(service.engine) as session:
        assert session.query(Tenant).count() == session.query(ProvisioningOperation).count() == 1


def test_retry_unknown_never_reserves_new_identity(service):
    service, _, _ = service
    with pytest.raises(AdminError, match="UNKNOWN_TENANT"):
        service.retry(uuid4())
    with Session(service.engine) as session:
        assert session.query(Tenant).count() == 0


def test_legacy_tenant_without_operation_not_adopted(service):
    service, _, _ = service
    tenant = uuid4()
    with Session(service.engine) as session, session.begin():
        session.add(Tenant(id=tenant, desired_version=VERSION))
    with pytest.raises(AdminError, match="UNKNOWN_OPERATION"):
        service.retry(tenant)
    with Session(service.engine) as session:
        assert session.query(ProvisioningOperation).count() == 0


def test_failed_check_does_not_repair_or_change_state(service):
    service, instance, backend = service
    backend.broken = True
    with pytest.raises(SagaError):
        service.create(instance, uuid4())
    with Session(service.engine) as session:
        tenant = session.scalar(sa.select(Tenant.id))
    before = service.show(tenant)
    with pytest.raises(AdminError, match="NOT_READY"):
        service.check(tenant)
    assert service.show(tenant) == before


def test_uuid_argument_errors_do_not_echo_values(monkeypatch, capsys):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    import f01_admin

    with pytest.raises(SystemExit) as error:
        f01_admin.parser().parse_args(
            ["create", "--instance", "do-not-echo-password", "--key", str(uuid4())]
        )
    assert error.value.code == 2
    assert "do-not-echo" not in capsys.readouterr().err


def test_parser_and_dispatch_all_commands(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    import f01_admin

    class Service:
        def __getattr__(self, name):
            return lambda *args: (name, args)

    tenant, instance, key = uuid4(), uuid4(), uuid4()
    for command in ("check", "retry", "migrate"):
        args = f01_admin.parser().parse_args([command, "--tenant", str(tenant)])
        assert f01_admin.execute(args, Service()) == (command, (tenant,))
    args = f01_admin.parser().parse_args(["create", "--instance", str(instance), "--key", str(key)])
    assert f01_admin.execute(args, Service()) == ("create", (instance, key))
    args = f01_admin.parser().parse_args(["show", "--tenant", str(tenant)])
    assert f01_admin.execute(args, Service()) == ("show", (tenant,))
    args = f01_admin.parser().parse_args(["show", "--instances"])
    assert f01_admin.execute(args, Service()) == ("instances", ())


def test_mutating_commands_reject_non_tty_before_catalog_or_password(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    import f01_admin

    def refuse():
        raise f01_admin.OperatorFailure("TTY_REQUIRED")

    monkeypatch.setattr(f01_admin, "tty_required", refuse)
    monkeypatch.setattr(f01_admin, "catalog", lambda: pytest.fail("catalog accessed before TTY"))
    with pytest.raises(SystemExit):
        f01_admin.main(["retry", "--tenant", str(uuid4())])


def test_clean_checkout_attachment_creates_only_private_path_configuration(monkeypatch, tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location("f01_attach_host", ROOT / "scripts/f01_host.py")
    host = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(host)
    data = tmp_path / "existing-data"
    data.mkdir()
    for name in ("raft", "postgres", "tls", "config", "secrets"):
        (data / name).mkdir()
    checkout = tmp_path / "clean"
    checkout.mkdir()
    monkeypatch.setattr(host, "DATA", data)
    monkeypatch.setattr(host, "ENV", checkout / ".env.f01")
    monkeypatch.setattr(host, "validate_host", lambda: None)
    monkeypatch.setattr(
        host.subprocess, "run", lambda *_a, **_k: pytest.fail("Service action during attach")
    )
    host.attach_existing()
    contents = host.ENV.read_text()
    assert len(contents.splitlines()) == 3
    assert not host.ENV.stat().st_mode & 0o077
    with pytest.raises(ValueError, match="overwritten"):
        host.attach_existing()
    assert host.ENV.read_text() == contents
    assert sorted(p.name for p in checkout.iterdir()) == [".env.f01"]
