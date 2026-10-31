"""T007 CLI parser/dispatch battery; run from the clean clone's fixed tools image."""

import json
import logging
from uuid import UUID, uuid4, uuid5

import sqlalchemy as sa
from f01_admin import (
    CA,
    ROOT,
    AdminError,
    Administration,
    execute,
    operator_service,
    parser,
    tty_required,
)
from f01_operator import OperatorFailure
from minio.error import S3Error
from sqlalchemy.orm import Session

from rag_platform.providers.secrets import SecretStoreError
from rag_platform.provisioning.migrations import MigrationError
from rag_platform.provisioning.saga import SagaError
from rag_platform.provisioning.storage import StorageError
from rag_platform.tenancy.resolver import TenantAccessError

NAMESPACE = UUID("c7e6e4fa-0d79-4bd9-8ba7-4f242a9b4f9b")
PHASE = "START"


def command(service, *argv):
    # Same parser and dispatcher used by the operator CLI, with one authenticated session.
    return execute(parser().parse_args(list(argv)), service)


def credential_values(service, tenant):
    snap, _ = service.snapshot(tenant)
    return tuple(service.store.read(ref) for ref in (*snap.sql_refs, snap.storage_ref))


def main(*, delegated=False):
    global PHASE
    logging.disable(logging.CRITICAL)
    try:
        if not delegated:
            tty_required()
        with (
            operator_service("create", delegated=True)
            if delegated
            else operator_service("create") as service
        ):
            PHASE = "CATALOG_SHOW"
            instances = command(service, "show", "--instances")
            selected = {i["host"]: i["instance"] for i in instances}
            assert {"postgres", "postgres2"} <= set(selected)
            before_factory = service.backend_factory
            PHASE = "CREATE_FAILURE"

            def faulty(snapshot):
                backend = before_factory(snapshot)

                def fail_bucket():
                    try:
                        service.storage.s3().make_bucket(backend.storage_names.bucket)
                    except S3Error as error:
                        if error.code == "AccessDenied":
                            raise StorageError("STORAGE_DENIED") from None
                        raise
                    raise AssertionError("Unsigned bucket creation accepted")

                backend.storage = fail_bucket
                return backend

            # Fresh primary fixture ensures every battery actually injects a failure.
            key = uuid4()
            service.backend_factory = faulty
            try:
                command(service, "create", "--instance", selected["postgres"], "--key", str(key))
            except SagaError as error:
                assert error.code == "STORAGE_FAILED"
            else:
                raise AssertionError("Injected failure did not reach CLI")
            finally:
                service.backend_factory = before_factory
            from rag_platform.control.models import ProvisioningOperation

            with Session(service.engine) as session:
                operation = session.scalar(
                    sa.select(ProvisioningOperation).where(
                        ProvisioningOperation.idempotency_key == key
                    )
                )
                tenant = operation.tenant_id
            failed = command(service, "show", "--tenant", str(tenant))
            assert failed["state"] == "FAILED"
            initial = credential_values(service, tenant)
            PHASE = "RETRY_IDEMPOTENCY"
            ready = command(service, "retry", "--tenant", str(tenant))
            assert ready["state"] == "READY"
            repeated = command(
                service, "create", "--instance", selected["postgres"], "--key", str(key)
            )
            assert repeated == ready and credential_values(service, tenant) == initial
            assert ready["operation"]["attempts"] == 2
            assert failed["operation"]["id"] == ready["operation"]["id"]
            print(
                "PASS T007: create/show/retry; fallo real sin READY y "
                "recuperación idempotente sin rotación."
            )

            PHASE = "CHECK_MIGRATE"
            # No IAM administrator credential supplied to check/migrate service.
            restricted = Administration(
                service.engine, service.actor, service.store, CA, service.storage, ROOT
            )
            assert command(restricted, "check", "--tenant", str(tenant))["check"] == "PASS"
            assert command(restricted, "migrate", "--tenant", str(tenant))["migration"] == "PASS"
            assert command(restricted, "migrate", "--tenant", str(tenant))["migration"] == "PASS"
            assert command(restricted, "check", "--tenant", str(tenant))["check"] == "PASS"
            try:
                command(restricted, "retry", "--tenant", str(uuid4()))
            except AdminError as error:
                assert error.code == "UNKNOWN_TENANT"
            else:
                raise AssertionError("Unknown retry reserved resources")
            print(
                "PASS T007: check y migrate repetidos sin admin IAM; "
                "desconocido rechazado sin alta."
            )

            PHASE = "SECOND_INSTANCE"
            second_key = uuid5(NAMESPACE, "secondary-cli-fixture")
            second = command(
                service, "create", "--instance", selected["postgres2"], "--key", str(second_key)
            )
            assert second["state"] == "READY"
            assert command(restricted, "check", "--tenant", second["tenant"])["check"] == "PASS"
            assert (
                command(restricted, "migrate", "--tenant", second["tenant"])["migration"] == "PASS"
            )
            assert command(restricted, "check", "--tenant", second["tenant"])["check"] == "PASS"
            assert credential_values(service, tenant) == initial
            output = json.dumps([ready, second], sort_keys=True)
            assert not any(word in output for word in ("password", "client_token", "secret_id"))
            print(
                "PASS T007: CLI en ambas instancias; versiones reales, "
                "salidas sin valores de secretos."
            )
            print("T007: batería CLI completada; esta ejecución no cambia la aceptación de fase.")
    except (AdminError, MigrationError, SagaError, TenantAccessError) as error:
        raise SystemExit(f"F01-T007 {PHASE}: {error.code}; recursos conservados.") from None
    except SecretStoreError as error:
        raise SystemExit(f"F01-T007 {PHASE}: {error.code.value}.") from None
    except OperatorFailure as error:
        raise SystemExit(f"F01-T007 {PHASE}: F01-{error.code}.") from None
    except (Exception, KeyboardInterrupt):
        raise SystemExit(f"F01-T007 {PHASE}: CHECK_FAILED; sin detalles sensibles.") from None


if __name__ == "__main__":
    main()
