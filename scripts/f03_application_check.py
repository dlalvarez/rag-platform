"""Trusted F03 credential battery; the API never receives the daily bearer."""

import json
import logging
from uuid import UUID

from f01_daily import session
from f01_operator import CA, CANARY, ENDPOINT
from f02_common import engine
from f03_fixtures import ROOT
from sqlalchemy.orm import Session

from rag_platform.control.models import DbLocation, Instance, StorageLocation
from rag_platform.providers.application_secrets import ApplicationSecretStore
from rag_platform.providers.secrets import SecretStoreError
from rag_platform.provisioning.postgres import Target
from rag_platform.tenancy.contracts import SecretRef


def prove():
    control = engine("migrator")
    try:
        scope = json.loads((ROOT / "ops/f03/application-scope.json").read_text())
        with session() as (day, _, _):
            role = day._request("GET", "/v1/auth/approle/role/f03-application/role-id")["data"][
                "role_id"
            ]
            issued = day._request(
                "POST", "/v1/auth/approle/role/f03-application/secret-id", json={}
            )["data"]
            if issued["secret_id_num_uses"] != 1 or issued["secret_id_ttl"] != 600:
                raise RuntimeError("SECRET_ID_LIMITS")
            with ApplicationSecretStore(ENDPOINT, CA) as app:
                try:
                    app.login(role, issued["secret_id"])
                    infra = [CANARY]
                    with Session(control) as catalog:
                        for fixture in scope["fixtures"]:
                            tenant = UUID(fixture["tenant"])
                            location = catalog.get(DbLocation, tenant)
                            instance = catalog.get(Instance, location.instance_id)
                            storage = catalog.get(StorageLocation, tenant)
                            refs = [
                                SecretRef(location.app_secret_ref, location.app_secret_version),
                                SecretRef(
                                    location.readonly_secret_ref, location.readonly_secret_version
                                ),
                                SecretRef(storage.credential_ref, storage.credential_version),
                            ]
                            if {str(ref.id) for ref in refs} != set(fixture["refs"]):
                                raise RuntimeError("SCOPE_CATALOG_MISMATCH")
                            infra.extend([location.migrator_secret_ref, instance.admin_secret_ref])
                            for ref, kind in zip(refs[:2], ("app", "readonly"), strict=True):
                                credential = app.read(ref)
                                if credential.username != "rag_t_" + tenant.hex + "_" + kind:
                                    raise RuntimeError("ROLE_MISMATCH")
                                with Target(instance.host, instance.port, CA).connect(
                                    location.db_name, credential
                                ) as sql:
                                    actual = sql.execute(
                                        "SELECT current_database(),current_user,"
                                        "(SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid())"
                                    ).fetchone()
                                    if actual != (location.db_name, credential.username, True):
                                        raise RuntimeError("DESTINATION_MISMATCH")
                                del credential
                            credential = app.read(refs[2])
                            if credential.username != "f01-t-" + tenant.hex:
                                raise RuntimeError("ROLE_MISMATCH")
                            del credential
                    token = app._store._token
                    for ref in set(infra):
                        result = app._store._client.get(
                            f"/v1/f01/data/{ref}",
                            params={"version": 1},
                            headers={"X-Vault-Token": token},
                        )
                        if result.status_code != 403:
                            raise RuntimeError("INFRA_NOT_DENIED")
                    repeated = app._store._client.post(
                        "/v1/auth/approle/login",
                        json={"role_id": role, "secret_id": issued["secret_id"]},
                    )
                    if repeated.status_code not in (400, 403):
                        raise RuntimeError("SECRET_ID_REUSED")
                    del token, issued
                finally:
                    app.revoke()
                try:
                    app.read(SecretRef(CANARY, 1))
                except SecretStoreError:
                    pass
                else:
                    raise RuntimeError("REVOKED_ACCEPTED")
        print("PASS F03 APP: 12 refs reales/versionadas; SQL app/readonly propios y TLS.")
        print("PASS F03 APP: admin/migrator/canary denegados; SecretID de un uso; token revocado.")
        print("PASS F03 APP: sesión diaria conservada; sin bearer infra en runtime.")
    finally:
        control.dispose()


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    try:
        prove()
    except (Exception, KeyboardInterrupt):
        raise SystemExit("F03 APP CHECK REFUSED; sin detalles sensibles.") from None
