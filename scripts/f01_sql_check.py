"""Operator-only T002 integration. SQL/Bao secrets remain inside this process."""

import logging
import re
from pathlib import Path
from uuid import UUID, uuid4, uuid5

import psycopg
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
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from rag_platform.control.migrations import upgrade_control
from rag_platform.control.models import DbLocation, Instance, Tenant
from rag_platform.providers.secrets import Credential, OpenBaoSecretStore, SecretStoreError
from rag_platform.provisioning.credentials import credential_for
from rag_platform.provisioning.migrations import migrate_initial
from rag_platform.provisioning.postgres import (
    PROVISIONER,
    Names,
    SqlProvisioningError,
    Target,
    bootstrap,
    database_record,
    execute,
    inspect_resources,
    provision_sql,
    role_record,
)
from rag_platform.tenancy.contracts import SecretRef

ROOT = Path(__file__).resolve().parents[1]
# Stable synthetic fixtures let a repeat prove reuse without creating duplicate identities.
NAMESPACE = UUID("014485c6-746c-43ab-b01b-a7d60f35b228")
TENANTS = [uuid5(NAMESPACE, name) for name in ("sql-fixture-a", "sql-fixture-b")]
COLLISION = Names(uuid5(NAMESPACE, "sql-foreign-role-fixture"))
PHASE = "START"


def expected_startup_rejection(error, database, username, state):
    """libpq startup failures may lack SQLSTATE. Never print their raw messages."""
    if error.sqlstate not in (None, state):
        return False
    if state == "42501":
        signature = r'FATAL:\s+permission denied for database "' + re.escape(database) + r'"'
    elif state == "28000":
        signature = (
            r'FATAL:\s+pg_hba.conf rejects connection for host "[^"]+", user "'
            + re.escape(username)
            + r'", database "'
            + re.escape(database)
            + r'", SSL encryption'
        )
    else:
        return False
    return re.search(signature, str(error)) is not None


def denied(target, database, credential, *, source_database, state="42501"):
    # Prove the exact credential/target/TLS works first, then verify the negative path.
    with target.connect(source_database, credential) as own:
        assert own.execute("SELECT current_user").fetchone() == (credential.username,)
        if state == "42501":
            assert own.execute(
                "SELECT has_database_privilege(current_user,%s,'CONNECT')", (database,)
            ).fetchone() == (False,)
    try:
        with target.connect(database, credential):
            pass
    except psycopg.OperationalError as error:
        if not expected_startup_rejection(error, database, credential.username, state):
            raise SqlProvisioningError("WRONG_DENIAL") from None
    else:
        raise SqlProvisioningError("CROSS_CONNECT_ALLOWED")


def denied_statement(connection, statement, *identifiers):
    try:
        with connection.transaction():
            execute(connection, statement, *identifiers)
    except psycopg.errors.InsufficientPrivilege:
        return
    raise SqlProvisioningError("PRIVILEGE_ALLOWED")


def own_probes(target, names, credentials, other):
    with target.connect(names.database, credentials["migrator"]) as connection:
        execute(connection, "SET ROLE {}", names.role("owner"))
        connection.execute(
            "CREATE TABLE IF NOT EXISTS public.f01_synthetic_probe "
            "(id uuid PRIMARY KEY, value integer NOT NULL)"
        )
    for kind in ("app", "readonly", "migrator"):
        with target.connect(names.database, credentials[kind], autocommit=True) as connection:
            assert connection.execute("SELECT current_database(), current_user").fetchone() == (
                names.database,
                names.role(kind),
            )
            assert connection.execute(
                "SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()"
            ).fetchone() == (True,)
            assert connection.execute("SELECT '[1,2,3]'::public.vector").fetchone()[0] is not None
            flags = role_record(connection, names.role(kind))
            assert flags[:6] == (False, False, False, False, False, True)
            for foreign in ("owner", "migrator", "app", "readonly"):
                denied_statement(connection, "SET ROLE {}", other.role(foreign))
            if kind != "migrator":
                for elevated in ("owner", "migrator"):
                    denied_statement(connection, "SET ROLE {}", names.role(elevated))
                denied_statement(connection, "CREATE TABLE public.forbidden_probe(id integer)")
            if kind == "app":
                with connection.transaction(force_rollback=True):
                    key = uuid4()
                    connection.execute(
                        "INSERT INTO public.f01_synthetic_probe VALUES (%s, 1)", (key,)
                    )
                    assert connection.execute(
                        "SELECT value FROM public.f01_synthetic_probe WHERE id=%s", (key,)
                    ).fetchone() == (1,)
                    connection.execute(
                        "UPDATE public.f01_synthetic_probe SET value=2 WHERE id=%s", (key,)
                    )
                    connection.execute("DELETE FROM public.f01_synthetic_probe WHERE id=%s", (key,))
            elif kind == "readonly":
                connection.execute("SELECT * FROM public.f01_synthetic_probe").fetchall()
                denied_statement(
                    connection,
                    "INSERT INTO public.f01_synthetic_probe VALUES (gen_random_uuid(), 1)",
                )
            else:
                execute(connection, "SET ROLE {}", names.role("owner"))
                assert connection.execute("SELECT current_user").fetchone() == (
                    names.role("owner"),
                )
        denied(target, other.database, credentials[kind], source_database=names.database)
        denied(
            target, "rag_control", credentials[kind], source_database=names.database, state="28000"
        )
        denied(target, "postgres", credentials[kind], source_database=names.database, state="28000")
        denied(
            target, "template1", credentials[kind], source_database=names.database, state="28000"
        )


def integration(store):
    global PHASE
    target = Target("postgres", 5432, CA)  # Explicit trusted development instance bootstrap.
    bootstrap_credential = Credential(
        "f01_bootstrap", Path("/run/secrets/postgres_password").read_text()
    )
    control_credential = Credential(
        "f01_control_migrator", Path("/run/secrets/control_migrator_password").read_text()
    )
    engine = sa.create_engine(
        "postgresql+psycopg://",
        creator=lambda: target.connect("rag_control", control_credential),
        poolclass=NullPool,
        hide_parameters=True,
    )
    try:
        PHASE = "CONTROL_MIGRATION"
        with engine.begin() as connection:
            upgrade_control(connection, ROOT)
        with Session(engine) as session, session.begin():
            instance = session.scalar(
                sa.select(Instance).where(
                    Instance.host == target.host, Instance.port == target.port
                )
            )
            if instance is None:
                instance = Instance(
                    id=uuid4(),
                    host=target.host,
                    port=target.port,
                    admin_secret_ref=uuid4(),
                    admin_secret_version=1,
                )
                session.add(instance)
                session.flush()
            instance_id = instance.id
            admin_ref = SecretRef(instance.admin_secret_ref, instance.admin_secret_version)
        with target.connect("rag_control", bootstrap_credential) as connection:
            exists = role_record(connection, PROVISIONER) is not None
        PHASE = "INSTANCE_BOOTSTRAP"
        admin = credential_for(store, admin_ref, PROVISIONER, resource_exists=exists)
        bootstrap(target, bootstrap_credential, admin)
        # Confirm that administrative SQL really uses a separate, non-superuser login.
        with target.connect("rag_control", admin) as connection:
            assert role_record(connection, PROVISIONER)[:6] == (
                False,
                True,
                True,
                False,
                False,
                True,
            )
        fixtures = []
        for tenant_id in TENANTS:
            names = Names(tenant_id)
            PHASE = "RESERVE"
            with Session(engine) as session, session.begin():
                tenant = session.get(Tenant, tenant_id)
                if tenant is None:
                    session.add(Tenant(id=tenant_id, desired_version="f01_tenant_0001"))
                    session.flush()
                elif tenant.state != "PROVISIONING":
                    raise SqlProvisioningError()
                location = session.get(DbLocation, tenant_id)
                if location is None:
                    location = DbLocation(
                        tenant_id=tenant_id,
                        instance_id=instance_id,
                        db_name=names.database,
                        app_secret_ref=uuid4(),
                        app_secret_version=1,
                        migrator_secret_ref=uuid4(),
                        migrator_secret_version=1,
                        readonly_secret_ref=uuid4(),
                        readonly_secret_version=1,
                    )
                    session.add(location)
                    session.flush()
                if (
                    location.instance_id != instance_id
                    or location.db_name != names.database
                    or not location.readonly_secret_ref
                ):
                    raise SqlProvisioningError()
                refs = {
                    kind: SecretRef(
                        getattr(location, kind + "_secret_ref"),
                        getattr(location, kind + "_secret_version"),
                    )
                    for kind in ("app", "migrator", "readonly")
                }
            with target.connect("rag_control", admin) as connection:
                inspect_resources(connection, names)
                resources = {
                    kind: role_record(connection, names.role(kind)) is not None for kind in refs
                }
                db_exists = database_record(connection, names.database) is not None
            PHASE = "TENANT_SECRETS"
            credentials = {
                kind: credential_for(
                    store, ref, names.role(kind), resource_exists=resources[kind] or db_exists
                )
                for kind, ref in refs.items()
            }
            PHASE = "TENANT_SQL"
            provision_sql(target, admin, names, credentials)
            PHASE = "TENANT_MIGRATION"
            migrate_initial(target, names, credentials["migrator"], ROOT)
            # Repeat exact resources/credentials; no password rotation or duplicate DB.
            provision_sql(target, admin, names, credentials)
            migrate_initial(target, names, credentials["migrator"], ROOT)
            assert all(store.read(refs[kind]) == credentials[kind] for kind in refs)
            fixtures.append((names, credentials))
        PHASE = "SQL_PROBES"
        for index, (names, credentials) in enumerate(fixtures):
            own_probes(target, names, credentials, fixtures[1 - index][0])
        PHASE = "COLLISION"
        # Retained synthetic foreign NOLOGIN role proves a matching name is not ownership.
        with target.connect("rag_control", bootstrap_credential) as connection:
            if role_record(connection, COLLISION.role("owner")) is None:
                execute(connection, "CREATE ROLE {} NOLOGIN", COLLISION.role("owner"))
            before = role_record(connection, COLLISION.role("owner"))
        with target.connect("rag_control", admin) as connection:
            try:
                inspect_resources(connection, COLLISION)
            except SqlProvisioningError:
                pass
            else:
                raise SqlProvisioningError("COLLISION_ACCEPTED")
            assert role_record(connection, COLLISION.role("owner")) == before
            assert database_record(connection, COLLISION.database) is None
            assert all(
                role_record(connection, COLLISION.role(kind)) is None
                for kind in ("app", "migrator", "readonly")
            )
            assert len({n.database for n, _ in fixtures} | {"rag_control"}) == 3
        print("PASS T002: tres bases distintas; roles limitados; TLS/vector y migración repetible.")
        print(
            "PASS T002: CRUD propio; readonly sin escritura; CONNECT/SET ROLE cruzados denegados."
        )
        print("PASS T002: secretos OpenBao; reintento sin rotación; colisión conservada.")
        print("Tenants sintéticos PROVISIONING; sin READY, bucket, saga ni cierre de F01.")
    finally:
        engine.dispose()


def main():
    global PHASE
    logging.disable(logging.CRITICAL)
    try:
        # Require a real operator terminal BEFORE any secret/API/SQL action.
        tty_required()
        PHASE = "BAO_STATUS"
        with client() as http:
            require_unsealed(http)
            PHASE = "OPERATOR_LOGIN"
            operator = login_operator(http)
            try:
                PHASE = "OPERATOR_POLICY"
                own = call(http, "GET", "auth/token/lookup-self", operator)["data"]
                if set(own["policies"]) != {"default", "f01-operator"}:
                    raise SqlProvisioningError("OPERATOR_POLICY")
                PHASE = "APPROLE_ISSUE"
                role = call(http, "GET", "auth/approle/role/f01-cli/role-id", operator)["data"][
                    "role_id"
                ]
                secret_id = call(http, "POST", "auth/approle/role/f01-cli/secret-id", operator, {})[
                    "data"
                ]["secret_id"]
                with OpenBaoSecretStore(ENDPOINT, CA) as store:
                    PHASE = "APPROLE_LOGIN"
                    store.login(role, secret_id)
                    del secret_id
                    integration(store)
            finally:
                call(http, "POST", "auth/token/revoke-self", operator, {})
    except OperatorFailure as error:
        raise SystemExit(f"F01-T002 {PHASE}: F01-{error.code}; sin detalles sensibles.") from None
    except SqlProvisioningError as error:
        allowed = {
            "OWNERSHIP_CONFLICT",
            "TEMPLATE_INCOMPATIBLE",
            "OPERATOR_POLICY",
            "WRONG_DENIAL",
            "CROSS_CONNECT_ALLOWED",
            "PRIVILEGE_ALLOWED",
            "COLLISION_ACCEPTED",
        }
        code = str(error) if str(error) in allowed else "SQL_FAILED"
        raise SystemExit(f"F01-T002 {PHASE}: {code}; recursos conservados.") from None
    except SecretStoreError as error:
        raise SystemExit(f"F01-T002 {PHASE}: {error.code.value}; recursos conservados.") from None
    except (psycopg.Error, DBAPIError) as error:
        original = error.orig if isinstance(error, DBAPIError) else error
        code = getattr(original, "sqlstate", None)
        state = (
            code if isinstance(code, str) and len(code) == 5 and code.isalnum() else "CONNECTION"
        )
        raise SystemExit(f"F01-T002 {PHASE}: SQLSTATE {state}; sin detalles sensibles.") from None
    except Exception:
        raise SystemExit(f"F01-T002 {PHASE}: operación detenida; sin detalles sensibles.") from None


if __name__ == "__main__":
    main()
