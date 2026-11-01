"""Real private delivery proof; tokens never enter output or infrastructure API mounts."""

import json
import logging
import os
from pathlib import Path
from uuid import UUID, uuid4

import sqlalchemy as sa
from f01_daily import session
from f01_operator import CA, ENDPOINT
from f02_testing import Humans
from f03_application_issue import ensure
from f03_fixtures import ROOT
from f03_testing import Services, real_actors

from rag_platform.control.models import DbLocation, StorageLocation
from rag_platform.documents.errors import DocumentError
from rag_platform.providers.application_handoff import NAME, FileApplicationStore, read_record
from rag_platform.providers.application_secrets import ApplicationSecretStore
from rag_platform.providers.secrets import SecretErrorCode, SecretStoreError
from rag_platform.tenancy.contracts import SecretRef


def require(value):
    if not value:
        raise RuntimeError("ASSERTION")


def prove():
    stage = "PREPARE"
    parent = Path("/run/f03-application")
    probe = parent / ("probe-" + uuid4().hex)
    humans, consumer = Humans(), None
    try:
        probe.mkdir(mode=0o700)
        for name in ("issuer.lock", "consumer.lock"):
            fd = os.open(probe / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(b"1")
        humans.ready()
        with session() as (day, _, _):
            stage = "ISSUE"
            first = ensure(day, probe)
            require(first["created"] and first["state"] == "ACTIVE")
            original = read_record(probe / NAME)["token"]
            consumer = FileApplicationStore(probe, ENDPOINT, CA)
            try:
                FileApplicationStore(probe, ENDPOINT, CA)
            except SecretStoreError:
                pass
            else:
                raise RuntimeError("ASSERTION")
            with Services(store=consumer) as services:
                actors = real_actors(services.control, humans)
                fixtures = json.loads((ROOT / "ops/f03/repositories-fixture.json").read_text())
                count = 0
                for fixture in fixtures["fixtures"]:
                    stage = fixture["name"].upper().replace("-", "_") + "/READ"
                    tenant, repo = UUID(fixture["tenant"]), UUID(fixture["repository"])
                    with services.control.connect() as c:
                        row = c.execute(
                            sa.select(
                                DbLocation.app_secret_ref,
                                DbLocation.app_secret_version,
                                DbLocation.readonly_secret_ref,
                                DbLocation.readonly_secret_version,
                                StorageLocation.credential_ref,
                                StorageLocation.credential_version,
                            )
                            .join(
                                StorageLocation, StorageLocation.tenant_id == DbLocation.tenant_id
                            )
                            .where(DbLocation.tenant_id == tenant)
                        ).one()
                    for ref, version in ((row[0], row[1]), (row[2], row[3]), (row[4], row[5])):
                        consumer.read(SecretRef(ref, version))
                        count += 1
                    trace = uuid4()
                    ctx = services.authority.authorize(actors["alice"], tenant, trace)
                    services.repositories.require(ctx, trace, repo, "read")
                require(count == 12)
                reused = ensure(day, probe)
                require(not reused["created"] and read_record(probe / NAME)["token"] == original)
                print("PASS T002 HANDOFF: 12 refs; entrega privada reutilizada; consumidor único.")

                stage = "REPLACE"
                replaced = ensure(day, probe, replace=True)
                require(replaced["created"])
                consumer.read(SecretRef(row[0], row[1]))
                with ApplicationSecretStore(ENDPOINT, CA) as rejected:
                    try:
                        rejected.attach_application(original)
                    except SecretStoreError as error:
                        require(error.code == SecretErrorCode.DENIED)
                    else:
                        raise RuntimeError("ASSERTION")
                print("PASS T002 HANDOFF: reemplazo atómico; identidad anterior revocada.")

                stage = "MISSING"
                path, hidden = probe / NAME, probe / "paused.json"
                path.rename(hidden)
                try:
                    try:
                        consumer.read(SecretRef(row[0], row[1]))
                    except SecretStoreError:
                        pass
                    else:
                        raise RuntimeError("ASSERTION")
                finally:
                    hidden.rename(path)
                consumer.read(SecretRef(row[0], row[1]))

                stage = "REVOKED"
                current = read_record(path)["token"]
                with ApplicationSecretStore(ENDPOINT, CA) as revoker:
                    revoker.attach_application(current)
                    revoker.revoke()
                # SQL pool was populated above. Acquisition must still validate the store.
                trace = uuid4()
                ctx = services.authority.authorize(actors["alice"], tenant, trace)
                try:
                    services.repositories.require(ctx, trace, repo, "read")
                except DocumentError as error:
                    require(error.code == "DEPENDENCY_UNAVAILABLE")
                else:
                    raise RuntimeError("ASSERTION")
                require(
                    day._request("GET", "/v1/auth/token/lookup-self")["data"]["meta"]["role_name"]
                    == "f01-dev-day"
                )
                print(
                    "PASS T002 HANDOFF: ausente/revocado sin fallback; pool caliente; día intacto."
                )
    except (Exception, KeyboardInterrupt):
        raise SystemExit(f"F03 T002 HANDOFF {stage}: REFUSED; sin detalles sensibles.") from None
    finally:
        try:
            if consumer is not None:
                consumer.close()
        finally:
            humans.close()
            if probe.exists():
                for name in (NAME, "paused.json", "issuer.lock", "consumer.lock"):
                    (probe / name).unlink(missing_ok=True)
                probe.rmdir()


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    prove()
