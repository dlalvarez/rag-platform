"""Reusable 24-hour development session; operator password never persisted."""

import json
import logging
import os
import stat
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from f01_access import AccessError, Parser, directory
from f01_operator import (
    CA,
    CANARY,
    ENDPOINT,
    call,
    client,
    login_operator,
    require_unsealed,
    tty_required,
)

from rag_platform.providers.secrets import Credential, OpenBaoSecretStore
from rag_platform.tenancy.contracts import SecretRef

ROLE = "f01-dev-day"
SECONDS = 86400
NAME = "day.json"
ROLE_SETTINGS = {
    "bind_secret_id": True,
    "secret_id_ttl": 600,
    "secret_id_num_uses": 1,
    "token_policies": ["f01-provisioner"],
    "token_ttl": SECONDS,
    "token_max_ttl": SECONDS,
    "token_explicit_max_ttl": SECONDS,
    "token_num_uses": 0,
    "token_period": 0,
    "token_type": "service",
    "token_no_default_policy": False,
}


def read_day(parent):
    fd = os.open(NAME, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_nlink != 1
            or not 0 < info.st_size <= 8192
        ):
            raise AccessError()
        with os.fdopen(fd, closefd=False) as source:
            result = json.load(source)
    finally:
        os.close(fd)
    if (
        not isinstance(result, dict)
        or set(result) != {"token", "expires_at"}
        or not isinstance(result["token"], str)
        or not 0 < len(result["token"]) <= 4096
        or type(result["expires_at"]) not in (float, int)
        or not time.time() < result["expires_at"] <= time.time() + SECONDS
    ):
        raise AccessError()
    return result


@contextmanager
def session():
    # Serialize entire batteries with revocation/replacement in this private directory.
    with directory() as parent:
        day = read_day(parent)
        with OpenBaoSecretStore(ENDPOINT, CA) as store:
            store.attach_day(day["token"], day["expires_at"])
            yield store, None, None
            # Keep server authorization for the next independent process until deadline.
            # __exit__ clears this local client's memory; revoke is explicit for the day.


def details(expiry):
    return {
        "state": "ACTIVE",
        "expires_at": datetime.fromtimestamp(expiry, timezone(timedelta(hours=-5))).isoformat(),
        "remaining_seconds": max(0, int(expiry - time.time())),
    }


def mint(http, operator):
    role = call(http, "GET", f"auth/approle/role/{ROLE}/role-id", operator)["data"]["role_id"]
    secret = call(http, "POST", f"auth/approle/role/{ROLE}/secret-id", operator, {})["data"]
    if secret["secret_id_num_uses"] != 1 or secret["secret_id_ttl"] != 600:
        raise AccessError()
    auth = call(
        http,
        "POST",
        "auth/approle/login",
        payload={
            "role_id": role,
            "secret_id": secret["secret_id"],
        },
    )["auth"]
    token = auth["client_token"]
    try:
        if set(auth["policies"]) != {"default", "f01-provisioner"}:
            raise AccessError()
        if type(auth["lease_duration"]) is not int or auth["lease_duration"] != SECONDS:
            raise AccessError()
        own = call(http, "GET", "auth/token/lookup-self", token)["data"]
        expiry = own["creation_time"] + SECONDS
        with OpenBaoSecretStore(ENDPOINT, CA) as store:
            store.attach_day(token, expiry)
        return {"token": token, "expires_at": expiry}
    except BaseException:
        revoke_token(http, token)
        raise


def revoke_token(http, token):
    call(http, "POST", "auth/token/revoke-self", token, {})
    if http.get("/v1/auth/token/lookup-self", headers={"X-Vault-Token": token}).status_code != 403:
        raise AccessError()


def start(*, password=None, trial=False):
    # password argument is only used by the operator's stdin bridge during setup.
    if password is None:
        tty_required()
    with directory() as parent:
        try:
            os.stat(NAME, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise AccessError()  # Never overwrite an active or unexamined prior session.
        with client() as http:
            require_unsealed(http)
            operator = (
                login_operator(http)
                if password is None
                else call(
                    http, "POST", "auth/userpass/login/diego", payload={"password": password}
                )["auth"]["client_token"]
            )
            day = None
            written = False
            try:
                own = call(http, "GET", "auth/token/lookup-self", operator)["data"]
                if set(own["policies"]) != {"default", "f01-operator"}:
                    raise AccessError()
                if trial:
                    probe = mint(http, operator)
                    revoke_token(http, probe["token"])
                    del probe
                day = mint(http, operator)
                fd = os.open(
                    NAME,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=parent,
                )
                try:
                    with os.fdopen(fd, "w") as output:
                        json.dump(day, output)
                    written = True
                except BaseException:
                    os.unlink(NAME, dir_fd=parent)
                    raise
            finally:
                try:
                    revoke_token(http, operator)
                except BaseException:
                    if written:
                        os.unlink(NAME, dir_fd=parent)
                        written = False
                    raise
                finally:
                    if day is not None and not written:
                        revoke_token(http, day["token"])
        return details(day["expires_at"])


def verify():
    with session() as (store, _role, _used):
        if store.read(SecretRef(CANARY, 1)) != Credential("f01-canary", "synthetic-not-an-account"):
            raise AccessError()
    print("PASS DAY: canary real; sesión diaria conservada para otra ejecución.")


def status():
    with directory() as parent:
        day = read_day(parent)
        with OpenBaoSecretStore(ENDPOINT, CA) as store:
            store.attach_day(day["token"], day["expires_at"])
        print(json.dumps(details(day["expires_at"]), sort_keys=True))


def revoke():
    with directory() as parent:
        # Expired local entries still need a server check before removing their token.
        fd = os.open(NAME, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_nlink != 1
                or not 0 < info.st_size <= 8192
            ):
                raise AccessError()
            with os.fdopen(fd, closefd=False) as source:
                day = json.load(source)
        finally:
            os.close(fd)
        if not isinstance(day, dict) or set(day) != {"token", "expires_at"}:
            raise AccessError()
        if not isinstance(day["token"], str) or not 0 < len(day["token"]) <= 4096:
            raise AccessError()
        with client() as http:
            response = http.get(
                "/v1/auth/token/lookup-self", headers={"X-Vault-Token": day["token"]}
            )
            if response.status_code == 200:
                # Validate origin before revoking any live token supplied in a local file.
                with OpenBaoSecretStore(ENDPOINT, CA) as store:
                    store.attach_day(day["token"], day["expires_at"])
                    store.revoke()
            elif response.status_code != 403:
                raise AccessError()
        os.unlink(NAME, dir_fd=parent)
    print("PASS DAY REVOKE: token rechazado por OpenBao; copia local eliminada.")


def main(argv=None):
    logging.disable(logging.CRITICAL)
    parser = Parser(description=__doc__, allow_abbrev=False)
    parser.add_argument("command", choices=("start", "status", "verify", "revoke", "cli-check"))
    args = parser.parse_args(argv)
    try:
        if args.command == "start":
            print(json.dumps(start(), sort_keys=True))
        elif args.command == "status":
            status()
        elif args.command == "verify":
            verify()
        elif args.command == "revoke":
            revoke()
        else:
            from f01_cli_check import main as battery

            battery(daily=True)
            print(
                "PASS DAY CLI: batería completada; sesión diaria disponible hasta su vencimiento."
            )
    except (Exception, KeyboardInterrupt):
        raise SystemExit("F01-DAY REFUSED; sin detalles sensibles ni fallback.") from None


if __name__ == "__main__":
    main()
