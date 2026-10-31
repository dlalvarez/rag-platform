"""T005 real administrative resolver/QueuePool checks. No end-user authorization."""

import logging
import time
from contextlib import ExitStack
from pathlib import Path
from uuid import uuid4

import sqlalchemy as sa
from f01_operator import (
    CA,
    ENDPOINT,
    OperatorFailure,
    call,
    client,
    login_operator,
    require_unsealed,
    tty_required,
)
from sqlalchemy.orm import Session

from rag_platform.control.models import DbLocation, Tenant
from rag_platform.providers.secrets import Credential, OpenBaoSecretStore, SecretStoreError
from rag_platform.provisioning.postgres import Target
from rag_platform.tenancy.registry import ConnectionRegistry
from rag_platform.tenancy.resolver import (
    AdministrativeTenant,
    CatalogResolver,
    TenantAccessError,
    control_engine,
)

PHASE = "START"


def issue(http, operator, store):
    role = call(http, "GET", "auth/approle/role/f01-cli/role-id", operator)["data"]["role_id"]
    secret = call(http, "POST", "auth/approle/role/f01-cli/secret-id", operator, {})["data"][
        "secret_id"
    ]
    store.login(role, secret)


def identity(connection, context, role="app"):
    row = connection.execute(
        sa.text(
            "SELECT current_database(),current_user,pg_backend_pid(),ssl "
            "FROM pg_stat_ssl WHERE pid=pg_backend_pid()"
        )
    ).one()
    assert row[0] == "rag_t_" + context.tenant_id.hex
    assert row[1] == row[0] + "_" + role
    assert row[3] is True
    flags = connection.execute(
        sa.text(
            "SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls "
            "FROM pg_roles WHERE rolname=current_user"
        )
    ).one()
    assert tuple(flags) == (False,) * 5
    return row[2]


def expect(code, action):
    try:
        action()
    except TenantAccessError as error:
        assert error.code == code
        return
    raise AssertionError("Expected closed rejection")


def borrow(registry, context, role="app"):
    with registry.connection(context, role):
        pass


def checks(http, operator, store):
    global PHASE
    credential = Credential(
        "f01_control_migrator", Path("/run/secrets/control_migrator_password").read_text()
    )
    control = control_engine(Target("postgres", 5432, CA), credential)
    resolver = CatalogResolver(control)
    registry = ConnectionRegistry(resolver, store, CA)
    try:
        with Session(control) as session:
            ids = session.scalars(
                sa.select(Tenant.id).where(Tenant.state == "READY").order_by(Tenant.id)
            ).all()
            failed = session.scalar(sa.select(Tenant.id).where(Tenant.state == "FAILED"))
        assert len(ids) >= 3 and failed is not None
        a, b, c = [AdministrativeTenant(value) for value in ids[:3]]
        PHASE = "RESOLUTION"
        expect("TENANT_UNAVAILABLE", lambda: borrow(registry, AdministrativeTenant(uuid4())))
        expect("TENANT_UNAVAILABLE", lambda: borrow(registry, AdministrativeTenant(failed)))
        expect("INVALID_CONTEXT", lambda: borrow(registry, str(a.tenant_id)))
        expect("INVALID_ROLE", lambda: borrow(registry, a, "migrator"))
        with registry.connection(a) as connection:
            pid_a = identity(connection, a)
            connection.execute(sa.text("SET LOCAL statement_timeout='1234ms'"))
        with registry.connection(b) as connection:
            pid_b = identity(connection, b)
        with registry.connection(a) as connection:
            assert identity(connection, a) == pid_a != pid_b
            assert connection.scalar(sa.text("SHOW statement_timeout")) == "10s"
        with registry.get_tenant_session(a) as session:
            assert (
                session.scalar(sa.text("SELECT current_database()")) == "rag_t_" + a.tenant_id.hex
            )
        print(
            "PASS T005: resolver READY; A→B→A sin mezcla, TLS/roles propios y rollback al devolver."
        )

        PHASE = "SATURATION"
        registry.close()
        registry = ConnectionRegistry(resolver, store, CA)
        with ExitStack() as stack:
            pids = set()
            for context in (a, b):
                for role in ("app", "readonly"):
                    for _ in range(2):
                        connection = stack.enter_context(registry.connection(context, role))
                        pids.add(identity(connection, context, role))
            assert len(pids) == 8
            assert registry.stats() == {"engines": 4, "leases": 8, "draining": 0}
            expect("CAPACITY", lambda: borrow(registry, c))
            started = time.monotonic()
            expect("POOL_TIMEOUT", lambda: borrow(registry, a))
            assert 4 <= time.monotonic() - started <= 12
            assert registry.stats()["leases"] == 8
        with registry.connection(c) as connection:
            identity(connection, c)
        assert registry.stats() == {"engines": 4, "leases": 0, "draining": 0}
        registry.close()
        assert registry.stats()["engines"] == 0
        print(
            "PASS T005: 4 engines/8 conexiones; capacidad y timeout reales; "
            "evicción/cierre sin fugas."
        )

        PHASE = "DRAINING"
        registry = ConnectionRegistry(resolver, store, CA)
        destination = resolver.resolve(a)
        old_ref = destination.credential
        # New synthetic reference, same credential/password; no SQL password rotation.
        replacement = store.write(uuid4(), store.read(old_ref), expected_version=0)
        try:
            with registry.connection(a) as previous:
                old_pid = identity(previous, a)
                with Session(control) as session, session.begin():
                    row = session.get(DbLocation, a.tenant_id)
                    assert (
                        row.app_secret_ref == old_ref.id
                        and row.app_secret_version == old_ref.version
                    )
                    row.app_secret_ref, row.app_secret_version = replacement.id, replacement.version
                with registry.connection(a) as current:
                    assert identity(current, a) != old_pid
                    assert identity(previous, a) == old_pid
                    assert registry.stats() == {"engines": 2, "leases": 2, "draining": 1}
                assert registry.stats()["draining"] == 1
            assert registry.stats() == {"engines": 1, "leases": 0, "draining": 0}
        finally:
            # Restore only the synthetic fixture's original opaque reference.
            with Session(control) as session, session.begin():
                row = session.get(DbLocation, a.tenant_id)
                if row.app_secret_ref == replacement.id:
                    row.app_secret_ref, row.app_secret_version = old_ref.id, old_ref.version
                elif row.app_secret_ref != old_ref.id:
                    raise TenantAccessError("CATALOG_UNAVAILABLE")
        with registry.connection(a) as connection:
            identity(connection, a)
        assert resolver.resolve(a).credential == old_ref
        registry.close()
        print(
            "PASS T005: referencia nueva drena pool antiguo sin cortar préstamo; "
            "referencia original restaurada."
        )

        PHASE = "SECRET_REVOKED"
        with OpenBaoSecretStore(ENDPOINT, CA) as revoked:
            issue(http, operator, revoked)
            denied_registry = ConnectionRegistry(resolver, revoked, CA)
            try:
                with denied_registry.connection(a) as connection:
                    identity(connection, a)
                # Revoke only this additional test token, preserving operator/main store.
                call(http, "POST", "auth/token/revoke-self", revoked._token, {})
                expect("SECRET_UNAVAILABLE", lambda: borrow(denied_registry, a))
                assert denied_registry.stats()["engines"] == 0
            finally:
                denied_registry.close()
        print("PASS T005: token AppRole revocado rechazado con pool ya caliente; sin fallback.")
        print(
            "T005: sin nuevos tenants, sin rotación de contraseñas; "
            "dos instancias pendientes de T006."
        )
    finally:
        registry.close()
        control.dispose()


def main():
    global PHASE
    logging.disable(logging.CRITICAL)
    try:
        tty_required()
        with client() as http:
            require_unsealed(http)
            PHASE = "OPERATOR_LOGIN"
            operator = login_operator(http)
            try:
                policies = call(http, "GET", "auth/token/lookup-self", operator)["data"]["policies"]
                if set(policies) != {"default", "f01-operator"}:
                    raise TenantAccessError("SECRET_UNAVAILABLE")
                with OpenBaoSecretStore(ENDPOINT, CA) as store:
                    issue(http, operator, store)
                    checks(http, operator, store)
            finally:
                call(http, "POST", "auth/token/revoke-self", operator, {})
    except OperatorFailure as error:
        raise SystemExit(f"F01-T005 {PHASE}: F01-{error.code}.") from None
    except SecretStoreError as error:
        raise SystemExit(f"F01-T005 {PHASE}: {error.code.value}.") from None
    except TenantAccessError as error:
        raise SystemExit(f"F01-T005 {PHASE}: {error.code}.") from None
    except (Exception, KeyboardInterrupt):
        raise SystemExit(f"F01-T005 {PHASE}: CHECK_FAILED; sin detalles sensibles.") from None


if __name__ == "__main__":
    main()
