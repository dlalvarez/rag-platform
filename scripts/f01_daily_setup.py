"""Operator-only stdin bridge: temporary root configuration, no secret stdout/files."""

import base64
import json
import logging
import sys
from pathlib import Path

from f01_access import AccessError
from f01_daily import ROLE, ROLE_SETTINGS, SECONDS, start
from f01_operator import call, client, require_unsealed

ROOT = Path(__file__).resolve().parents[1]
GENERATION = "sys/generate-root"


def optional(http, path, token):
    response = http.get("/v1/" + path, headers={"X-Vault-Token": token})
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise AccessError()
    return response.json()["data"]


def role_matches(data):
    return data is not None and all(data.get(k) == v for k, v in ROLE_SETTINGS.items())


def configure(http, root):
    if set(call(http, "GET", "auth/token/lookup-self", root)["data"]["policies"]) != {"root"}:
        raise AccessError()
    old_role = call(http, "GET", "auth/approle/role/f01-cli", root)["data"]
    before = (ROOT / "ops/f01/operator.hcl").read_text().strip()
    after = (ROOT / "ops/f01/operator-day.hcl").read_text().strip()
    policy = call(http, "GET", "sys/policies/acl/f01-operator", root)["data"]["policy"].strip()
    if policy not in (before, after):
        raise AccessError()
    existing = optional(http, f"auth/approle/role/{ROLE}", root)
    if existing is not None and not role_matches(existing):
        raise AccessError()
    tuning = call(http, "GET", "sys/auth/approle/tune", root)["data"]
    if tuning["max_lease_ttl"] < SECONDS:
        raise AccessError()
    if existing is None:
        call(http, "POST", f"auth/approle/role/{ROLE}", root, ROLE_SETTINGS)
    if not role_matches(call(http, "GET", f"auth/approle/role/{ROLE}", root)["data"]):
        raise AccessError()
    if policy != after:
        call(http, "PUT", "sys/policies/acl/f01-operator", root, {"policy": after})
    if call(http, "GET", "sys/policies/acl/f01-operator", root)["data"]["policy"].strip() != after:
        raise AccessError()
    if call(http, "GET", "auth/approle/role/f01-cli", root)["data"] != old_role:
        raise AccessError()


def recover(http, key):
    status = call(http, "GET", "sys/seal-status")
    if status["n"] != 1 or status["t"] != 1:
        raise AccessError()
    if status["sealed"]:
        result = call(http, "POST", "sys/unseal", payload={"key": key})
        if result["sealed"]:
            raise AccessError()
    state = call(http, "GET", GENERATION + "/attempt")
    if state["started"]:
        raise AccessError()  # Never adopt/cancel someone else's ceremony.
    root = nonce = None
    try:
        attempt = call(http, "POST", GENERATION + "/attempt", payload={})
        nonce, otp = attempt["nonce"], attempt["otp"]
        if attempt["required"] != 1 or not nonce or not otp:
            raise AccessError()
        result = call(http, "POST", GENERATION + "/update", payload={"nonce": nonce, "key": key})
        if result["nonce"] != nonce or not result["complete"]:
            raise AccessError()
        encoded = result.get("encoded_token", result.get("encoded_root_token", ""))
        raw = base64.b64decode(encoded + "=" * (-len(encoded) % 4), validate=True)
        mask = otp.encode("ascii")
        if not raw or len(raw) != len(mask):
            raise AccessError()
        root = bytes(a ^ b for a, b in zip(raw, mask, strict=True)).decode("ascii")
        del otp, raw, mask, result, key
        configure(http, root)
    finally:
        try:
            if root is not None:
                call(http, "POST", "auth/token/revoke-self", root, {})
                if (
                    http.get(
                        "/v1/auth/token/lookup-self", headers={"X-Vault-Token": root}
                    ).status_code
                    != 403
                ):
                    raise AccessError()
        finally:
            if nonce is not None:
                current = call(http, "GET", GENERATION + "/attempt")
                if current["started"] and current["nonce"] == nonce:
                    call(http, "DELETE", GENERATION + "/attempt")


def main():
    logging.disable(logging.CRITICAL)
    phase = "INPUT"
    try:
        body = json.loads(sys.stdin.read(8193))
        if not isinstance(body, dict) or body.get("action") not in (
            "recover",
            "activate",
            "restore",
            "health",
        ):
            raise AccessError()
        with client() as http:
            if body["action"] == "health":
                state = call(http, "GET", "sys/seal-status")
                if not state["initialized"]:
                    raise AccessError()
                print(json.dumps({"ok": True, "sealed": state["sealed"]}))
                return
            key = body["key"]
            if not isinstance(key, str) or not key or any(c.isspace() for c in key):
                raise AccessError()
            phase = body["action"].upper()
            if body["action"] == "recover":
                recover(http, key)
                output = {"ok": True, "root_revoked": True}
            else:
                state = call(http, "GET", "sys/seal-status")
                if state["sealed"]:
                    call(http, "POST", "sys/unseal", payload={"key": key})
                require_unsealed(http)
                # Confirm the temporary legacy endpoint was disabled again after restart.
                disabled = http.get("/v1/sys/generate-root/attempt")
                if disabled.status_code != 405:
                    raise AccessError()
                output = (
                    {"ok": True}
                    if body["action"] == "restore"
                    else {"ok": True, "day": start(password=body["password"], trial=True)}
                )
        print(json.dumps(output, sort_keys=True))
    except (Exception, KeyboardInterrupt):
        print(json.dumps({"ok": False, "code": "F01-DAY-" + phase}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
