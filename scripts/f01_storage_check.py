"""T003 compatibility calibration or real operator/OpenBao tenant battery."""

import argparse
import io
import logging
import secrets
from pathlib import Path
from uuid import uuid4, uuid5

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
from f01_sql_check import NAMESPACE, TENANTS
from minio.error import MinioAdminException, S3Error
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from rag_platform.control.models import StorageLocation, Tenant
from rag_platform.providers.secrets import Credential, OpenBaoSecretStore, SecretStoreError
from rag_platform.provisioning.credentials import credential_for
from rag_platform.provisioning.postgres import Target
from rag_platform.provisioning.storage import (
    StorageError,
    StorageNames,
    StorageProvisioner,
    StorageTarget,
    admin_error,
)
from rag_platform.tenancy.contracts import SecretRef

PHASE = "START"
STORAGE_ENDPOINT = "https://minio:9000"


def admin_credential():
    return Credential(
        Path("/run/secrets/storage_admin_user").read_text(),
        Path("/run/secrets/storage_admin_password").read_text(),
    )


def payload(names):
    return ("F01 synthetic storage probe " + names.tenant.hex).encode()


def key(names):
    return "_f01/probe/" + names.tenant.hex + ".txt"


def read_object(s3, bucket, name):
    response = s3.get_object(bucket, name)
    try:
        return response.read(1024)
    finally:
        response.close()
        response.release_conn()


def put_fixture(s3, names):
    value = payload(names)
    try:
        existing = read_object(s3, names.bucket, key(names))
    except S3Error as error:
        if error.code != "NoSuchKey":
            raise
    else:
        if existing != value:
            raise StorageError()
        return
    s3.put_object(names.bucket, key(names), io.BytesIO(value), len(value))


def require_denied(function):
    try:
        function()
    except S3Error as error:
        if error.code != "AccessDenied":
            raise StorageError("STORAGE_INVALID") from None
        return
    raise StorageError("ISOLATION_FAILED")


def probes(target, fixtures):
    for names, credential in fixtures:
        put_fixture(target.s3(credential), names)
    for index, (names, credential) in enumerate(fixtures):
        own = target.s3(credential)
        foreign = fixtures[1 - index][0]
        assert read_object(own, names.bucket, key(names)) == payload(names)
        assert key(names) in {
            obj.object_name for obj in own.list_objects(names.bucket, recursive=True)
        }
        # Prove DELETE on own objects, leaving the persistent cross-access canary intact.
        temporary = "_f01/delete/" + uuid4().hex
        own.put_object(names.bucket, temporary, io.BytesIO(b"synthetic"), 9)
        own.remove_object(names.bucket, temporary)
        try:
            read_object(own, names.bucket, temporary)
        except S3Error as error:
            assert error.code == "NoSuchKey"
        else:
            raise StorageError("STORAGE_INVALID")
        require_denied(
            lambda own=own, foreign=foreign: read_object(own, foreign.bucket, key(foreign))
        )
        require_denied(lambda own=own, foreign=foreign: list(own.list_objects(foreign.bucket)))
        require_denied(
            lambda own=own, foreign=foreign, names=names: own.put_object(
                foreign.bucket, "_f01/forbidden-" + names.tenant.hex, io.BytesIO(b"synthetic"), 9
            )
        )
        require_denied(
            lambda own=own, foreign=foreign: own.remove_object(foreign.bucket, key(foreign))
        )
        # This pinned release filters ListBuckets by per-bucket permissions.
        # Never permit another bucket in the response; no ListAllMyBuckets grant.
        if {bucket.name for bucket in own.list_buckets()} != {names.bucket}:
            raise StorageError("ISOLATION_FAILED")
        # This global admin read cannot be satisfied by tenant S3 privileges.
        try:
            target.admin(credential).user_list()
        except MinioAdminException as error:
            if admin_error(error) != "STORAGE_DENIED":
                raise StorageError("STORAGE_INVALID") from None
        else:
            raise StorageError("ISOLATION_FAILED")
        anon = target.s3()
        require_denied(lambda anon=anon, names=names: read_object(anon, names.bucket, key(names)))
        require_denied(lambda anon=anon, names=names: list(anon.list_objects(names.bucket)))
        require_denied(
            lambda anon=anon, names=names: anon.put_object(
                names.bucket, "_f01/anonymous", io.BytesIO(b"synthetic"), 9
            )
        )
    # Denied DELETE/PUT must leave the other tenant's synthetic object intact.
    for names, credential in fixtures:
        assert read_object(target.s3(credential), names.bucket, key(names)) == payload(names)


def collision(provisioner, names):
    ref = uuid5(names.tenant, "not-owned")
    s3 = provisioner.s3
    if not s3.bucket_exists(names.bucket):
        s3.make_bucket(names.bucket)
        from minio.commonconfig import Tags

        tags = Tags.new_bucket_tags()
        tags["synthetic-owner"] = "foreign"
        s3.set_bucket_tags(names.bucket, tags)
        put_fixture(s3, names)
    before_tags = dict(s3.get_bucket_tags(names.bucket) or {})
    before_value = read_object(s3, names.bucket, key(names))
    try:
        provisioner.provision(names, ref, Credential(names.user, secrets.token_urlsafe(36)))
    except StorageError as error:
        if str(error) != "OWNERSHIP_CONFLICT":
            raise
    else:
        raise StorageError("ISOLATION_FAILED")
    assert dict(s3.get_bucket_tags(names.bucket) or {}) == before_tags
    assert read_object(s3, names.bucket, key(names)) == before_value
    assert provisioner.optional_admin(provisioner.admin.user_info, names.user) is None
    assert provisioner.optional_admin(provisioner.admin.policy_info, names.policy) is None


def compatibility(target, provisioner):
    """Fresh non-tenant calibration only. No catalog, SecretStore replacement or production data."""
    global PHASE
    fixtures = []
    try:
        for _ in range(2):
            names, ref = StorageNames(uuid4()), uuid4()
            PHASE = "COMPAT_INSPECT"
            assert provisioner.inspect(names, ref) == (False, False, False)
            credential = Credential(names.user, secrets.token_urlsafe(36))
            PHASE = "COMPAT_PROVISION"
            provisioner.provision(names, ref, credential)
            fixtures.append((names, credential))
            provisioner.provision(names, ref, credential)
        PHASE = "COMPAT_PROBES"
        probes(target, fixtures)
        PHASE = "COMPAT_COLLISION"
        collision(provisioner, StorageNames(uuid4()))
        print("PASS compatibility: API MinioAdmin, TLS, políticas, objetos y denegaciones reales.")
    finally:
        # Disable only users successfully created/attributed by this calibration.
        # Retain synthetic buckets/policies; never delete foreign resources.
        for names, _ in fixtures:
            provisioner.admin.user_disable(names.user)
        if fixtures:
            print("Calibración: usuarios propios deshabilitados; fixtures conservadas.")


def tenants(target, provisioner, store):
    global PHASE
    sql_target = Target("postgres", 5432, CA)
    control = Credential(
        "f01_control_migrator", Path("/run/secrets/control_migrator_password").read_text()
    )
    engine = sa.create_engine(
        "postgresql+psycopg://",
        creator=lambda: sql_target.connect("rag_control", control),
        poolclass=NullPool,
        hide_parameters=True,
    )
    fixtures = []
    try:
        for tenant_id in TENANTS:
            names = StorageNames(tenant_id)
            PHASE = "STORAGE_RESERVE"
            with Session(engine) as session, session.begin():
                tenant = session.get(Tenant, tenant_id)
                if tenant is None or tenant.state != "PROVISIONING":
                    raise StorageError()
                location = session.get(StorageLocation, tenant_id)
                if location is None:
                    location = StorageLocation(
                        tenant_id=tenant_id,
                        endpoint=target.endpoint,
                        bucket=names.bucket,
                        credential_ref=uuid4(),
                        credential_version=1,
                    )
                    session.add(location)
                    session.flush()
                if location.endpoint != target.endpoint or location.bucket != names.bucket:
                    raise StorageError()
                ref = SecretRef(location.credential_ref, location.credential_version)
            PHASE = "STORAGE_INSPECT"
            state = provisioner.inspect(names, ref.id)
            PHASE = "STORAGE_SECRET"
            credential = credential_for(store, ref, names.user, resource_exists=any(state))
            PHASE = "STORAGE_PROVISION"
            provisioner.provision(names, ref.id, credential)
            provisioner.provision(names, ref.id, credential)
            assert store.read(ref) == credential
            fixtures.append((names, credential))
        PHASE = "STORAGE_PROBES"
        probes(target, fixtures)
        PHASE = "STORAGE_COLLISION"
        collision(provisioner, StorageNames(uuid5(NAMESPACE, "s3-foreign-bucket-fixture")))
        print("PASS T003: buckets privados A/B, credenciales OpenBao y referencias versionadas.")
        print("PASS T003: get/put/list/delete propios; cruces y anónimo denegados; sin admin.")
        print("PASS T003: repetición sin rotación y recurso ajeno conservado.")
        print("Tenants PROVISIONING; sin READY, saga ni cierre de F01.")
    finally:
        engine.dispose()


def main():
    global PHASE
    logging.disable(logging.CRITICAL)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("compatibility", "tenants"))
    args = parser.parse_args()
    target = None
    try:
        if args.mode == "tenants":
            tty_required()
        target = StorageTarget(STORAGE_ENDPOINT, CA)
        provisioner = StorageProvisioner(target, admin_credential())
        if args.mode == "compatibility":
            compatibility(target, provisioner)
        else:
            PHASE = "BAO_STATUS"
            with client() as http:
                require_unsealed(http)
                PHASE = "OPERATOR_LOGIN"
                operator = login_operator(http)
                try:
                    PHASE = "APPROLE_ISSUE"
                    own = call(http, "GET", "auth/token/lookup-self", operator)["data"]
                    if set(own["policies"]) != {"default", "f01-operator"}:
                        raise StorageError("STORAGE_DENIED")
                    role = call(http, "GET", "auth/approle/role/f01-cli/role-id", operator)["data"][
                        "role_id"
                    ]
                    secret_id = call(
                        http, "POST", "auth/approle/role/f01-cli/secret-id", operator, {}
                    )["data"]["secret_id"]
                    with OpenBaoSecretStore(ENDPOINT, CA) as store:
                        PHASE = "APPROLE_LOGIN"
                        store.login(role, secret_id)
                        del secret_id
                        tenants(target, provisioner, store)
                finally:
                    call(http, "POST", "auth/token/revoke-self", operator, {})
    except OperatorFailure as error:
        raise SystemExit(f"F01-T003 {PHASE}: F01-{error.code}.") from None
    except SecretStoreError as error:
        raise SystemExit(f"F01-T003 {PHASE}: {error.code.value}.") from None
    except StorageError as error:
        raise SystemExit(f"F01-T003 {PHASE}: {error}. Recursos conservados.") from None
    except MinioAdminException as error:
        raise SystemExit(f"F01-T003 {PHASE}: {admin_error(error)}.") from None
    except S3Error as error:
        code = (
            error.code
            if error.code in {"AccessDenied", "NoSuchKey", "NoSuchBucket", "SignatureDoesNotMatch"}
            else "STORAGE_FAILED"
        )
        raise SystemExit(f"F01-T003 {PHASE}: {code}.") from None
    except DBAPIError as error:
        code = getattr(error.orig, "sqlstate", None)
        code = code if isinstance(code, str) and len(code) == 5 and code.isalnum() else "SQL_FAILED"
        raise SystemExit(f"F01-T003 {PHASE}: {code}.") from None
    except (Exception, KeyboardInterrupt):
        raise SystemExit(f"F01-T003 {PHASE}: operación detenida; sin detalles sensibles.") from None
    finally:
        if target:
            target.close()


if __name__ == "__main__":
    main()
