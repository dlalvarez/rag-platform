"""Actual T006 OIDC/SQL/S3 harness; requires the existing daily authorization."""

import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from uuid import UUID, uuid5

import psycopg
import sqlalchemy as sa
from f01_daily import session as daily_session
from f02_common import engine
from f02_testing import FIXTURE_NAMES, ISSUER, NAMESPACE, Humans, legacy_snapshot
from minio.error import S3Error

from rag_platform.control.identity_models import Membership
from rag_platform.control.models import (
    DbLocation,
    Instance,
    ProvisioningOperation,
    StorageLocation,
    Tenant,
)
from rag_platform.provisioning.postgres import Target
from rag_platform.provisioning.storage import StorageTarget
from rag_platform.tenancy.contracts import SecretRef
from rag_platform.tenancy.resolver import AdministrativeTenant, CatalogResolver

PHASE = "START"
CA = Path("/run/f01-ca.crt")


def provider_crosses(control, fixtures):
    resolver = CatalogResolver(control)
    with daily_session() as (store, _role, _used):
        for a, b in (
            (fixtures["same-a"], fixtures["same-b"]),
            (fixtures["two-a"], fixtures["two-b"]),
        ):
            for own, other in ((a, b), (b, a)):
                source = resolver.resolve(AdministrativeTenant(own), "app")
                destination = resolver.resolve(AdministrativeTenant(other), "app")
                credential = store.read(source.credential)
                with Target(source.host, source.port, CA).connect(source.database, credential) as c:
                    assert c.execute("SELECT current_database()").fetchone()[0] == source.database
                try:
                    c = Target(destination.host, destination.port, CA).connect(
                        destination.database, credential
                    )
                except psycopg.Error as error:
                    assert error.sqlstate in {"42501", "28P01"}
                else:
                    c.close()
                    raise RuntimeError("SQL_CROSS_ALLOWED")
                with control.connect() as c:
                    locations = {
                        row.tenant_id: row
                        for row in c.execute(
                            sa.select(StorageLocation).where(
                                StorageLocation.tenant_id.in_([own, other])
                            )
                        ).mappings()
                    }
                location = locations[own]
                storage = StorageTarget(location["endpoint"], CA)
                try:
                    secret = store.read(
                        SecretRef(location["credential_ref"], location["credential_version"])
                    )
                    s3 = storage.s3(secret)
                    list(s3.list_objects(location["bucket"]))
                    try:
                        list(s3.list_objects(locations[other]["bucket"]))
                    except S3Error as error:
                        assert error.code == "AccessDenied"
                    else:
                        raise RuntimeError("S3_CROSS_ALLOWED")
                finally:
                    storage.close()


def run():
    global PHASE
    driver, control = Humans(), engine("migrator")
    child, log = None, None
    temporary = tempfile.TemporaryDirectory(prefix="f02-t006-", dir="/run/f02-auth")
    tokens, cleanup = [], []
    before = None
    try:
        PHASE = "SESSION"
        with daily_session():
            pass
        driver.ready()
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
            hosts = dict(
                c.execute(
                    sa.select(DbLocation.tenant_id, Instance.host)
                    .join(Instance, Instance.id == DbLocation.instance_id)
                    .where(DbLocation.tenant_id.in_(fixtures.values()))
                ).all()
            )
            assert hosts[fixtures["two-b"]] == "postgres2"
            assert {hosts[fixtures[n]] for n in ("same-a", "same-b", "two-a")} == {"postgres"}
        before = legacy_snapshot(control)
        users = {
            n: UUID(driver.command(n, "me")["principal_id"])
            for n in ("alice", "bob", "carol", "dave")
        }
        PHASE = "MEMBERSHIPS"
        # Preserve T004/T005 logical state after exercising the second topology.
        for owner, tenant, member, role in (
            ("alice", fixtures["two-a"], "bob", "editor"),
            ("alice", fixtures["two-a"], "carol", "reader"),
            ("bob", fixtures["two-b"], "alice", "reader"),
        ):
            with control.connect() as c:
                prior = c.execute(
                    sa.select(Membership.role, Membership.state).where(
                        Membership.user_id == users[member], Membership.tenant_id == tenant
                    )
                ).first()
            restored_role, restored_state = tuple(prior) if prior else (role, "REVOKED")
            cleanup.append((owner, tenant, users[member], restored_role, restored_state))
            driver.command(
                owner, "membership", "--tenant", tenant, "--user", users[member], "--role", role
            )
        PHASE = "DIRECT_CROSSES"
        provider_crosses(control, fixtures)
        PHASE = "FIXTURE_START"
        path = Path(temporary.name) / "api.log"
        log = os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "w")
        child = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "f02_api_fixture:factory",
                "--factory",
                "--app-dir",
                "scripts",
                "--host",
                "127.0.0.1",
                "--port",
                "9443",
                "--workers",
                "1",
                "--limit-concurrency",
                "16",
                "--timeout-keep-alive",
                "5",
                "--no-access-log",
                "--ssl-keyfile",
                "/tls/api.key",
                "--ssl-certfile",
                "/tls/api.crt",
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        base = "https://localhost:9443"
        deadline = time.monotonic() + 45
        while True:
            if child.poll() is not None:
                raise RuntimeError("FIXTURE_START")
            try:
                if driver.http.get(base + "/healthz").status_code == 200:
                    break
            except Exception:
                pass
            if time.monotonic() > deadline:
                raise RuntimeError("FIXTURE_READINESS")
            time.sleep(1)

        forbidden = [ISSUER, driver.values["client_secret"]] + [
            item[field] for item in driver.values["users"].values() for field in ("id", "password")
        ]

        def counters():
            response = driver.http.get(base + "/__test/counters")
            assert response.status_code == 200
            result = response.json()
            assert set(result) == {"secrets", "connections", "queries", "s3"}
            return result

        def request(name, tenant, *, expected=200, params=None, bearer=None, headers=None):
            raw = driver.tokens(name)["access_token"] if bearer is None else bearer
            tokens.append(raw)
            response = driver.http.get(
                base + "/__test/context/" + str(tenant),
                params=params,
                headers={"Authorization": "Bearer " + raw, **(headers or {})},
            )
            if response.status_code != expected:
                raise RuntimeError("HTTP_" + str(response.status_code))
            assert not any(value in response.text for value in forbidden + tokens)
            return response.json()

        def denied(name, tenant, **options):
            original = counters()
            request(name, tenant, expected=options.pop("expected", 403), **options)
            assert counters() == original

        PHASE = "COLD_DENIALS"
        assert counters() == {"secrets": 0, "connections": 0, "queries": 0, "s3": 0}
        denied(
            "carol",
            fixtures["same-b"],
            headers={"X-Tenant-ID": str(fixtures["same-a"]), "X-Role": "owner"},
        )
        denied("dave", fixtures["same-a"])
        denied("alice", fixtures["same-a"], bearer="synthetic-invalid", expected=401)
        # A changed payload with an unchanged real signature must not authorize.
        raw = driver.tokens("alice")["access_token"]
        head, body, signature = raw.split(".")
        import base64

        claims = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        claims["tenant_id"] = str(fixtures["same-b"])
        changed = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
        denied(
            "alice", fixtures["same-b"], bearer=head + "." + changed + "." + signature, expected=401
        )

        for label, a, b in (
            ("SAME_INSTANCE", fixtures["same-a"], fixtures["same-b"]),
            ("TWO_INSTANCES", fixtures["two-a"], fixtures["two-b"]),
        ):
            PHASE = label
            for tenant, role in ((a, "owner"), (b, "reader"), (a, "owner")):
                result = request("alice", tenant, params={"role": "owner"})
                assert result == {"tenant_id": str(tenant), "role": role, "sql": True, "s3": True}
            result = request("carol", a)
            assert result["role"] == "reader"
            denied("carol", b, headers={"X-Tenant-ID": str(a)})
            denied("dave", a)
            denied("alice", a, params={"forge": str(b)}, expected=422)
            denied("alice", a, params={"other_request": "1"}, expected=422)
            # State changes are observed on the next request, with warm pools.
            driver.command(
                "alice",
                "membership",
                "--tenant",
                a,
                "--user",
                users["carol"],
                "--role",
                "reader",
                "--state",
                "SUSPENDED",
            )
            try:
                denied("carol", a)
            finally:
                driver.command(
                    "alice",
                    "membership",
                    "--tenant",
                    a,
                    "--user",
                    users["carol"],
                    "--role",
                    "reader",
                    "--state",
                    "ACTIVE",
                )
            driver.command(
                "alice", "principal-state", "--user", users["bob"], "--state", "SUSPENDED"
            )
            try:
                denied("bob", b)
            finally:
                driver.command(
                    "alice", "principal-state", "--user", users["bob"], "--state", "ACTIVE"
                )
            for changes in ({"state": "SUSPENDED"}, {"observed_version": "incompatible"}):
                with control.begin() as c:
                    c.execute(sa.update(Tenant).where(Tenant.id == a).values(**changes))
                try:
                    denied("alice", a)
                finally:
                    with control.begin() as c:
                        c.execute(
                            sa.update(Tenant)
                            .where(Tenant.id == a)
                            .values(state="READY", observed_version="f01_tenant_0001")
                        )
            request("alice", a)
            print(f"PASS T006 {label}: OIDC roles A/B/A; SQL/S3 propios y cruces denegados.")
            print(f"PASS T006 {label}: IDOR/estados: cero secretos, conexiones, queries y S3.")

        PHASE = "AUDIT"
        with control.connect() as c:
            assert (
                c.scalar(
                    sa.text("SELECT count(*) FROM identity_audit WHERE event_code='AUTH_DENIED'")
                )
                > 0
            )
        assert legacy_snapshot(control) == before
        PHASE = "LOGS"
        child.terminate()
        child.wait(timeout=20)
        child = None
        log.close()
        log = None
        text = path.read_text()
        assert not any(value in text for value in forbidden + tokens)
        assert not re.search(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", text)
        assert "Traceback" not in text
        print("PASS T006: captura API sin JWT/credenciales/subjects; datos F01 conservados.")
        print("T006: fixtures conservadas, sin nuevas fases ni cierre automático de F02.")
    finally:
        if child:
            child.terminate()
            try:
                child.wait(timeout=20)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)
        if log:
            log.close()
        failed = False
        for owner, tenant, user, role, state in reversed(cleanup):
            try:
                driver.command(
                    owner,
                    "membership",
                    "--tenant",
                    tenant,
                    "--user",
                    user,
                    "--role",
                    role,
                    "--state",
                    state,
                )
            except Exception:
                failed = True
        temporary.cleanup()
        driver.close()
        control.dispose()
        if failed:
            raise RuntimeError("RESTORE_MEMBERSHIPS") from None


if __name__ == "__main__":
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    try:
        run()
    except Exception as error:
        safe = str(error)
        if safe not in {
            "SESSION",
            "FIXTURE_START",
            "FIXTURE_READINESS",
            "HTTP_401",
            "HTTP_403",
            "HTTP_422",
            "HTTP_503",
            "RESTORE_MEMBERSHIPS",
        }:
            safe = "STOPPED"
        print(f"F02-T006 {PHASE}: {safe}; no sensitive details; preserve fixtures.")
        raise SystemExit(1) from None
