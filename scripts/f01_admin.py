"""CLI administrativa F01: create/show/check/retry/migrate. Solo frontera SSH."""

import argparse
import json
import logging
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid5

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

from rag_platform.providers.secrets import Credential, OpenBaoSecretStore, SecretStoreError
from rag_platform.provisioning.administration import AdminError, Administration
from rag_platform.provisioning.migrations import MigrationError
from rag_platform.provisioning.postgres import Target
from rag_platform.provisioning.saga import SagaError
from rag_platform.provisioning.storage import StorageTarget
from rag_platform.tenancy.resolver import TenantAccessError, control_engine

ROOT = Path(__file__).resolve().parents[1]
ACTOR = uuid5(UUID("310bf4df-1c98-4a15-a7a3-46d979774f17"), "openbao-userpass-diego")
DELEGATED_ACTOR = uuid5(
    UUID("310bf4df-1c98-4a15-a7a3-46d979774f17"), "openbao-approle-f01-cli-delegated"
)
STORAGE_ENDPOINT = "https://minio:9000"


class Parser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("allow_abbrev", False)
        super().__init__(*args, **kwargs)

    def error(self, message):
        self.exit(2, "F01-ADMIN INPUT_INVALID; consulta --help.\n")


def parser():
    result = Parser(description=__doc__, allow_abbrev=False)
    commands = result.add_subparsers(dest="command", required=True, parser_class=Parser)
    create = commands.add_parser("create", help="Crear o retomar una clave idempotente")
    create.add_argument("--instance", type=UUID, required=True)
    create.add_argument("--key", type=UUID, required=True)
    show = commands.add_parser("show", help="Mostrar metadatos sin valores de secretos")
    choice = show.add_mutually_exclusive_group(required=True)
    choice.add_argument("--tenant", type=UUID)
    choice.add_argument("--instances", action="store_true")
    for name in ("check", "retry", "migrate"):
        command = commands.add_parser(name)
        command.add_argument("--tenant", type=UUID, required=True)
    return result


def execute(arguments, service):
    if arguments.command == "show":
        return service.instances() if arguments.instances else service.show(arguments.tenant)
    if arguments.command == "create":
        return service.create(arguments.instance, arguments.key)
    return getattr(service, arguments.command)(arguments.tenant)


def catalog():
    credential = Credential(
        "f01_control_migrator", Path("/run/secrets/control_migrator_password").read_text()
    )
    return control_engine(Target("postgres", 5432, CA), credential)


@contextmanager
def operator_service(command, *, delegated=False):
    # Interactive callers verify TTY; delegated callers require an explicit one-use grant.
    control = storage = None
    try:
        control = catalog()
        storage = StorageTarget(STORAGE_ENDPOINT, CA)
        admin = None
        if command in ("create", "retry"):
            admin = Credential(
                Path("/run/secrets/storage_admin_user").read_text(),
                Path("/run/secrets/storage_admin_password").read_text(),
            )
        with client() as http:
            require_unsealed(http)
            if delegated:
                from f01_access import session

                with session("cli-check") as (store, _role, _used):
                    yield Administration(
                        control, DELEGATED_ACTOR, store, CA, storage, ROOT, storage_admin=admin
                    )
                return
            operator = login_operator(http)
            try:
                policies = call(http, "GET", "auth/token/lookup-self", operator)["data"]["policies"]
                if set(policies) != {"default", "f01-operator"}:
                    raise AdminError("CONFIG_UNAVAILABLE")
                with OpenBaoSecretStore(ENDPOINT, CA) as store:
                    role = call(http, "GET", "auth/approle/role/f01-cli/role-id", operator)["data"][
                        "role_id"
                    ]
                    secret_id = call(
                        http, "POST", "auth/approle/role/f01-cli/secret-id", operator, {}
                    )["data"]["secret_id"]
                    store.login(role, secret_id)
                    del secret_id
                    yield Administration(
                        control, ACTOR, store, CA, storage, ROOT, storage_admin=admin
                    )
            finally:
                call(http, "POST", "auth/token/revoke-self", operator, {})
    finally:
        if control is not None:
            control.dispose()
        if storage is not None:
            storage.close()


def main(argv=None):
    logging.disable(logging.CRITICAL)
    args = parser().parse_args(argv)
    control = None
    try:
        if args.command == "show":
            control = catalog()
            service = Administration(control, ACTOR, None, CA, None, ROOT)
            output = execute(args, service)
        else:
            tty_required()
            with operator_service(args.command) as service:
                output = execute(args, service)
        print(json.dumps(output, sort_keys=True))
        return 0
    except (AdminError, MigrationError, SagaError, TenantAccessError) as error:
        raise SystemExit(f"F01-ADMIN {args.command}: {error.code}; recursos conservados.") from None
    except SecretStoreError as error:
        raise SystemExit(f"F01-ADMIN {args.command}: {error.code.value}.") from None
    except OperatorFailure as error:
        raise SystemExit(f"F01-ADMIN {args.command}: F01-{error.code}.") from None
    except (Exception, KeyboardInterrupt):
        raise SystemExit(
            f"F01-ADMIN {args.command}: OPERATION_STOPPED; sin detalles sensibles."
        ) from None
    finally:
        if control is not None:
            control.dispose()


if __name__ == "__main__":
    main()
