"""Isolated OpenBao-only proof. No production endpoints or operator credentials."""

import json
import logging
import os
from uuid import UUID

from f01_daily import ROLE_SETTINGS
from f01_daily_setup import recover, wait_active
from f01_operator import CA, ENDPOINT, call, client
from f03_application_setup import ROOT, configure

from rag_platform.providers.application_secrets import ApplicationSecretStore
from rag_platform.providers.secrets import SecretStoreError
from rag_platform.tenancy.contracts import SecretRef


def prove():
    if os.environ.get("F03_ISOLATED_PROOF") != "1":
        raise RuntimeError("ISOLATED_ONLY")
    with client() as http:
        # An isolated, empty server only. Never adopt an initialized service.
        wait_active_uninitialized(http)
        state = call(http, "GET", "sys/seal-status")
        if state["initialized"]:
            raise RuntimeError("ALREADY_INITIALIZED")
        init = call(http, "POST", "sys/init", payload={"secret_shares": 1, "secret_threshold": 1})
        key, root = init["keys_base64"][0], init["root_token"]
        del init
        call(http, "POST", "sys/unseal", payload={"key": key})
        wait_active(http)
        call(http, "POST", "sys/mounts/f01", root, {"type": "kv", "options": {"version": "2"}})
        call(http, "POST", "sys/auth/approle", root, {"type": "approle"})
        baseline = (ROOT / "ops/f01/provisioner.hcl").read_text()
        call(http, "PUT", "sys/policies/acl/f01-provisioner", root, {"policy": baseline})
        call(
            http,
            "PUT",
            "sys/policies/acl/f01-operator",
            root,
            {"policy": (ROOT / "ops/f01/operator-day.hcl").read_text()},
        )
        call(
            http,
            "POST",
            "auth/approle/role/f01-cli",
            root,
            {
                **ROLE_SETTINGS,
                "token_ttl": 900,
                "token_max_ttl": 3600,
                "token_explicit_max_ttl": 3600,
            },
        )
        call(http, "POST", "auth/approle/role/f01-dev-day", root, ROLE_SETTINGS)
        role = call(http, "GET", "auth/approle/role/f01-dev-day/role-id", root)["data"]["role_id"]
        secret = call(http, "POST", "auth/approle/role/f01-dev-day/secret-id", root, {})["data"][
            "secret_id"
        ]
        day = call(
            http,
            "POST",
            "auth/approle/login",
            payload={
                "role_id": role,
                "secret_id": secret,
            },
        )["auth"]["client_token"]
        scope = json.loads((ROOT / "ops/f03/application-scope.json").read_text())
        refs = [UUID(ref) for fixture in scope["fixtures"] for ref in fixture["refs"]]
        infra = UUID("ab05245c-d070-486c-9cb4-088bd419cd6e")
        for ref in [*refs, infra]:
            call(
                http,
                "POST",
                f"f01/data/{ref}",
                root,
                {
                    "options": {"cas": 0},
                    "data": {"username": "synthetic-v1", "password": "synthetic"},
                },
            )
        call(
            http,
            "POST",
            f"f01/data/{refs[0]}",
            root,
            {"options": {"cas": 1}, "data": {"username": "synthetic-v2", "password": "synthetic"}},
        )
        before = http.get(
            "/v1/auth/approle/role/f03-application/role-id", headers={"X-Vault-Token": day}
        )
        if before.status_code != 403:
            raise RuntimeError("BASELINE_NOT_DENIED")
        call(http, "POST", "auth/token/revoke-self", root, {})
        if (
            http.get("/v1/auth/token/lookup-self", headers={"X-Vault-Token": root}).status_code
            != 403
        ):
            raise RuntimeError("INITIAL_ROOT_NOT_REVOKED")
        del root
        # Actual recovery ceremony, root-only fixed bootstrap, verified revocation.
        recover(http, key, configure_action=configure)
        recover(http, key, configure_action=configure)
        del key
        role = call(http, "GET", "auth/approle/role/f03-application/role-id", day)["data"][
            "role_id"
        ]
        issued = call(http, "POST", "auth/approle/role/f03-application/secret-id", day, {})["data"]
        if issued["secret_id_ttl"] != 600 or issued["secret_id_num_uses"] != 1:
            raise RuntimeError("SECRET_ID_LIMITS")
        with ApplicationSecretStore(ENDPOINT, CA) as store:
            store.login(role, issued["secret_id"])
            for ref in refs:
                if store.read(SecretRef(ref, 1)).username != "synthetic-v1":
                    raise RuntimeError("EXACT_VERSION")
            if store.read(SecretRef(refs[0], 2)).username != "synthetic-v2":
                raise RuntimeError("NEW_VERSION")
            repeated = http.post(
                "/v1/auth/approle/login",
                json={
                    "role_id": role,
                    "secret_id": issued["secret_id"],
                },
            )
            if repeated.status_code not in (400, 403):
                raise RuntimeError("SECRET_ID_REUSED")
            token = store._store._token
            for method, path, payload in (
                ("GET", f"f01/data/{infra}", None),
                ("LIST", "f01/metadata", None),
                ("POST", f"f01/data/{refs[0]}", {"data": {"username": "x", "password": "x"}}),
                ("DELETE", f"f01/data/{refs[0]}", None),
                ("GET", "auth/approle/role/f03-application", None),
                ("GET", "sys/policies/acl/f03-application", None),
                ("POST", "auth/token/create", {}),
            ):
                if (
                    http.request(
                        method, "/v1/" + path, headers={"X-Vault-Token": token}, json=payload
                    ).status_code
                    != 403
                ):
                    raise RuntimeError("EXCESS_CAPABILITY")
            del token, issued
            store.revoke()
            try:
                store.read(SecretRef(refs[0], 1))
            except SecretStoreError:
                pass
            else:
                raise RuntimeError("REVOKED_ACCEPTED")
        call(http, "POST", "auth/token/revoke-self", day, {})
        del day
    print("PASS F03 APP PROOF: recuperación repetible; roots revocados; roles anteriores intactos.")
    print("PASS F03 APP PROOF: 12 refs versionadas; infra/list/write/delete/admin/token denegados.")
    print(
        "PASS F03 APP PROOF: SecretID de un uso; revocación sin fallback; sin claves del operador."
    )


def wait_active_uninitialized(http):
    import time

    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            if http.get("/v1/sys/health").status_code == 501:
                return
        except Exception:
            pass
        time.sleep(0.25)
    raise RuntimeError("EMPTY_NODE_NOT_READY")


def main():
    logging.disable(logging.CRITICAL)
    try:
        prove()
    except (Exception, KeyboardInterrupt) as error:
        # Closed stages only, never HTTP bodies, keys, tokens or traceback.
        allowed = {
            "ISOLATED_ONLY",
            "ALREADY_INITIALIZED",
            "BASELINE_NOT_DENIED",
            "INITIAL_ROOT_NOT_REVOKED",
            "SECRET_ID_LIMITS",
            "EXACT_VERSION",
            "NEW_VERSION",
            "SECRET_ID_REUSED",
            "EXCESS_CAPABILITY",
            "REVOKED_ACCEPTED",
            "EMPTY_NODE_NOT_READY",
        }
        code = str(error) if type(error) is RuntimeError and str(error) in allowed else "REFUSED"
        raise SystemExit("F03 APP PROOF " + code) from None


if __name__ == "__main__":
    main()
