"""T006 real two-topology battery; synthetic fixtures, operator-only secrets."""

import logging
import multiprocessing
import re
import time
from dataclasses import dataclass, replace
from pathlib import Path
from uuid import UUID, uuid5

import psycopg
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
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
from f01_pool_check import identity, issue
from f01_saga_check import ACTOR
from f01_saga_check import engine as control_engine
from f01_sql_check import denied, denied_statement, own_probes, vector_probe
from f01_storage_check import STORAGE_ENDPOINT, admin_credential, probes
from minio.error import S3Error
from sqlalchemy.orm import Session

from rag_platform.control.models import (
    AuditControl,
    Instance,
    ProvisioningOperation,
    Tenant,
)
from rag_platform.providers.secrets import Credential, OpenBaoSecretStore, SecretStoreError
from rag_platform.provisioning.credentials import credential_for
from rag_platform.provisioning.live_saga import LiveBackend
from rag_platform.provisioning.migration_control import migrate_controlled
from rag_platform.provisioning.migrations import (
    MigrationError,
    apply_initial,
    migration_session,
)
from rag_platform.provisioning.postgres import (
    PROVISIONER,
    Names,
    Target,
    bootstrap,
    execute,
    role_record,
)
from rag_platform.provisioning.saga import Saga, SagaError
from rag_platform.provisioning.storage import StorageError, StorageNames, StorageTarget
from rag_platform.tenancy.contracts import SecretRef
from rag_platform.tenancy.registry import ConnectionRegistry
from rag_platform.tenancy.resolver import AdministrativeTenant, CatalogResolver, TenantAccessError

ROOT = Path(__file__).resolve().parents[1]
NAMESPACE = UUID("c6e95dc8-ad57-40da-afb6-70587f131f17")
PHASE = "START"


@dataclass
class Fixture:
    snap: object
    target: Target
    names: Names
    credentials: dict


def fixture_config(connection):
    config = Config()
    config.set_main_option("script_location", str(ROOT / "tests/integration/f01/migration_fixture"))
    config.attributes["connection"] = connection
    return config


def fixture_snapshot(fixture):
    with migration_session(
        fixture.target, fixture.names, fixture.credentials["migrator"]
    ) as connection:
        canonical = connection.scalar(
            sa.text("SELECT version_num FROM public.alembic_version_tenant")
        )
        version = connection.scalar(
            sa.text("SELECT version_num FROM public.alembic_version_fixture")
        )
        canary = connection.execute(
            sa.text("SELECT id,value,upgrade_value FROM public.f01_synthetic_migration_canary")
        ).all()
        absent = connection.scalar(
            sa.text("SELECT to_regclass('public.f01_synthetic_failed_migration') IS NULL")
        )
        assert absent
        return canonical, version, canary


def reversible(fixture):
    with migration_session(
        fixture.target, fixture.names, fixture.credentials["migrator"]
    ) as connection:
        config = fixture_config(connection)
        # First run creates the fixture base; subsequent runs retain its canary.
        if not connection.scalar(
            sa.text("SELECT to_regclass('public.alembic_version_fixture') IS NOT NULL")
        ):
            command.upgrade(config, "fixture_0001")
        command.upgrade(config, "fixture_0002")
        assert connection.execute(
            sa.text("SELECT id,value,upgrade_value FROM public.f01_synthetic_migration_canary")
        ).all() == [(1, 41, 42)]
        command.downgrade(config, "fixture_0001")
        columns = {
            row[0]
            for row in connection.execute(
                sa.text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name='f01_synthetic_migration_canary'"
                )
            )
        }
        assert columns == {"id", "value"}
        assert connection.execute(
            sa.text("SELECT id,value FROM public.f01_synthetic_migration_canary")
        ).all() == [(1, 41)]
        command.upgrade(config, "fixture_0002")


def fail_revision(target, names, credential, repository):
    with migration_session(target, names, credential) as connection:
        apply_initial(connection, names, repository)
        command.upgrade(fixture_config(connection), "fixture_0003_bad")
    raise AssertionError("Intentional revision did not fail")


def failed_state(control, tenant_id):
    with Session(control) as session:
        tenant = session.get(Tenant, tenant_id)
        assert (tenant.state, tenant.migration_state, tenant.observed_version) == (
            "FAILED",
            "MIGRATION_FAILED",
            None,
        )
    try:
        CatalogResolver(control).resolve(AdministrativeTenant(tenant_id))
    except TenantAccessError as error:
        assert error.code == "TENANT_UNAVAILABLE"
    else:
        raise AssertionError("Failed migration resolved READY")


def prepare_instance(control, store):
    second_id = uuid5(NAMESPACE, "second-instance")
    ref = SecretRef(uuid5(NAMESPACE, "second-instance-admin"), 1)
    target = Target("postgres2", 5432, CA)
    bootstrap_credential = Credential(
        "f01_bootstrap", Path("/run/secrets/postgres2_password").read_text()
    )
    with Session(control) as session, session.begin():
        primary = session.scalar(
            sa.select(Instance).where(Instance.host == "postgres", Instance.port == 5432)
        )
        assert primary is not None
        primary_id = primary.id
        instance = session.scalar(
            sa.select(Instance).where(Instance.host == "postgres2", Instance.port == 5432)
        )
        if instance is None:
            session.add(
                Instance(
                    id=second_id,
                    host="postgres2",
                    port=5432,
                    admin_secret_ref=ref.id,
                    admin_secret_version=ref.version,
                )
            )
        else:
            assert (instance.id, instance.admin_secret_ref, instance.admin_secret_version) == (
                second_id,
                ref.id,
                ref.version,
            )
    with target.connect("rag_control", bootstrap_credential) as connection:
        connection.execute("REVOKE CONNECT ON DATABASE rag_control FROM PUBLIC")
        connection.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
        exists = role_record(connection, PROVISIONER) is not None
    credential = credential_for(store, ref, PROVISIONER, resource_exists=exists)
    bootstrap(target, bootstrap_credential, credential)
    return primary_id, second_id


def provision(control, store, storage, instance_id, label, inject=False):
    key = uuid5(NAMESPACE, label)
    saga = Saga(
        control, lambda snap: LiveBackend(snap, store, CA, storage, admin_credential(), ROOT)
    )
    arguments = (key, instance_id, STORAGE_ENDPOINT, ACTOR)
    snap = saga.reserve(*arguments)
    with Session(control) as session:
        operation = session.get(ProvisioningOperation, snap.operation)
        done = operation.state == "SUCCEEDED"
        tenant_state = session.get(Tenant, snap.tenant).state
    if done and tenant_state == "FAILED":
        migrate_controlled(control, snap.tenant, ACTOR, store, CA, ROOT)
    if inject and not done:

        def failure(step, when, snapshot):
            if step == "STORAGE" and when == "before":
                try:
                    storage.s3().make_bucket(StorageNames(snapshot.tenant).bucket)
                except S3Error as error:
                    if error.code == "AccessDenied":
                        raise StorageError("STORAGE_DENIED") from None
                    raise
                raise AssertionError("Unsigned creation allowed")

        try:
            saga.run(*arguments, hook=failure)
        except SagaError as error:
            assert error.code == "STORAGE_FAILED"
        else:
            raise AssertionError("Bucket failure not observed")
        with Session(control) as session:
            assert session.get(Tenant, snap.tenant).state == "FAILED"
        before = tuple(store.read(ref) for ref in (*snap.sql_refs, snap.storage_ref))
    else:
        before = None
    result = saga.run(*arguments)
    assert result == snap and saga.run(*arguments) == snap
    if before is not None:
        assert tuple(store.read(ref) for ref in (*snap.sql_refs, snap.storage_ref)) == before
    if inject:
        with Session(control) as session:
            assert session.get(ProvisioningOperation, snap.operation).attempts >= 2
            assert (
                session.scalar(
                    sa.select(sa.func.count())
                    .select_from(AuditControl)
                    .where(
                        AuditControl.operation_id == snap.operation,
                        AuditControl.event_code == "STEP_FAILED",
                    )
                )
                >= 1
            )
    credentials = {
        kind: store.read(ref)
        for kind, ref in zip(("migrator", "app", "readonly"), snap.sql_refs, strict=True)
    }
    return Fixture(
        snap, Target(snap.host, snap.port, CA), Names(snap.tenant, snap.operation), credentials
    )


def cross_instance_sql(own, foreign):
    # The foreign endpoint must lack this principal: authentication denial is distinct
    # from CONNECT denial within one instance. Never count TLS/network/wrong password.
    with foreign.target.connect(foreign.names.database, foreign.credentials["app"]) as connection:
        assert not connection.execute(
            "SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname=%s)", (own.names.role("app"),)
        ).fetchone()[0]
    for kind, credential in own.credentials.items():
        with own.target.connect(own.names.database, credential) as connection:
            assert connection.execute("SELECT current_user").fetchone() == (credential.username,)
        try:
            with foreign.target.connect(foreign.names.database, credential):
                pass
        except psycopg.OperationalError as error:
            signature = (
                r'FATAL:\s+password authentication failed for user "'
                + re.escape(credential.username)
                + r'"'
            )
            assert error.sqlstate in (None, "28P01", "28000") and re.search(signature, str(error))
        else:
            raise AssertionError("Foreign endpoint accepted credential")
        with own.target.connect(own.names.database, credential, autocommit=True) as connection:
            # Unknown roles are absent on this node; do not claim a 42501 grant denial.
            assert not connection.execute(
                "SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname=%s)",
                (foreign.names.role(kind),),
            ).fetchone()[0]
        denied(
            own.target, "rag_control", credential, source_database=own.names.database, state="28000"
        )


def own_sql(fixture):
    names, credentials, target = fixture.names, fixture.credentials, fixture.target
    with target.connect(names.database, credentials["migrator"]) as connection:
        execute(connection, "SET ROLE {}", names.role("owner"))
        connection.execute(
            "CREATE TABLE IF NOT EXISTS public.f01_synthetic_probe "
            "(id uuid PRIMARY KEY,value integer NOT NULL)"
        )
    for kind, credential in credentials.items():
        with target.connect(names.database, credential, autocommit=True) as connection:
            assert connection.execute("SELECT current_database(),current_user").fetchone() == (
                names.database,
                credential.username,
            )
            assert role_record(connection, credential.username)[:6] == (
                False,
                False,
                False,
                False,
                False,
                True,
            )
            vector_probe(connection, names, kind)
            if kind != "migrator":
                denied_statement(connection, "SET ROLE {}", names.role("owner"))
                denied_statement(connection, "CREATE TABLE public.forbidden_t006(id integer)")
            if kind == "app":
                with connection.transaction(force_rollback=True):
                    value = uuid5(names.tenant, "crud-probe")
                    connection.execute(
                        "INSERT INTO public.f01_synthetic_probe VALUES(%s,1)", (value,)
                    )
                    assert connection.execute(
                        "SELECT value FROM public.f01_synthetic_probe WHERE id=%s", (value,)
                    ).fetchone() == (1,)
                    connection.execute(
                        "UPDATE public.f01_synthetic_probe SET value=2 WHERE id=%s", (value,)
                    )
                    connection.execute(
                        "DELETE FROM public.f01_synthetic_probe WHERE id=%s", (value,)
                    )
            elif kind == "readonly":
                connection.execute("SELECT * FROM public.f01_synthetic_probe").fetchall()
                denied_statement(
                    connection, "INSERT INTO public.f01_synthetic_probe VALUES(gen_random_uuid(),1)"
                )


def lock_holder(pipe, snap):
    logging.disable(logging.CRITICAL)
    try:
        role, secret = pipe.recv()
        with OpenBaoSecretStore(ENDPOINT, CA) as store:
            store.login(role, secret)
            del secret
            names = Names(snap.tenant, snap.operation)
            with migration_session(
                Target(snap.host, snap.port, CA), names, store.read(snap.sql_refs[0])
            ) as connection:
                apply_initial(connection, names, ROOT)
                pipe.send("MIGRATED_LOCKED")
                if not pipe.poll(45) or pipe.recv() != "GO":
                    raise MigrationError()
        pipe.send("COMMITTED")
    except Exception:
        pipe.send("CHILD_FAILED")
    finally:
        pipe.close()


def concurrent_migration(http, operator, control, store, fixture):
    # One extra process in this tools container; a fresh one-use SecretID over pipe.
    role = call(http, "GET", "auth/approle/role/f01-cli/role-id", operator)["data"]["role_id"]
    secret = call(http, "POST", "auth/approle/role/f01-cli/secret-id", operator, {})["data"][
        "secret_id"
    ]
    context = multiprocessing.get_context("spawn")
    parent, remote = context.Pipe()
    process = context.Process(target=lock_holder, args=(remote, fixture.snap))
    process.start()
    remote.close()
    parent.send((role, secret))
    del secret
    try:
        assert parent.poll(30) and parent.recv() == "MIGRATED_LOCKED"
        started = time.monotonic()
        try:
            migrate_controlled(control, fixture.snap.tenant, ACTOR, store, CA, ROOT)
        except MigrationError:
            pass
        else:
            raise AssertionError("Concurrent migration entered locked transaction")
        assert 4 <= time.monotonic() - started <= 15
        failed_state(control, fixture.snap.tenant)
        parent.send("GO")
        assert parent.poll(30) and parent.recv() == "COMMITTED"
    finally:
        process.join(10)
        if process.is_alive():
            process.terminate()
            process.join(5)
        parent.close()
    assert process.exitcode == 0
    migrate_controlled(control, fixture.snap.tenant, ACTOR, store, CA, ROOT)


def pair(http, operator, control, store, storage, instances, label):
    global PHASE
    PHASE = label + "_PROVISION"
    fixtures = [
        provision(control, store, storage, instance, label + "-" + name, inject=index == 0)
        for index, (instance, name) in enumerate(zip(instances, ("a", "b"), strict=True))
    ]
    a, b = fixtures
    assert a.names.database != b.names.database
    PHASE = label + "_SQL"
    if a.target.host == b.target.host:
        for index, fixture in enumerate(fixtures):
            own_probes(
                fixture.target, fixture.names, fixture.credentials, fixtures[1 - index].names
            )
    else:
        for index, fixture in enumerate(fixtures):
            own_sql(fixture)
            cross_instance_sql(fixture, fixtures[1 - index])
    PHASE = label + "_S3"
    probes(
        storage,
        [
            (StorageNames(f.snap.tenant, f.snap.operation), store.read(f.snap.storage_ref))
            for f in fixtures
        ],
    )
    PHASE = label + "_POOLS"
    registry = ConnectionRegistry(CatalogResolver(control), store, CA)
    try:
        contexts = [AdministrativeTenant(f.snap.tenant) for f in fixtures]
        pids = []
        for index in (0, 1, 0):
            with registry.connection(contexts[index]) as connection:
                pids.append(identity(connection, contexts[index]))
        assert pids[0] == pids[2] and registry.stats()["engines"] == 2
        # Across instances PID integers can coincide: identity is endpoint + database + role.
        if a.target.host == b.target.host:
            assert pids[0] != pids[1]
    finally:
        registry.close()
    if a.target.host != b.target.host:
        PHASE = label + "_WRONG_DESTINATION"

        class FaultedCatalog:
            wrong = False

            def resolve(self, context, role):
                destination = CatalogResolver(control).resolve(context, role)
                if self.wrong:
                    return replace(
                        destination,
                        instance_id=b.snap.instance,
                        host=b.target.host,
                        port=b.target.port,
                    )
                return destination

        catalog = FaultedCatalog()
        registry = ConnectionRegistry(catalog, store, CA)
        context = AdministrativeTenant(a.snap.tenant)
        try:
            with registry.connection(context) as previous:
                identity(previous, context)
                catalog.wrong = True
                try:
                    with registry.connection(context):
                        raise AssertionError("Wrong target acquired or fell back")
                except TenantAccessError as error:
                    assert error.code == "CONNECTION_FAILED"
                assert registry.stats()["leases"] == 1
                assert registry.stats()["draining"] == 1
                identity(previous, context)
            catalog.wrong = False
            with registry.connection(context) as restored:
                identity(restored, context)
        finally:
            registry.close()
        print(
            "PASS T006 TWO_INSTANCES: destino erróneo rechazado sin fallback; "
            "destino correcto recuperado."
        )
    PHASE = label + "_REVERSIBLE"
    for fixture in fixtures:
        reversible(fixture)
    before_other = fixture_snapshot(b)
    before_a = fixture_snapshot(a)
    PHASE = label + "_MIGRATION_FAILURE"
    try:
        migrate_controlled(control, a.snap.tenant, ACTOR, store, CA, ROOT, runner=fail_revision)
    except MigrationError:
        pass
    else:
        raise AssertionError("Failed revision published")
    failed_state(control, a.snap.tenant)
    assert fixture_snapshot(a) == before_a and fixture_snapshot(b) == before_other
    migrate_controlled(control, a.snap.tenant, ACTOR, store, CA, ROOT)
    migrate_controlled(control, a.snap.tenant, ACTOR, store, CA, ROOT)
    assert fixture_snapshot(a) == before_a
    PHASE = label + "_MIGRATION_LOCK"
    concurrent_migration(http, operator, control, store, a)
    assert fixture_snapshot(a) == before_a and fixture_snapshot(b) == before_other
    print(
        "PASS T006 "
        + label
        + ": SQL/S3 propios y cruces denegados; A→B→A con destinos/roles propios."
    )
    print(
        "PASS T006 " + label + ": fallo bucket sin READY y reintento estable; migración repetible."
    )
    print(
        "PASS T006 " + label + ": revisión reversible, fallo DDL revertido y otro tenant intacto."
    )
    print(
        "PASS T006 "
        + label
        + ": dos procesos, lock/timeout reales; FAILED sin versión falsa y recuperación."
    )


def main():
    global PHASE
    logging.disable(logging.CRITICAL)
    control = storage = None
    try:
        tty_required()
        with client() as http:
            require_unsealed(http)
            PHASE = "OPERATOR_LOGIN"
            operator = login_operator(http)
            try:
                assert set(
                    call(http, "GET", "auth/token/lookup-self", operator)["data"]["policies"]
                ) == {"default", "f01-operator"}
                with OpenBaoSecretStore(ENDPOINT, CA) as store:
                    issue(http, operator, store)
                    control = control_engine()
                    storage = StorageTarget(STORAGE_ENDPOINT, CA)
                    PHASE = "SECOND_INSTANCE"
                    primary, secondary = prepare_instance(control, store)
                    pair(
                        http, operator, control, store, storage, (primary, primary), "SAME_INSTANCE"
                    )
                    pair(
                        http,
                        operator,
                        control,
                        store,
                        storage,
                        (primary, secondary),
                        "TWO_INSTANCES",
                    )
                    print(
                        "T006: cuatro tenants sintéticos READY; sin cierre de F01, "
                        "sin backup/restore acreditado."
                    )
            finally:
                call(http, "POST", "auth/token/revoke-self", operator, {})
    except OperatorFailure as error:
        raise SystemExit(f"F01-T006 {PHASE}: F01-{error.code}.") from None
    except SecretStoreError as error:
        raise SystemExit(f"F01-T006 {PHASE}: {error.code.value}.") from None
    except (MigrationError, SagaError, TenantAccessError) as error:
        raise SystemExit(f"F01-T006 {PHASE}: {error.code}; recursos conservados.") from None
    except (Exception, KeyboardInterrupt):
        raise SystemExit(f"F01-T006 {PHASE}: CHECK_FAILED; sin detalles sensibles.") from None
    finally:
        if control is not None:
            control.dispose()
        if storage is not None:
            storage.close()


if __name__ == "__main__":
    main()
