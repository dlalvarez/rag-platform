"""F03-owned synthetic fixtures; preserve all pre-existing F01/F02 catalog rows."""

from pathlib import Path
from uuid import UUID, uuid5

import sqlalchemy as sa
from f01_admin import DAY_ACTOR
from f01_daily import session
from f02_common import engine

from rag_platform.control.models import Base, Instance, ProvisioningOperation
from rag_platform.providers.secrets import Credential
from rag_platform.provisioning.administration import Administration
from rag_platform.provisioning.storage import StorageTarget

NAMESPACE = UUID("67646a24-d263-4474-a722-71393ceda772")
NAMES = ("same-a", "same-b", "two-a", "two-b")
ROOT = Path(__file__).resolve().parents[1]


def snapshot(control):
    import hashlib
    import json

    with control.connect() as c:
        owned = list(
            c.execute(
                sa.select(ProvisioningOperation.id, ProvisioningOperation.tenant_id).where(
                    ProvisioningOperation.idempotency_key.in_(
                        [uuid5(NAMESPACE, name) for name in NAMES]
                    )
                )
            )
        )
        tenants, operations = [r.tenant_id for r in owned], [r.id for r in owned]
        result = {}
        for name, table in Base.metadata.tables.items():
            query = sa.select(table)
            if tenants and name == "tenants":
                query = query.where(table.c.id.not_in(tenants))
            elif tenants and "tenant_id" in table.c:
                query = query.where(table.c.tenant_id.not_in(tenants))
            elif operations and "operation_id" in table.c:
                query = query.where(table.c.operation_id.not_in(operations))
            rows = sorted(
                json.dumps(dict(r), sort_keys=True, default=str)
                for r in c.execute(query).mappings()
            )
            result[name] = hashlib.sha256("".join(rows).encode()).digest()
        return result


def provision():
    control = engine("migrator")
    storage = StorageTarget("https://minio:9000", Path("/run/f01-ca.crt"))
    try:
        before = snapshot(control)
        with control.connect() as c:
            instances = {
                row.host: row.id for row in c.execute(sa.select(Instance.host, Instance.id))
            }
        admin = Credential(
            Path("/run/secrets/storage_admin_user").read_text(),
            Path("/run/secrets/storage_admin_password").read_text(),
        )
        with session() as (store, _, _):
            service = Administration(
                control,
                DAY_ACTOR,
                store,
                Path("/run/f01-ca.crt"),
                storage,
                ROOT,
                storage_admin=admin,
            )
            result = {}
            for name in NAMES:
                host = "postgres2" if name == "two-b" else "postgres"
                item = service.create(instances[host], uuid5(NAMESPACE, name))
                if item["state"] != "READY":
                    raise RuntimeError("F03_FIXTURE_NOT_READY")
                result[name] = UUID(item["tenant"])
        if snapshot(control) != before:
            raise RuntimeError("F03_LEGACY_CHANGED")
        return result
    finally:
        storage.close()
        control.dispose()
