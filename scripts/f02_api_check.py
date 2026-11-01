"""Real TLS/OIDC metadata API; no product data-plane endpoints or secret output."""

import logging
import time
from uuid import UUID, uuid5

import sqlalchemy as sa
from f02_common import engine
from f02_testing import FIXTURE_NAMES, NAMESPACE, Humans

from rag_platform.control.models import ProvisioningOperation

PHASE = "START"


def run():
    global PHASE
    driver = Humans()
    control = engine("migrator")
    tokens = []
    try:
        PHASE = "READINESS"
        driver.ready()
        deadline = time.monotonic() + 60
        while True:
            try:
                response = driver.http.get("https://api:9443/healthz")
                if response.status_code == 200 and response.json()["phase"] == "F02":
                    break
            except Exception:
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError("READINESS")
            time.sleep(1)
        PHASE = "FIXTURES"
        with control.connect() as c:
            fixtures = {
                name: c.scalar(
                    sa.select(ProvisioningOperation.tenant_id).where(
                        ProvisioningOperation.idempotency_key == uuid5(NAMESPACE, name)
                    )
                )
                for name in FIXTURE_NAMES
            }
        assert all(fixtures.values())
        users = {
            name: driver.command(name, "me")["principal_id"]
            for name in ("alice", "bob", "carol", "dave")
        }
        forbidden = [driver.values["client_secret"]] + [
            item[field] for item in driver.values["users"].values() for field in ("id", "password")
        ]

        def request(name, path, *, bearer=None, params=None, expected=200, headers=None):
            token = bearer if bearer is not None else driver.tokens(name)["access_token"]
            tokens.append(token)
            response = driver.http.get(
                "https://api:9443" + path,
                params=params,
                headers={"Authorization": "Bearer " + token, **(headers or {})},
            )
            if response.status_code != expected:
                raise RuntimeError("HTTP_STATUS")
            if any(value in response.text for value in forbidden + tokens):
                raise RuntimeError("OUTPUT_LEAK")
            if response.headers.get("cache-control") != "no-store":
                raise RuntimeError("CACHE")
            UUID(response.json()["request_id"])
            return response.json()

        PHASE = "VIEWS"
        alice = request("alice", "/api/v1/me")
        assert alice["principal_id"] == users["alice"]
        roles = {item["tenant_id"]: item["role"] for item in alice["memberships"]}
        assert roles[str(fixtures["same-a"])] == "owner"
        assert roles[str(fixtures["same-b"])] == "reader"
        carol = request("carol", "/api/v1/tenants")
        assert {item["tenant_id"] for item in carol["items"]} == {str(fixtures["same-a"])}
        dave = request("dave", "/api/v1/me")
        assert dave["memberships"] == [] and dave["platform_roles"] == []
        PHASE = "PAGINATION"
        first = request("alice", "/api/v1/tenants", params={"limit": 1})
        assert len(first["items"]) == 1 and first["next_cursor"]
        second = request(
            "alice", "/api/v1/tenants", params={"limit": 1, "cursor": first["next_cursor"]}
        )
        assert second["items"][0]["tenant_id"] != first["items"][0]["tenant_id"]
        request("bob", "/api/v1/tenants", params={"cursor": first["next_cursor"]}, expected=422)
        request("alice", "/api/v1/tenants", params={"limit": 101}, expected=422)
        PHASE = "NEGATIVES"
        request("alice", "/api/v1/me", bearer="invalid-synthetic-token", expected=401)
        id_token = driver.tokens("alice")["id_token"]
        request("alice", "/api/v1/me", bearer=id_token, expected=401)
        request(
            "carol",
            "/api/v1/tenants",
            headers={"X-Tenant-ID": str(fixtures["same-b"]), "X-Role": "owner"},
        )
        request("alice", "/api/v1/tenants/" + str(fixtures["same-a"]), expected=404)
        request("alice", "/__test/context/" + str(fixtures["same-a"]), expected=404)
        PHASE = "SUSPENSION"
        driver.command("alice", "principal-state", "--user", users["bob"], "--state", "SUSPENDED")
        try:
            request("bob", "/api/v1/me", expected=403)
        finally:
            driver.command("alice", "principal-state", "--user", users["bob"], "--state", "ACTIVE")
        request("bob", "/api/v1/me")
        print(
            "PASS T005: API TLS/OIDC; roles A/B distinct; authorized views and bounded pagination."
        )
        print("PASS T005: invalid/ID token denied; bound cursor; no admin/test routes.")
        print("PASS T005: suspension effective and restored; no credentials in output.")
        print("T005: metadata API only; real data-plane counters/two topologies remain T006.")
    finally:
        driver.close()
        control.dispose()


if __name__ == "__main__":
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    try:
        run()
    except Exception:
        print(f"F02-T005 {PHASE}: stopped; no sensitive details; preserve fixtures.")
        raise SystemExit(1) from None
