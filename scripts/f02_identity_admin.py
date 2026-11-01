"""OIDC-authenticated internal administration. Tokens only through private files."""

import argparse
import json
import logging
import os
import stat
from pathlib import Path
from uuid import UUID, uuid4

from f02_common import engine

from rag_platform.control.identity import AccessError, audit, register
from rag_platform.control.identity_admin import IdentityAdministration
from rag_platform.providers.identity import IdentityError, OIDCSettings, OIDCVerifier


class Parser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("allow_abbrev", False)
        super().__init__(*args, **kwargs)

    def error(self, message):
        self.exit(2, "F02-CLI INPUT_INVALID\n")


def read_token(path):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        raise AccessError("INPUT_INVALID") from None
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_nlink != 1
            or not 0 < info.st_size <= 16384
        ):
            raise AccessError("INPUT_INVALID")
        with os.fdopen(fd, closefd=False) as stream:
            return stream.read().strip()
    finally:
        os.close(fd)


def settings():
    return OIDCSettings(
        os.environ["RAG_OIDC_ISSUER"],
        os.environ["RAG_OIDC_AUDIENCE"],
        os.environ["RAG_OIDC_JWKS"],
        Path("/tls/ca.crt"),
        leeway=0,
    )


def infrastructure():
    # Only the explicit bootstrap profile mounts this private 24h authorization.
    from f01_daily import session
    from f01_operator import CANARY

    from rag_platform.providers.secrets import Credential
    from rag_platform.tenancy.contracts import SecretRef

    with session() as (store, _role, _used):
        if store.read(SecretRef(CANARY, 1)) != Credential("f01-canary", "synthetic-not-an-account"):
            raise AccessError("ROLE_DENIED")


def parser():
    p = Parser(allow_abbrev=False)
    p.add_argument("--token-file", type=Path, required=True)
    sub = p.add_subparsers(dest="command", required=True, parser_class=Parser)
    sub.add_parser("me")
    sub.add_parser("bootstrap-operator")
    owner = sub.add_parser("bootstrap-owner")
    owner.add_argument("--tenant", type=UUID, required=True)
    owner.add_argument("--user", type=UUID, required=True)
    owner.add_argument("--kind", choices=["PERSONAL", "ORG"], required=True)
    membership = sub.add_parser("membership")
    membership.add_argument("--tenant", type=UUID, required=True)
    membership.add_argument("--user", type=UUID, required=True)
    membership.add_argument("--role", choices=["owner", "admin", "editor", "reader"], required=True)
    membership.add_argument("--state", choices=["ACTIVE", "SUSPENDED", "REVOKED"], default="ACTIVE")
    platform = sub.add_parser("platform-role")
    platform.add_argument("--user", type=UUID, required=True)
    platform.add_argument(
        "--role", choices=["platform_operator", "platform_support"], required=True
    )
    platform.add_argument("--state", choices=["ACTIVE", "REVOKED"], default="ACTIVE")
    user = sub.add_parser("principal-state")
    user.add_argument("--user", type=UUID, required=True)
    user.add_argument("--state", choices=["ACTIVE", "SUSPENDED"], required=True)
    return p


def main():
    args = parser().parse_args()
    request = uuid4()
    app = admin = None
    try:
        app = engine()
        with_verifier = OIDCVerifier(settings())
        try:
            principal = register(app, with_verifier.verify(read_token(args.token_file)), request)
        finally:
            with_verifier.close()
        admin = engine("admin")
        service = IdentityAdministration(admin, principal, request)
        if args.command == "me":
            result = service.me()
        elif args.command == "bootstrap-operator":
            infrastructure()
            result = service.bootstrap_operator(infrastructure_authorized=True)
        elif args.command == "bootstrap-owner":
            result = service.bootstrap_owner(args.tenant, args.user, args.kind)
        elif args.command == "membership":
            result = service.membership(args.tenant, args.user, args.role, args.state)
        elif args.command == "platform-role":
            result = service.platform_role(args.user, args.role, args.state)
        else:
            result = service.principal_state(args.user, args.state)
        print(
            json.dumps(
                {"status": "OK", "request_id": str(request), "result": result}, sort_keys=True
            )
        )
        return 0
    except Exception as error:
        if isinstance(error, (IdentityError, AccessError)):
            code = error.code
        else:
            code = "CATALOG_UNAVAILABLE"
        if app is not None and isinstance(error, IdentityError):
            try:
                with app.begin() as c:
                    audit(
                        c,
                        request_id=request,
                        event="AUTH_DENIED",
                        outcome="DENIED",
                        reason="TOKEN_INVALID"
                        if code == "INVALID_TOKEN"
                        else "DEPENDENCY_UNAVAILABLE",
                    )
            except Exception:
                pass
        print(json.dumps({"status": "DENIED", "request_id": str(request), "code": code}))
        return 1
    finally:
        for e in (app, admin):
            if e is not None:
                e.dispose()


if __name__ == "__main__":
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    raise SystemExit(main())
