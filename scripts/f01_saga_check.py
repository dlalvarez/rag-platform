"""Real T004 battery; operator password only at the controlling terminal."""

import argparse
import logging
import multiprocessing
import os
from pathlib import Path
from uuid import UUID, uuid4

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
from f01_storage_check import STORAGE_ENDPOINT, admin_credential, read_object
from minio.commonconfig import Tags
from minio.error import S3Error
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from rag_platform.control.models import (
    Instance,
    ProvisioningOperation,
    ProvisioningPending,
    ProvisioningStep,
    Tenant,
)
from rag_platform.providers.secrets import Credential, OpenBaoSecretStore, SecretStoreError
from rag_platform.provisioning.live_saga import LiveBackend
from rag_platform.provisioning.postgres import Names, Target, database_record, role_record
from rag_platform.provisioning.saga import VERSION, Saga, SagaError, postgres_lock
from rag_platform.provisioning.storage import (
    StorageError,
    StorageNames,
    StorageProvisioner,
    StorageTarget,
)

REPOSITORY = Path(__file__).resolve().parents[1]
ACTOR = UUID("fe87c033-90df-48bc-bd82-4f94a2fe468c")
PHASE = "START"


def engine():
    credential = Credential(
        "f01_control_migrator", Path("/run/secrets/control_migrator_password").read_text()
    )
    target = Target("postgres", 5432, CA)
    return sa.create_engine(
        "postgresql+psycopg://",
        creator=lambda: target.connect("rag_control", credential),
        poolclass=NullPool,
        hide_parameters=True,
    )


def factory(store, target):
    return lambda snap: LiveBackend(snap, store, CA, target, admin_credential(), REPOSITORY)


def instance_id(control):
    with Session(control) as session:
        row = session.scalar(
            sa.select(Instance).where(Instance.host == "postgres", Instance.port == 5432)
        )
        if row is None:
            raise SagaError("REQUEST_CONFLICT")
        return row.id


def args(key, instance):
    return key, instance, STORAGE_ENDPOINT, ACTOR


def state(control, snap, expected):
    with Session(control) as session:
        tenant = session.get(Tenant, snap.tenant)
        operation = session.get(ProvisioningOperation, snap.operation)
        assert (tenant.state, operation.state) == expected
        if expected == ("READY", "SUCCEEDED"):
            assert (tenant.migration_state, tenant.observed_version) == ("READY", VERSION)
            assert (
                session.scalars(
                    sa.select(ProvisioningStep.state).where(
                        ProvisioningStep.operation_id == snap.operation
                    )
                ).all()
                == ["SUCCEEDED"] * 6
            )


def identities(store, snap):
    return tuple(store.read(ref) for ref in (*snap.sql_refs, snap.storage_ref))


def sql_identity(store, snap):
    names = Names(snap.tenant, snap.operation)
    with Target(snap.host, snap.port, CA).connect(
        "rag_control", store.read(snap.admin), autocommit=True
    ) as connection:
        db = connection.execute(
            "SELECT oid FROM pg_database WHERE datname=%s", (names.database,)
        ).fetchone()
        roles = connection.execute(
            "SELECT oid FROM pg_roles WHERE rolname=ANY(%s) ORDER BY rolname",
            ([names.role(k) for k in ("owner", "migrator", "app", "readonly")],),
        ).fetchall()
        return db, roles


def child(pipe, key, instance, mode):
    logging.disable(logging.CRITICAL)
    control = target = None
    try:
        role, secret_id = pipe.recv()
        with OpenBaoSecretStore(ENDPOINT, CA) as store:
            store.login(role, secret_id)
            del secret_id
            control = engine()
            target = StorageTarget(STORAGE_ENDPOINT, CA)
            saga = Saga(control, factory(store, target))

            def hook(step, when, snap):
                if step == "DATABASE" and when == "after" and mode == "crash":
                    os._exit(86)
                if step == "DATABASE" and when == "before" and mode == "concurrent":
                    pipe.send("LOCKED")
                    if not pipe.poll(60) or pipe.recv() != "GO":
                        raise SagaError("SQL_FAILED")

            saga.run(*args(key, instance), hook=hook)
            pipe.send("READY")
    except SagaError as error:
        pipe.send(error.code)
    except Exception:
        pipe.send("CHILD_FAILED")
    finally:
        if control is not None:
            control.dispose()
        if target is not None:
            target.close()
        pipe.close()


def start_child(http, operator, key, instance, mode):
    # Credentials cross an anonymous pipe; never process arguments, environment or files.
    role = call(http, "GET", "auth/approle/role/f01-cli/role-id", operator)["data"]["role_id"]
    secret_id = call(http, "POST", "auth/approle/role/f01-cli/secret-id", operator, {})["data"][
        "secret_id"
    ]
    context = multiprocessing.get_context("spawn")
    parent, remote = context.Pipe()
    process = context.Process(target=child, args=(remote, key, instance, mode))
    process.start()
    remote.close()
    parent.send((role, secret_id))
    del secret_id
    return process, parent


def finish(process, pipe, expected):
    process.join(60)
    if process.is_alive():
        process.terminate()
        process.join(5)
        raise SagaError("SQL_FAILED")
    try:
        assert process.exitcode == expected
    finally:
        pipe.close()


def battery(http, operator, store):
    global PHASE
    control = engine()
    target = StorageTarget(STORAGE_ENDPOINT, CA)
    saga = Saga(control, factory(store, target))
    instance = instance_id(control)
    try:
        PHASE = "BUCKET_FAILURE"
        key = uuid4()
        snap = saga.reserve(*args(key, instance))

        def fail_bucket(step, when, snapshot):
            if step == "STORAGE" and when == "before":
                # Deliberately unsigned HTTPS request: a real denied CreateBucket,
                # isolated to this failure injection, never a credential fallback.
                try:
                    target.s3().make_bucket(StorageNames(snapshot.tenant).bucket)
                except S3Error as error:
                    if error.code == "AccessDenied":
                        raise StorageError("STORAGE_DENIED") from None
                    raise SagaError("STORAGE_FAILED") from None
                raise AssertionError("Unsigned CreateBucket unexpectedly allowed")

        try:
            saga.run(*args(key, instance), hook=fail_bucket)
        except SagaError as error:
            assert error.code == "STORAGE_FAILED"
        else:
            raise AssertionError("Injected failure was not observed")
        state(control, snap, ("FAILED", "FAILED"))
        before, sql_before = identities(store, snap), sql_identity(store, snap)
        names = Names(snap.tenant, snap.operation)
        with Target(snap.host, snap.port, CA).connect(
            "rag_control", store.read(snap.admin), autocommit=True
        ) as connection:
            assert database_record(connection, names.database)[2] is False
            assert all(
                role_record(connection, names.role(k))[5] is False
                for k in ("migrator", "app", "readonly")
            )
        assert saga.run(*args(key, instance)) == snap
        state(control, snap, ("READY", "SUCCEEDED"))
        assert identities(store, snap) == before and sql_identity(store, snap) == sql_before
        assert saga.run(*args(key, instance)) == snap
        print(
            "PASS T004: fallo real de bucket; FAILED sin READY; "
            "reintento sin rotación ni duplicados."
        )

        PHASE = "CRASH_AFTER_SQL"
        key = uuid4()
        process, pipe = start_child(http, operator, key, instance, "crash")
        finish(process, pipe, 86)
        snap = saga.reserve(*args(key, instance))
        state(control, snap, ("PROVISIONING", "RUNNING"))
        before, sql_before = identities(store, snap), sql_identity(store, snap)
        with Session(control) as session:
            assert session.get(ProvisioningStep, (snap.operation, "DATABASE")).state == "RUNNING"
        assert saga.run(*args(key, instance)) == snap
        state(control, snap, ("READY", "SUCCEEDED"))
        assert identities(store, snap) == before and sql_identity(store, snap) == sql_before
        print(
            "PASS T004: caída de proceso tras SQL y antes del journal; "
            "recuperación de la misma operación."
        )

        PHASE = "CONCURRENT_RETRY"
        key = uuid4()
        process, pipe = start_child(http, operator, key, instance, "concurrent")
        try:
            assert pipe.poll(45) and pipe.recv() == "LOCKED"
            snap = saga.reserve(*args(key, instance))
            try:
                saga.run(*args(key, instance))
            except SagaError as error:
                assert error.code == "LOCK_BUSY"
            else:
                raise AssertionError("Concurrent attempt entered external effects")
            with Session(control) as session:
                assert session.get(ProvisioningOperation, snap.operation).attempts == 1
            pipe.send("GO")
            assert pipe.poll(60) and pipe.recv() == "READY"
        finally:
            finish(process, pipe, 0)
        state(control, snap, ("READY", "SUCCEEDED"))
        assert saga.run(*args(key, instance)) == snap
        with Session(control) as session:
            assert (
                session.scalar(
                    sa.select(sa.func.count())
                    .select_from(ProvisioningOperation)
                    .where(ProvisioningOperation.idempotency_key == key)
                )
                == 1
            )
        print("PASS T004: dos procesos, un lock/tenant/operación; segundo intento sin efectos.")

        PHASE = "FOREIGN_RESOURCE"
        key = uuid4()
        snap = saga.reserve(*args(key, instance))
        foreign = StorageNames(snap.tenant, snap.operation)
        api = StorageProvisioner(target, admin_credential())
        api.s3.make_bucket(foreign.bucket)
        tags = Tags.new_bucket_tags()
        tags["synthetic-owner"] = "foreign"
        api.s3.set_bucket_tags(foreign.bucket, tags)
        import io

        api.s3.put_object(foreign.bucket, "canary", io.BytesIO(b"foreign synthetic"), 17)
        try:
            saga.run(*args(key, instance))
        except SagaError as error:
            assert error.code == "OWNERSHIP_CONFLICT"
        else:
            raise AssertionError("Foreign bucket adopted")
        state(control, snap, ("FAILED", "FAILED"))
        assert dict(api.s3.get_bucket_tags(foreign.bucket)) == dict(tags)
        assert read_object(api.s3, foreign.bucket, "canary") == b"foreign synthetic"
        with Session(control) as session:
            assert session.get(ProvisioningOperation, snap.operation).compensation_state == "REVIEW"
            assert (
                session.get(ProvisioningPending, (snap.operation, "STORAGE_BUCKET")).disposition
                == "REVIEW"
            )
        print("PASS T004: recurso ajeno y canary conservados; revisión pendiente registrada.")
        print("T004: tres tenants sintéticos READY y uno FAILED; F01 sigue abierta.")
    finally:
        control.dispose()
        target.close()


def lock_probe():
    control = engine()
    identity = uuid4()
    try:
        with postgres_lock(control, "f01-t004-probe:", identity):
            try:
                with postgres_lock(control, "f01-t004-probe:", identity):
                    raise AssertionError("Concurrent lock accepted")
            except SagaError as error:
                assert error.code == "LOCK_BUSY"
            with control.connect() as connection:
                rows = connection.execute(
                    sa.text(
                        "SELECT a.state,a.xact_start FROM pg_locks l "
                        "JOIN pg_stat_activity a ON a.pid=l.pid WHERE l.locktype='advisory' "
                        "AND l.granted AND a.usename=current_user AND l.pid<>pg_backend_pid()"
                    )
                ).all()
                assert rows and all(row == ("idle", None) for row in rows)
        with postgres_lock(control, "f01-t004-probe:", identity):
            pass
        print("PASS T004: lock de sesión exclusivo, sin transacción abierta y liberado.")
    finally:
        control.dispose()


def main():
    global PHASE
    logging.disable(logging.CRITICAL)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--locks-only", action="store_true")
    options = parser.parse_args()
    try:
        if options.locks_only:
            lock_probe()
            return
        tty_required()
        with client() as http:
            require_unsealed(http)
            PHASE = "OPERATOR_LOGIN"
            operator = login_operator(http)
            try:
                own = call(http, "GET", "auth/token/lookup-self", operator)["data"]
                if set(own["policies"]) != {"default", "f01-operator"}:
                    raise SagaError("SECRET_DENIED")
                role = call(http, "GET", "auth/approle/role/f01-cli/role-id", operator)["data"][
                    "role_id"
                ]
                secret_id = call(http, "POST", "auth/approle/role/f01-cli/secret-id", operator, {})[
                    "data"
                ]["secret_id"]
                with OpenBaoSecretStore(ENDPOINT, CA) as store:
                    store.login(role, secret_id)
                    del secret_id
                    battery(http, operator, store)
            finally:
                call(http, "POST", "auth/token/revoke-self", operator, {})
    except OperatorFailure as error:
        raise SystemExit(f"F01-T004 {PHASE}: F01-{error.code}.") from None
    except SecretStoreError as error:
        raise SystemExit(f"F01-T004 {PHASE}: {error.code.value}.") from None
    except SagaError as error:
        raise SystemExit(f"F01-T004 {PHASE}: {error.code}; recursos conservados.") from None
    except (Exception, KeyboardInterrupt):
        raise SystemExit(f"F01-T004 {PHASE}: CHECK_FAILED; sin detalles sensibles.") from None


if __name__ == "__main__":
    main()
