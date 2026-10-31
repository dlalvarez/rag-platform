"""One-use, short-lived AppRole handoff; never accepts an operator password in automation."""

import argparse
import fcntl
import json
import logging
import os
import stat
import time
from contextlib import contextmanager
from pathlib import Path

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

DIRECTORY = Path("/run/f01-access")
NAME = "grant.json"
PURPOSES = ("verify", "cli-check")


class AccessError(RuntimeError):
    def __init__(self):
        super().__init__("F01-ACCESS REFUSED; sin detalles sensibles ni fallback.")


@contextmanager
def directory():
    fd = os.open(DIRECTORY, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise AccessError()
        # Linux directory inode lock serializes issue/consume/discard across containers.
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield fd
    finally:
        os.close(fd)


def consume(purpose):
    with directory() as parent:
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
            # Claim before parsing or networking; no retry with the same material.
            os.unlink(NAME, dir_fd=parent)
            with os.fdopen(fd, "r", closefd=False) as source:
                grant = json.load(source)
        finally:
            os.close(fd)
    if not isinstance(grant, dict) or set(grant) != {
        "purpose",
        "issued_at",
        "expires_at",
        "role_id",
        "secret_id",
    }:
        raise AccessError()
    issued, expiry = grant["issued_at"], grant["expires_at"]
    if (
        purpose not in PURPOSES
        or grant["purpose"] != purpose
        or type(issued) not in (int, float)
        or type(expiry) not in (int, float)
        or not issued <= time.time() < expiry <= issued + 600
        or not all(
            isinstance(grant[k], str) and 0 < len(grant[k]) <= 4096
            for k in ("role_id", "secret_id")
        )
    ):
        raise AccessError()
    return grant["role_id"], grant["secret_id"]


def issue(purpose):
    tty_required()
    # Lock before authentication; refuse existing files without overwriting them.
    with directory() as parent:
        try:
            os.stat(NAME, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise AccessError()
        with client() as http:
            require_unsealed(http)
            operator = login_operator(http)
            try:
                own = call(http, "GET", "auth/token/lookup-self", operator)["data"]
                if set(own["policies"]) != {"default", "f01-operator"}:
                    raise AccessError()
                role = call(http, "GET", "auth/approle/role/f01-cli/role-id", operator)["data"][
                    "role_id"
                ]
                issued = time.time()
                data = call(http, "POST", "auth/approle/role/f01-cli/secret-id", operator, {})[
                    "data"
                ]
                ttl = data["secret_id_ttl"]
                if (
                    type(ttl) is not int
                    or not 0 < ttl <= 600
                    or data["secret_id_num_uses"] != 1
                    or not all(
                        isinstance(v, str) and 0 < len(v) <= 4096 for v in (role, data["secret_id"])
                    )
                ):
                    raise AccessError()
                body = json.dumps(
                    {
                        "purpose": purpose,
                        "issued_at": issued,
                        "expires_at": issued + ttl,
                        "role_id": role,
                        "secret_id": data["secret_id"],
                    }
                )
                fd = os.open(
                    NAME,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=parent,
                )
                try:
                    with os.fdopen(fd, "w") as output:
                        output.write(body)
                except BaseException:
                    os.unlink(NAME, dir_fd=parent)
                    raise
                del body, data
            finally:
                call(http, "POST", "auth/token/revoke-self", operator, {})
    print("PASS ACCESS ISSUE: autorización de un uso preparada; caducidad máxima 10 minutos.")


@contextmanager
def session(purpose):
    role, secret_id = consume(purpose)
    with OpenBaoSecretStore(ENDPOINT, CA) as store:
        try:
            store.login(role, secret_id)
            yield store, role, secret_id
        finally:
            # Explicit revoke, not merely clearing the in-memory bearer.
            store.revoke()


def verify():
    with client() as http:
        require_unsealed(http)
    with session("verify") as (store, role, used):
        if store.read(SecretRef(CANARY, 1)) != Credential("f01-canary", "synthetic-not-an-account"):
            raise AccessError()
        with client() as http:
            rejected = http.post(
                "/v1/auth/approle/login", json={"role_id": role, "secret_id": used}
            )
            if rejected.status_code not in (400, 403):
                raise AccessError()
    print("PASS ACCESS: canary real, SecretID consumido rechazado y token revocado verificado.")


def discard():
    with directory() as parent:
        try:
            os.unlink(NAME, dir_fd=parent)
        except FileNotFoundError:
            pass
    print("PASS ACCESS DISCARD: copia local eliminada; SecretID no usado caduca en OpenBao.")


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "F01-ACCESS INPUT_INVALID; consulta --help.\n")


def main(argv=None):
    logging.disable(logging.CRITICAL)
    parser = Parser(description=__doc__, allow_abbrev=False)
    commands = parser.add_subparsers(dest="command", required=True)
    issuing = commands.add_parser("issue")
    issuing.add_argument("--purpose", choices=PURPOSES, default="verify")
    for name in (*PURPOSES, "discard"):
        commands.add_parser(name)
    args = parser.parse_args(argv)
    try:
        if args.command == "issue":
            issue(args.purpose)
        elif args.command == "verify":
            verify()
        elif args.command == "discard":
            discard()
        else:
            from f01_cli_check import main as battery

            battery(delegated=True)
            print("PASS ACCESS CLI: batería delegada completada y token revocado verificado.")
    except (Exception, KeyboardInterrupt):
        raise SystemExit("F01-ACCESS REFUSED; sin detalles sensibles ni fallback.") from None


if __name__ == "__main__":
    main()
