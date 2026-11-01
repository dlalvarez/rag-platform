"""Trusted daily operator issues only the fixed F03 application identity into tmpfs."""

import argparse
import json
import logging
import os
import time
from pathlib import Path

from f01_daily import session
from f01_operator import CA, ENDPOINT

from rag_platform.providers.application_handoff import (
    NAME,
    directory,
    lock_file,
    publish,
    read_record,
)
from rag_platform.providers.application_secrets import ROLE, ApplicationSecretStore

DELIVERY = Path("/run/f03-application")


def ensure(day, path=DELIVERY, *, replace=False):
    fd = directory(path)
    os.close(fd)
    lock = lock_file(path / "issuer.lock")
    try:
        destination = path / NAME
        if destination.exists() or destination.is_symlink():
            record = read_record(destination)
            if not replace and record["expires_at"] > time.time() + 120:
                with ApplicationSecretStore(ENDPOINT, CA) as current:
                    current.attach_application(record["token"])
                return {"state": "ACTIVE", "expires_at": record["expires_at"], "created": False}
        role = day._request("GET", f"/v1/auth/approle/role/{ROLE}/role-id")["data"]["role_id"]
        grant = day._request("POST", f"/v1/auth/approle/role/{ROLE}/secret-id", json={})["data"]
        if grant["secret_id_num_uses"] != 1 or grant["secret_id_ttl"] != 600:
            raise ValueError()
        store = ApplicationSecretStore(ENDPOINT, CA)
        published = False
        try:
            store.login(role, grant["secret_id"])
            del grant, role
            now = time.time()
            ttl = min(3599, store._store._expires_at - time.monotonic())
            if ttl <= 120:
                raise ValueError()
            record = {
                "version": 1,
                "token": store._store._token,
                "issued_at": now,
                "expires_at": now + ttl,
            }
            publish(path, record)
            published = True
            store._store._token, store._store._expires_at = None, 0.0
            return {"state": "ACTIVE", "expires_at": record["expires_at"], "created": True}
        finally:
            try:
                if not published:
                    store.revoke()
            finally:
                store.close()
    finally:
        os.close(lock)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["ensure", "replace"])
    args = parser.parse_args()
    with session() as (day, _, _):
        return ensure(day, replace=args.action == "replace")


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    try:
        print(json.dumps(main(), sort_keys=True))
    except (Exception, KeyboardInterrupt):
        raise SystemExit("F03 HANDOFF: REFUSED; sin detalles sensibles.") from None
