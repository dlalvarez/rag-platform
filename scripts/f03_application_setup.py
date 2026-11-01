"""Fixed F03 application policy/role bootstrap, called only within root recovery."""

import hashlib
import json
import logging
import sys
from pathlib import Path
from uuid import UUID

from f01_access import AccessError
from f01_daily_setup import SetupFailure, optional, recover, wait_active
from f01_operator import call, client, require_unsealed

ROOT = Path(__file__).resolve().parents[1]
ROLE = "f03-application"
SETTINGS = {
    "bind_secret_id": True,
    "secret_id_ttl": 600,
    "secret_id_num_uses": 1,
    "token_policies": [ROLE],
    "token_ttl": 3600,
    "token_max_ttl": 3600,
    "token_explicit_max_ttl": 3600,
    "token_num_uses": 0,
    "token_period": 0,
    "token_type": "service",
    "token_no_default_policy": True,
}
ISSUANCE = (
    '\npath "auth/approle/role/f03-application/role-id" {\n'
    '  capabilities = ["read"]\n}\n'
    'path "auth/approle/role/f03-application/secret-id" {\n'
    '  capabilities = ["update"]\n}\n'
)


def scope_policy(scope):
    if not isinstance(scope, dict) or set(scope) != {"version", "fixtures"}:
        raise AccessError()
    if type(scope["version"]) is not int or scope["version"] != 1:
        raise AccessError()
    fixtures = scope["fixtures"]
    if not isinstance(fixtures, list) or len(fixtures) != 4:
        raise AccessError()
    names, tenants, refs = set(), set(), set()
    for item in fixtures:
        if not isinstance(item, dict) or set(item) != {"name", "tenant", "refs"}:
            raise AccessError()
        name, tenant, values = item["name"], item["tenant"], item["refs"]
        if name in names or name not in {"same-a", "same-b", "two-a", "two-b"}:
            raise AccessError()
        if not isinstance(tenant, str) or str(UUID(tenant)) != tenant or tenant in tenants:
            raise AccessError()
        if not isinstance(values, list) or len(values) != 3:
            raise AccessError()
        for value in values:
            if not isinstance(value, str) or str(UUID(value)) != value or value in refs:
                raise AccessError()
            refs.add(value)
        names.add(name)
        tenants.add(tenant)
    paths = {f"f01/data/{ref}": {"capabilities": ["read"]} for ref in sorted(refs)}
    paths["auth/token/lookup-self"] = {"capabilities": ["read"]}
    paths["auth/token/revoke-self"] = {"capabilities": ["update"]}
    return json.dumps({"path": paths}, sort_keys=True, separators=(",", ":"))


def matches(data):
    return data is not None and all(data.get(k) == v for k, v in SETTINGS.items())


def configure(http, root):
    # All conflict checks precede any mutation. Existing differing policies/roles stop.
    policy = scope_policy(json.loads((ROOT / "ops/f03/application-scope.json").read_text()))
    if set(call(http, "GET", "auth/token/lookup-self", root)["data"]["policies"]) != {"root"}:
        raise AccessError()
    baseline = (ROOT / "ops/f01/provisioner.hcl").read_text().strip()
    updated = baseline + ISSUANCE
    current = call(http, "GET", "sys/policies/acl/f01-provisioner", root)["data"]["policy"]
    if current.strip() not in (baseline, updated.strip()):
        raise AccessError()
    existing_policy = optional(http, "sys/policies/acl/" + ROLE, root)
    if existing_policy is not None:
        try:
            if json.loads(existing_policy["policy"]) != json.loads(policy):
                raise AccessError()
        except (KeyError, ValueError, TypeError):
            raise AccessError() from None
    existing_role = optional(http, "auth/approle/role/" + ROLE, root)
    if existing_role is not None and not matches(existing_role):
        raise AccessError()
    preserved = {
        path: call(http, "GET", path, root)["data"]
        for path in (
            "auth/approle/role/f01-cli",
            "auth/approle/role/f01-dev-day",
            "sys/policies/acl/f01-operator",
        )
    }
    if existing_policy is None:
        call(http, "PUT", "sys/policies/acl/" + ROLE, root, {"policy": policy})
    if existing_role is None:
        call(http, "POST", "auth/approle/role/" + ROLE, root, SETTINGS)
    if current.strip() != updated.strip():
        call(http, "PUT", "sys/policies/acl/f01-provisioner", root, {"policy": updated})
    if json.loads(
        call(http, "GET", "sys/policies/acl/" + ROLE, root)["data"]["policy"]
    ) != json.loads(policy):
        raise AccessError()
    if not matches(call(http, "GET", "auth/approle/role/" + ROLE, root)["data"]):
        raise AccessError()
    if (
        call(http, "GET", "sys/policies/acl/f01-provisioner", root)["data"]["policy"].strip()
        != updated.strip()
    ):
        raise AccessError()
    for path, before in preserved.items():
        if call(http, "GET", path, root)["data"] != before:
            raise AccessError()


def main():
    logging.disable(logging.CRITICAL)
    phase = "INPUT"
    try:
        body = json.loads(sys.stdin.read(8193))
        if not isinstance(body, dict) or body.get("action") not in ("health", "recover", "restore"):
            raise AccessError()
        with client() as http:
            phase = body["action"].upper()
            if body["action"] == "health":
                state = call(http, "GET", "sys/seal-status")
                if not state["initialized"]:
                    raise AccessError()
                result = {
                    "ok": True,
                    "sealed": state["sealed"],
                    "source_hash": hashlib.sha256(
                        b"".join(
                            (ROOT / name).read_bytes()
                            for name in (
                                "scripts/f03_application_setup.py",
                                "scripts/f01_daily_setup.py",
                                "ops/f01/provisioner.hcl",
                                "ops/f03/application-scope.json",
                            )
                        )
                    ).hexdigest(),
                }
            else:
                key = body["key"]
                if not isinstance(key, str) or not key or any(c.isspace() for c in key):
                    raise AccessError()
                if body["action"] == "recover":
                    recover(http, key, configure_action=configure)
                    result = {"ok": True, "root_revoked": True}
                else:
                    state = call(http, "GET", "sys/seal-status")
                    if state["sealed"]:
                        call(http, "POST", "sys/unseal", payload={"key": key})
                    require_unsealed(http)
                    wait_active(http)
                    if http.get("/v1/sys/generate-root/attempt").status_code != 405:
                        raise AccessError()
                    result = {"ok": True}
        print(json.dumps(result, sort_keys=True))
    except (Exception, KeyboardInterrupt) as error:
        step = error.step if isinstance(error, SetupFailure) else phase
        print(json.dumps({"ok": False, "code": "F03-APP-" + step}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
