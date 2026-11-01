"""Actual OIDC CLI matrix/last-owner concurrency; preserves all owned fixtures."""

import logging
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

from f02_testing import Humans, provision

PHASE = "START"


def run():
    global PHASE
    driver = Humans()
    try:
        PHASE = "IDENTITIES"
        driver.ready()
        users = {
            name: UUID(driver.command(name, "me")["principal_id"])
            for name in ("alice", "bob", "carol", "dave")
        }
        assert len(set(users.values())) == 4
        PHASE = "BOOTSTRAP"
        driver.command("alice", "bootstrap-operator")
        driver.command("alice", "bootstrap-operator")
        driver.command("dave", "bootstrap-operator", expected="ROLE_DENIED")
        fixtures = provision()
        PHASE = "OWNERS"
        for name, tenant in fixtures.items():
            owner = "alice" if name.endswith("a") else "bob"
            kind = "PERSONAL" if owner == "alice" else "ORG"
            driver.command(
                "alice",
                "bootstrap-owner",
                "--tenant",
                tenant,
                "--user",
                users[owner],
                "--kind",
                kind,
            )
        a, b = fixtures["same-a"], fixtures["same-b"]
        driver.command(
            "alice",
            "bootstrap-owner",
            "--tenant",
            b,
            "--user",
            users["alice"],
            "--kind",
            "ORG",
            expected="STATE_CONFLICT",
        )
        driver.command(
            "alice",
            "membership",
            "--tenant",
            b,
            "--user",
            users["carol"],
            "--role",
            "reader",
            expected="ROLE_DENIED",
        )
        PHASE = "ROLE_MATRIX"
        driver.command(
            "alice", "membership", "--tenant", a, "--user", users["bob"], "--role", "admin"
        )
        driver.command(
            "bob", "membership", "--tenant", a, "--user", users["carol"], "--role", "editor"
        )
        driver.command(
            "bob",
            "membership",
            "--tenant",
            a,
            "--user",
            users["carol"],
            "--role",
            "owner",
            expected="ROLE_DENIED",
        )
        driver.command(
            "alice", "membership", "--tenant", a, "--user", users["bob"], "--role", "editor"
        )
        driver.command(
            "alice", "membership", "--tenant", a, "--user", users["carol"], "--role", "reader"
        )
        driver.command(
            "carol",
            "membership",
            "--tenant",
            a,
            "--user",
            users["dave"],
            "--role",
            "reader",
            expected="ROLE_DENIED",
        )
        driver.command(
            "bob", "membership", "--tenant", b, "--user", users["alice"], "--role", "reader"
        )
        driver.command(
            "alice", "platform-role", "--user", users["carol"], "--role", "platform_support"
        )
        driver.command(
            "carol",
            "bootstrap-owner",
            "--tenant",
            b,
            "--user",
            users["carol"],
            "--kind",
            "ORG",
            expected="ROLE_DENIED",
        )
        PHASE = "LAST_OWNER"
        driver.command(
            "alice",
            "membership",
            "--tenant",
            a,
            "--user",
            users["alice"],
            "--role",
            "reader",
            expected="LAST_OWNER",
        )
        driver.command(
            "alice", "membership", "--tenant", a, "--user", users["bob"], "--role", "owner"
        )

        def remove(name):
            # Independent CLI processes, engines and PostgreSQL transactions.
            try:
                driver.command(
                    name,
                    "membership",
                    "--tenant",
                    a,
                    "--user",
                    users[name],
                    "--role",
                    "owner",
                    "--state",
                    "REVOKED",
                )
                return "OK"
            except RuntimeError as error:
                if str(error) == "LAST_OWNER":
                    return "LAST_OWNER"
                raise

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(remove, ("alice", "bob")))
        assert sorted(outcomes) == ["LAST_OWNER", "OK"]
        survivor = "alice" if outcomes[0] == "LAST_OWNER" else "bob"
        driver.command(
            survivor, "membership", "--tenant", a, "--user", users["alice"], "--role", "owner"
        )
        driver.command(
            "alice", "membership", "--tenant", a, "--user", users["bob"], "--role", "editor"
        )
        PHASE = "SUSPENSION"
        try:
            driver.command(
                "alice", "principal-state", "--user", users["bob"], "--state", "SUSPENDED"
            )
            driver.command("bob", "me", expected="IDENTITY_SUSPENDED")
        finally:
            driver.command("alice", "principal-state", "--user", users["bob"], "--state", "ACTIVE")
        driver.command(
            "alice",
            "principal-state",
            "--user",
            users["alice"],
            "--state",
            "SUSPENDED",
            expected="LAST_OWNER",
        )
        driver.command(
            "alice",
            "platform-role",
            "--user",
            users["alice"],
            "--role",
            "platform_operator",
            "--state",
            "REVOKED",
            expected="LAST_OWNER",
        )
        PHASE = "FINAL"
        alice = driver.command("alice", "me")
        role_map = {
            item["tenant_id"]: item["role"]
            for item in alice["memberships"]
            if item["state"] == "ACTIVE"
        }
        assert role_map[str(a)] == "owner" and role_map[str(b)] == "reader"
        assert not driver.command("dave", "me")["memberships"]
        print("PASS T004: real OIDC CLI; explicit bootstrap; no implicit role or tenant takeover.")
        print("PASS T004: owner/admin/editor/reader/support; cross-tenant administration denied.")
        print("PASS T004: two CLI processes, one owner retained; suspension denied and restored.")
        print("PASS T004: secrets preserved; private token files removed; output without JWT.")
        print("T004: four IdP fixtures/four owned tenants retained; F02 still open.")
    finally:
        driver.close()


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    try:
        run()
    except Exception as error:
        closed = {
            "ROLE_DENIED",
            "LAST_OWNER",
            "INPUT_INVALID",
            "STATE_CONFLICT",
            "IDENTITY_SUSPENDED",
            "TENANT_UNAVAILABLE",
            "CATALOG_UNAVAILABLE",
            "IDP_LOGIN",
            "IDP_READINESS",
            "CLI_REJECTED",
            "WRONG_DENIAL",
            "OUTPUT_LEAK",
        }
        detail = " " + str(error) if str(error) in closed else ""
        print("F02-T004 " + PHASE + detail + ": stopped; no sensitive details.")
        raise SystemExit(1) from None
