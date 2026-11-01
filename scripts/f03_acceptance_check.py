"""Real concurrent HTTP receipt and a structurally complete DOCX expansion attack."""

import io
import json
import logging
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import sqlalchemy as sa
from f01_daily import session
from f02_common import engine
from f02_testing import Humans
from f03_application_issue import ensure
from f03_fixtures import ROOT, snapshot
from f03_http_check import API, DELIVERY, formats
from f03_receipt_check import totals
from f03_testing import Services, application, real_actors

from rag_platform.documents.schema import audit_events, document_receipts


class Failure(RuntimeError):
    pass


def require(value, code):
    if not value:
        raise Failure(code)


def prove():
    humans, api, catalog = Humans(), None, engine("migrator")
    phase, records = "START", []
    try:
        humans.ready()
        api = API(humans)
        fixtures = json.loads((ROOT / "ops/f03/repositories-fixture.json").read_text())["fixtures"]
        with session() as (day, _, _):
            ensure(day, DELIVERY)
            before = snapshot(catalog)
            with application(day) as store, Services(store=store) as services:
                actors = real_actors(services.control, humans)
                for item in fixtures:
                    tag = item["name"].upper().replace("-", "_")
                    tenant, repo = UUID(item["tenant"]), UUID(item["repository"])
                    path = f"/api/v1/tenants/{tenant}/repositories/{repo}/documents"
                    phase = tag + "/CONCURRENT"
                    key = "f03-http-race-" + uuid4().hex
                    before_rows = totals(services, actors["alice"], tenant)
                    tokens = [humans.tokens("alice")["access_token"] for _ in range(2)]
                    barrier = threading.Barrier(2, timeout=10)

                    def send(token, barrier=barrier, path=path, key=key):
                        barrier.wait()
                        body, _ = api.call(
                            None,
                            "POST",
                            path + "?filename=concurrent.txt",
                            body=b"F03 concurrent HTTP fixture.\n",
                            headers={
                                "Content-Type": "text/plain",
                                "Idempotency-Key": key,
                                "Authorization": "Bearer " + token,
                            },
                            expected=(200, 201, 409),
                        )
                        return json.loads(body)

                    with ThreadPoolExecutor(max_workers=2) as workers:
                        results = list(workers.map(send, tokens))
                    del tokens
                    positive = [r["document"] for r in results if "document" in r]
                    require(bool(positive), "NO_WINNER")
                    for result in results:
                        if "error" in result:
                            require(
                                result["error"]["code"] == "OPERATION_IN_PROGRESS",
                                "WRONG_CONCURRENT_CONFLICT",
                            )
                    replay = api.json(
                        "alice",
                        "POST",
                        path + "?filename=concurrent.txt",
                        body=b"F03 concurrent HTTP fixture.\n",
                        headers={"Content-Type": "text/plain", "Idempotency-Key": key},
                    )["document"]
                    require(all(r == replay for r in positive), "HTTP_DUPLICATE")
                    after_rows = totals(services, actors["alice"], tenant)
                    require(after_rows == tuple(n + 1 for n in before_rows), "HTTP_ROW_COUNTS")
                    trace = uuid4()
                    ctx = services.authority.authorize(actors["alice"], tenant, trace)
                    with services.connections.connection(ctx, trace) as c:
                        require(
                            c.scalar(
                                sa.select(sa.func.count())
                                .select_from(document_receipts)
                                .where(
                                    document_receipts.c.repository_id == repo,
                                    document_receipts.c.principal_id == actors["alice"],
                                    document_receipts.c.idempotency_key == key,
                                )
                            )
                            == 1,
                            "RECEIPT_DUPLICATE",
                        )
                        require(
                            c.scalar(
                                sa.select(sa.func.count())
                                .select_from(audit_events)
                                .where(
                                    audit_events.c.target_id == UUID(replay["document_id"]),
                                    audit_events.c.action == "DOCUMENT_RECEIVED",
                                )
                            )
                            == 1,
                            "AUDIT_DUPLICATE",
                        )

                    phase = tag + "/COMPLETE_DOCX_BOMB"

                    def objects(tenant=tenant, repo=repo):
                        trace = uuid4()
                        ctx = services.authority.authorize(actors["alice"], tenant, trace)
                        with services.gateway.client(ctx, trace, repo, "read") as (s3, bucket):
                            return sorted(
                                (v.object_name, v.etag, v.size)
                                for v in s3.list_objects(
                                    bucket, prefix=f"f03/{repo.hex}/", recursive=True
                                )
                            )

                    baseline_objects = objects()
                    bomb = io.BytesIO()
                    with zipfile.ZipFile(io.BytesIO(formats()[-1][2])) as valid:
                        with zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED) as attack:
                            for name in valid.namelist():
                                attack.writestr(name, valid.read(name))
                            attack.writestr("word/bomb.bin", b"x" * (2 * 1024 * 1024))
                    api.json(
                        "alice",
                        "POST",
                        path + "?filename=bomb.docx",
                        body=bomb.getvalue(),
                        headers={
                            "Content-Type": formats()[-1][1],
                            "Idempotency-Key": "f03-zip-specific-" + uuid4().hex,
                        },
                        expected=422,
                    )
                    require(
                        totals(services, actors["alice"], tenant) == after_rows
                        and objects() == baseline_objects,
                        "ZIP_LEFT_RESOURCE",
                    )
                    records.append(
                        {
                            "tenant": str(tenant),
                            "repository": str(repo),
                            "document": replay["document_id"],
                            "version": replay["version_id"],
                        }
                    )
                    print(f"PASS T007 FINAL {tag}: HTTP concurrente/replay sin duplicados.")
                    print(f"PASS T007 FINAL {tag}: DOCX expansivo rechazado sin filas/objetos.")
                require(snapshot(catalog) == before, "LEGACY_CHANGED")
                print(
                    "F03 HTTP RACE FIXTURES "
                    + json.dumps({"version": 1, "fixtures": records}, sort_keys=True)
                )
                print("PASS T007 FINAL: catálogo intacto; cuatro originales retenidos.")
    except (Exception, KeyboardInterrupt) as error:
        code = str(error) if isinstance(error, Failure) else "REFUSED"
        raise SystemExit(f"F03 T007 FINAL {phase}: {code}; sin detalles sensibles.") from None
    finally:
        if api is not None:
            api.close()
        humans.close()
        catalog.dispose()


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    prove()
