"""Live T004 effects using approved SQL, OpenBao and S3 primitives."""

import io
from pathlib import Path

from rag_platform.provisioning.credentials import credential_for
from rag_platform.provisioning.migrations import migrate_initial
from rag_platform.provisioning.postgres import (
    Names,
    Target,
    database_record,
    execute,
    inspect_resources,
    provision_sql,
    role_record,
    withdraw_sql,
)
from rag_platform.provisioning.saga import VERSION, SagaError
from rag_platform.provisioning.storage import StorageNames, StorageProvisioner


class LiveBackend:
    def __init__(self, snapshot, store, ca, storage_target, storage_admin, repository: Path):
        self.snapshot = snapshot
        self.store = store
        self.sql_target = Target(snapshot.host, snapshot.port, ca)
        self.sql_names = Names(snapshot.tenant, snapshot.operation)
        self.storage_names = StorageNames(snapshot.tenant, snapshot.operation)
        if snapshot.storage_endpoint != storage_target.endpoint:
            raise SagaError("REQUEST_CONFLICT")
        self.storage_target = storage_target
        self.storage_api = StorageProvisioner(storage_target, storage_admin)
        self.repository = repository
        self.admin = None
        self.credentials = {}
        self.storage_credential = None

    def reserve(self):
        return None

    def secrets(self):
        snap = self.snapshot
        self.admin = self.store.read(snap.admin)
        # Preflight both providers before generating any credential.
        with self.sql_target.connect("rag_control", self.admin, autocommit=True) as connection:
            inspect_resources(connection, self.sql_names, allow_disabled=True)
            exists = {
                kind: role_record(connection, self.sql_names.role(kind)) is not None
                or database_record(connection, self.sql_names.database) is not None
                for kind in ("migrator", "app", "readonly")
            }
        state = self.storage_api.inspect(
            self.storage_names, snap.storage_ref.id, allow_disabled=True
        )
        for kind, ref in zip(("migrator", "app", "readonly"), snap.sql_refs, strict=True):
            self.credentials[kind] = credential_for(
                self.store, ref, self.sql_names.role(kind), resource_exists=exists[kind]
            )
        self.storage_credential = credential_for(
            self.store, snap.storage_ref, self.storage_names.user, resource_exists=any(state)
        )

    def database(self):
        provision_sql(self.sql_target, self.admin, self.sql_names, self.credentials)

    def migrate(self):
        migrate_initial(
            self.sql_target, self.sql_names, self.credentials["migrator"], self.repository
        )
        with self.sql_target.connect(
            self.sql_names.database, self.credentials["migrator"]
        ) as connection:
            execute(connection, "SET ROLE {}", self.sql_names.role("owner"))
            rows = connection.execute(
                "SELECT version_num FROM public.alembic_version_tenant"
            ).fetchall()
            identity = connection.execute("SELECT tenant_id FROM public.ops_identity").fetchall()
            if rows != [(VERSION,)] or identity != [(self.snapshot.tenant,)]:
                raise SagaError("MIGRATION_FAILED")
        return VERSION

    def storage(self):
        self.storage_api.provision(
            self.storage_names, self.snapshot.storage_ref.id, self.storage_credential
        )

    def probes(self):
        with self.sql_target.connect(
            self.sql_names.database, self.credentials["app"]
        ) as connection:
            row = connection.execute(
                "SELECT current_database(), current_user, ssl FROM pg_stat_ssl "
                "WHERE pid=pg_backend_pid()"
            ).fetchone()
            if row != (self.sql_names.database, self.sql_names.role("app"), True):
                raise SagaError("SQL_FAILED")
            value = connection.execute(
                "SELECT '[1,2,3]'::public.vector <-> '[1,2,3]'::public.vector"
            ).fetchone()
            if value != (0.0,):
                raise SagaError("SQL_FAILED")
        s3 = self.storage_target.s3(self.storage_credential)
        key = "_f01/saga-probe/" + self.snapshot.operation.hex
        payload = b"F01 synthetic saga probe"
        s3.put_object(self.storage_names.bucket, key, io.BytesIO(payload), len(payload))
        response = s3.get_object(self.storage_names.bucket, key)
        try:
            if response.read(1024) != payload:
                raise SagaError("STORAGE_FAILED")
        finally:
            response.close()
            response.release_conn()
        if key not in {
            item.object_name for item in s3.list_objects(self.storage_names.bucket, prefix=key)
        }:
            raise SagaError("STORAGE_FAILED")
        s3.remove_object(self.storage_names.bucket, key)
        # References must still resolve to precisely the credentials used by probes.
        for ref, kind in zip(self.snapshot.sql_refs, ("migrator", "app", "readonly"), strict=True):
            if self.store.read(ref) != self.credentials[kind]:
                raise SagaError("SECRET_CONFLICT")
        if self.store.read(self.snapshot.storage_ref) != self.storage_credential:
            raise SagaError("SECRET_CONFLICT")

    def compensate(self):
        result = {}
        try:
            admin = self.admin or self.store.read(self.snapshot.admin)
            result.update(withdraw_sql(self.sql_target, admin, self.sql_names))
        except Exception:
            result.update(SQL_DATABASE="REVIEW", SQL_ROLES="REVIEW")
        try:
            result.update(
                self.storage_api.withdraw(self.storage_names, self.snapshot.storage_ref.id)
            )
        except Exception:
            result.update(STORAGE_BUCKET="REVIEW", STORAGE_USER="REVIEW")
        return result
