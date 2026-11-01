"""Real OIDC/SQL/MinIO boundaries with in-process observers, never a debug endpoint."""

import json
import logging
import os
from pathlib import Path
from uuid import UUID, uuid4

from f01_daily import session
from f01_operator import CA, ENDPOINT
from f02_common import engine
from f02_identity_admin import settings
from f02_testing import Humans
from f03_application_issue import ensure
from f03_fixtures import ROOT, snapshot
from f03_testing import real_actors
from fastapi.testclient import TestClient

from rag_platform.documents import api as adapter
from rag_platform.identity_api import create_app, private_file
from rag_platform.providers.application_handoff import NAME, read_record
from rag_platform.providers.application_secrets import ApplicationSecretStore
from rag_platform.providers.identity import OIDCVerifier
from rag_platform.providers.secrets import SecretErrorCode, SecretStoreError
from rag_platform.provisioning.storage import StorageTarget


class Failure(RuntimeError):
    pass


def require(value, code):
    if not value:
        raise Failure(code)


def prove():
    humans, control, catalog = Humans(), engine(), engine("migrator")
    path = Path("/run/f03-application") / ("observers-" + uuid4().hex)
    runtime, phase = None, "PREPARE"
    previous_s3, previous_spool = StorageTarget.s3, adapter.UploadSpool
    try:
        path.mkdir(mode=0o700)
        for name in ("issuer.lock", "consumer.lock"):
            fd = os.open(path / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(b"1")
        phase = "IDENTITY"
        humans.ready()
        with session() as (day, _, _):
            phase = "ACTORS"
            actors = real_actors(control, humans)
            before = snapshot(catalog)
            phase = "ISSUE"
            ensure(day, path)
            key = private_file("/run/secrets/api_authority_key", 32)
            phase = "RUNTIME"
            runtime = adapter.Runtime(control, key, path, ENDPOINT, CA)
            counts = {"secret": 0, "s3": 0, "spool": 0}
            read = runtime.store.read

            def counted_read(ref):
                counts["secret"] += 1
                return read(ref)

            def counted_s3(target, credential=None):
                counts["s3"] += 1
                return previous_s3(target, credential)

            class CountedSpool(previous_spool):
                def __init__(self, *args, **kwargs):
                    counts["spool"] += 1
                    super().__init__(*args, **kwargs)

            runtime.store.read = counted_read
            StorageTarget.s3, adapter.UploadSpool = counted_s3, CountedSpool
            phase = "APP"
            app = create_app(
                control,
                OIDCVerifier(settings()),
                key,
                profiles=("identity", "documents"),
                close_resources=True,
            )
            adapter.install(app, runtime)
            app.state.resource_closers.append(runtime.close)
            phase = "FIXTURES"
            fixtures = json.loads((ROOT / "ops/f03/repositories-fixture.json").read_text())[
                "fixtures"
            ]
            manifest = json.loads((ROOT / "ops/f03/http-fixture.json").read_text())["documents"]
            phase = "LIFESPAN"
            with TestClient(app) as client:
                for fixture in fixtures:
                    tag = fixture["name"].upper().replace("-", "_")
                    tenant, repo = UUID(fixture["tenant"]), UUID(fixture["repository"])
                    base = f"/api/v1/tenants/{tenant}/repositories/{repo}"
                    record = next(
                        r for r in manifest if r["tenant"] == str(tenant) and r["format"] == "txt"
                    )

                    def call(user, method, endpoint, *, expected, body=None, headers=None):
                        actual = dict(headers or {})
                        if user is not None:
                            actual["Authorization"] = (
                                "Bearer " + humans.tokens(user)["access_token"]
                            )
                        response = client.request(method, endpoint, content=body, headers=actual)
                        require(response.status_code == expected, "HTTP_STATUS")
                        return response

                    def reset():
                        counts.update(secret=0, s3=0, spool=0)

                    phase = tag + "/POSITIVE"
                    reset()
                    call(
                        "alice",
                        "POST",
                        base + "/documents?filename=http-fixture.txt",
                        expected=200,
                        body=b"F03 HTTP original fixture.\n",
                        headers={
                            "Content-Type": "text/plain",
                            "Idempotency-Key": "f03-http-" + fixture["name"] + "-txt",
                        },
                    )
                    require(
                        all(counts[k] > 0 for k in ("secret", "s3", "spool")), "OBSERVER_NOT_LIVE"
                    )
                    call(
                        "carol",
                        "GET",
                        base + f"/documents/{record['document']}/original",
                        expected=200,
                    )

                    phase = tag + "/PRE_AUTH"
                    for user, endpoint in (
                        (None, base),
                        ("alice", f"/api/v1/tenants/{uuid4()}/repositories/{repo}"),
                    ):
                        reset()
                        call(user, "GET", endpoint, expected=401 if user is None else 403)
                        require(
                            counts == {"secret": 0, "s3": 0, "spool": 0},
                            "EARLY_DENIAL_TOUCHED_DATA",
                        )

                    reset()
                    call(
                        "carol",
                        "POST",
                        base + "/documents?filename=invalid.txt",
                        expected=403,
                        body=b"\xff",
                        headers={
                            "Content-Type": "text/plain",
                            "Idempotency-Key": "synthetic-invalid-key",
                        },
                    )
                    require(counts == {"secret": 0, "s3": 0, "spool": 0}, "READER_TOUCHED_DATA")

                    phase = tag + "/CURSOR"
                    ctx = runtime.authority.authorize(actors["alice"], tenant, uuid4())
                    cursor = runtime.repositories.pagination.encode(
                        ctx, "documents:" + str(repo), UUID(record["document"])
                    )
                    reset()
                    call("bob", "GET", base + "/documents?cursor=" + cursor, expected=422)
                    require(counts == {"secret": 0, "s3": 0, "spool": 0}, "CURSOR_TOUCHED_DATA")

                    phase = tag + "/ACL_AND_DOCUMENT"
                    reset()
                    call("dave", "GET", base + "/documents", expected=403)
                    require(
                        counts["secret"] > 0 and counts["s3"] == counts["spool"] == 0,
                        "ACL_OPENED_STORAGE",
                    )
                    foreign = next(r for r in manifest if r["tenant"] != str(tenant))
                    reset()
                    call(
                        "alice",
                        "GET",
                        base + f"/documents/{foreign['document']}/original",
                        expected=404,
                    )
                    require(
                        counts["secret"] > 0 and counts["s3"] == counts["spool"] == 0,
                        "FOREIGN_DOCUMENT_OPENED_STORAGE",
                    )
                    print(f"PASS T007 OBSERVERS {tag}: autoridad antes de datos.")
                    print(f"PASS T007 OBSERVERS {tag}: ACL/doc antes de S3; pool caliente.")
                require(snapshot(catalog) == before, "LEGACY_CHANGED")
                require(
                    day._request("GET", "/v1/auth/token/lookup-self")["data"]["meta"]["role_name"]
                    == "f01-dev-day",
                    "DAY_CHANGED",
                )
                print("PASS T007 OBSERVERS: cuatro fixtures; catálogo intacto; sin debug público.")
    except (Exception, KeyboardInterrupt) as error:
        code = str(error) if isinstance(error, Failure) else "REFUSED"
        raise SystemExit(f"F03 T007 OBSERVERS {phase}: {code}; sin detalles sensibles.") from None
    finally:
        StorageTarget.s3, adapter.UploadSpool = previous_s3, previous_spool
        try:
            if runtime is not None:
                runtime.close()
            delivery = path / NAME
            if delivery.exists():
                with ApplicationSecretStore(ENDPOINT, CA) as cleanup:
                    try:
                        cleanup.attach_application(read_record(delivery)["token"])
                    except SecretStoreError as error:
                        if error.code != SecretErrorCode.DENIED:
                            raise
                    else:
                        cleanup.revoke()
        finally:
            humans.close()
            control.dispose()
            catalog.dispose()
            if path.exists():
                for name in (NAME, "issuer.lock", "consumer.lock"):
                    (path / name).unlink(missing_ok=True)
                path.rmdir()


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    prove()
