"""Internal synthetic test driver; JWTs/IdP passwords never enter output."""

import hashlib
import json
import os
import ssl
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from uuid import UUID, uuid4, uuid5

import httpx
import sqlalchemy as sa
from f01_admin import DAY_ACTOR
from f01_daily import session as daily_session
from f02_common import engine

from rag_platform.control.models import Base, Instance, ProvisioningOperation
from rag_platform.providers.secrets import Credential
from rag_platform.provisioning.administration import Administration
from rag_platform.provisioning.storage import StorageTarget

ROOT = Path(__file__).resolve().parents[1]
ISSUER = "https://idp:8443/realms/rag-dev-identity-fixture-v2"
NAMESPACE = UUID("091da0ab-dfa8-452c-a4d2-0b699aac7653")
FIXTURE_NAMES = ("same-a", "same-b", "two-a", "two-b")


class Humans:
    def __init__(self):
        self.values = json.loads(Path("/run/secrets/identity-fixture.json").read_text())
        self.http = httpx.Client(
            verify=ssl.create_default_context(cafile="/tls/ca.crt"),
            timeout=10,
            trust_env=False,
            follow_redirects=False,
        )
        self.directory = tempfile.TemporaryDirectory(prefix="f02-", dir="/run/f02-auth")

    def close(self):
        self.http.close()
        self.directory.cleanup()

    def ready(self):
        deadline = time.monotonic() + 180
        while True:
            try:
                response = self.http.get(ISSUER + "/.well-known/openid-configuration")
                if response.status_code == 200 and response.json()["issuer"] == ISSUER:
                    return
            except httpx.HTTPError:
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError("IDP_READINESS")
            time.sleep(2)

    def tokens(self, name):
        response = self.http.post(
            ISSUER + "/protocol/openid-connect/token",
            auth=httpx.BasicAuth("f02-identity-probe", self.values["client_secret"]),
            data={
                "grant_type": "password",
                "username": name,
                "password": self.values["users"][name]["password"],
                "scope": "openid",
            },
        )
        if response.status_code != 200:
            raise RuntimeError("IDP_LOGIN")
        return response.json()

    def command(self, name, *arguments, expected=None):
        token = self.tokens(name)["access_token"]
        path = Path(self.directory.name) / (uuid4().hex + ".jwt")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "w") as output:
                output.write(token)
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/f02_identity_admin.py",
                    "--token-file",
                    str(path),
                    *map(str, arguments),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=45,
            )
        finally:
            path.unlink(missing_ok=True)
        combined = result.stdout + result.stderr
        forbidden = (
            [token, self.values["client_secret"]]
            + [user["password"] for user in self.values["users"].values()]
            + [user["id"] for user in self.values["users"].values()]
        )
        if any(secret in combined for secret in forbidden):
            raise RuntimeError("OUTPUT_LEAK")
        data = json.loads(result.stdout)
        if expected is None:
            if result.returncode != 0 or data.get("status") != "OK":
                code = data.get("code")
                if code in {
                    "ROLE_DENIED",
                    "LAST_OWNER",
                    "INPUT_INVALID",
                    "STATE_CONFLICT",
                    "IDENTITY_SUSPENDED",
                    "TENANT_UNAVAILABLE",
                    "CATALOG_UNAVAILABLE",
                }:
                    raise RuntimeError(code)
                raise RuntimeError("CLI_REJECTED")
            return data["result"]
        if result.returncode != 1 or data.get("status") != "DENIED" or data.get("code") != expected:
            raise RuntimeError("WRONG_DENIAL")
        return data


def legacy_snapshot(control):
    with control.connect() as c:
        rows = c.execute(
            sa.select(ProvisioningOperation.id, ProvisioningOperation.tenant_id).where(
                ProvisioningOperation.idempotency_key.in_(
                    [uuid5(NAMESPACE, name) for name in FIXTURE_NAMES]
                )
            )
        ).all()
        tenants, operations = [r.tenant_id for r in rows], [r.id for r in rows]
        result = {}
        for name, table in Base.metadata.tables.items():
            query = sa.select(table)
            if tenants and name == "tenants":
                query = query.where(table.c.id.not_in(tenants))
            elif tenants and "tenant_id" in table.c:
                query = query.where(table.c.tenant_id.not_in(tenants))
            elif operations and "operation_id" in table.c:
                query = query.where(table.c.operation_id.not_in(operations))
            values = sorted(
                json.dumps(dict(r), sort_keys=True, default=str)
                for r in c.execute(query).mappings()
            )
            result[name] = hashlib.sha256("".join(values).encode()).digest()
        return result


def provision():
    control = engine("migrator")
    storage = StorageTarget("https://minio:9000", Path("/run/f01-ca.crt"))
    try:
        before = legacy_snapshot(control)
        with control.connect() as c:
            instances = {
                row.host: row.id for row in c.execute(sa.select(Instance.host, Instance.id))
            }
        credential = Credential(
            Path("/run/secrets/storage_admin_user").read_text(),
            Path("/run/secrets/storage_admin_password").read_text(),
        )
        with daily_session() as (store, _role, _used):
            service = Administration(
                control,
                DAY_ACTOR,
                store,
                Path("/run/f01-ca.crt"),
                storage,
                ROOT,
                storage_admin=credential,
            )
            result = {}
            for name in FIXTURE_NAMES:
                host = "postgres2" if name == "two-b" else "postgres"
                record = service.create(instances[host], uuid5(NAMESPACE, name))
                if record["state"] != "READY":
                    raise RuntimeError("PROVISION")
                result[name] = UUID(record["tenant"])
            if legacy_snapshot(control) != before:
                raise RuntimeError("LEGACY_CHANGED")
            return result
    finally:
        storage.close()
        control.dispose()
