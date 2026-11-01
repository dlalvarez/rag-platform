"""Real F03 HTTPS/SQL/S3 proof. Closed output, retained synthetic documents only."""

import hashlib
import io
import json
import logging
import ssl
import zipfile
from pathlib import Path
from uuid import UUID, uuid4

import urllib3
from f01_daily import session
from f01_operator import CA, ENDPOINT
from f02_common import engine
from f02_testing import Humans
from f03_application_issue import ensure
from f03_fixtures import ROOT, snapshot
from f03_receipt_check import totals
from f03_repository_check import identity_snapshot
from f03_testing import Services, application, real_actors

from rag_platform.documents.validation import MAX_BYTES
from rag_platform.providers.application_handoff import NAME, read_record
from rag_platform.providers.application_secrets import ApplicationSecretStore

DELIVERY = Path("/run/f03-application")
HOST = "rag-f03-api-candidate"


class Failure(RuntimeError):
    pass


def check(value, code):
    if not value:
        raise Failure(code)


class API:
    def __init__(self, humans):
        self.humans = humans
        self.pool = urllib3.HTTPSConnectionPool(
            HOST,
            9443,
            ssl_context=ssl.create_default_context(cafile="/tls/ca.crt"),
            server_hostname="api",
            assert_hostname="api",
            retries=False,
            maxsize=2,
            block=True,
            timeout=urllib3.Timeout(connect=3, read=30, total=35),
        )

    def call(self, user, method, path, *, body=None, headers=None, expected=200, chunked=False):
        headers = dict(headers or {})
        if user is not None:
            headers["Authorization"] = "Bearer " + self.humans.tokens(user)["access_token"]
        response = self.pool.urlopen(
            method,
            path,
            body=body,
            headers=headers,
            preload_content=False,
            chunked=chunked,
            retries=False,
        )
        try:
            check(
                response.status in expected
                if isinstance(expected, tuple)
                else response.status == expected,
                "HTTP_STATUS",
            )
            check(response.headers.get("Cache-Control") == "no-store", "CACHE_HEADER")
            UUID(response.headers["X-Request-ID"])
            data = response.read(256 * 1024 + 1)
            check(len(data) <= 256 * 1024, "RESPONSE_LIMIT")
            return data, response.headers.copy()
        finally:
            response.close()
            response.release_conn()

    def json(
        self,
        user,
        method,
        path,
        *,
        value=None,
        body=None,
        headers=None,
        expected=200,
        chunked=False,
    ):
        headers = dict(headers or {})
        if value is not None:
            body = json.dumps(value).encode()
            headers["Content-Type"] = "application/json"
        raw, result_headers = self.call(
            user, method, path, body=body, headers=headers, expected=expected, chunked=chunked
        )
        result = json.loads(raw)
        check(result["request_id"] == result_headers["X-Request-ID"], "REQUEST_ID")
        if expected >= 400:
            check(
                set(result) == {"error", "request_id"}
                and set(result["error"]) == {"version", "code"}
                and result["error"]["version"] == "v1",
                "ERROR_SHAPE",
            )
        return result

    def close(self):
        self.pool.close()


def formats():
    docx = io.BytesIO()
    with zipfile.ZipFile(docx, "w") as archive:
        for name, data in (
            (
                "[Content_Types].xml",
                b"<Types>application/vnd.openxmlformats-officedocument."
                b"wordprocessingml.document.main+xml</Types>",
            ),
            ("_rels/.rels", b"<Relationships/>"),
            ("word/document.xml", b"<document/>"),
        ):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    return (
        ("txt", "text/plain", b"F03 HTTP original fixture.\n"),
        ("md", "text/markdown", b"# F03\nPrivate fixture.\n"),
        ("pdf", "application/pdf", b"%PDF-1.7\nStructural fixture\n%%EOF\n"),
        (
            "docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            docx.getvalue(),
        ),
    )


def prove():
    humans, api = Humans(), None
    catalog = engine("migrator")
    stage = "START"
    records = []
    try:
        humans.ready()
        api = API(humans)
        fixtures = json.loads((ROOT / "ops/f03/repositories-fixture.json").read_text())["fixtures"]
        with session() as (day, _, _):
            with application(day) as store, Services(store=store) as services:
                actors = real_actors(services.control, humans)
                before = snapshot(catalog)
                identities_before = identity_snapshot(
                    services.control, [UUID(f["tenant"]) for f in fixtures]
                )

                for fixture in fixtures:
                    tag = fixture["name"].upper().replace("-", "_")
                    tenant, repo = UUID(fixture["tenant"]), UUID(fixture["repository"])
                    root = f"/api/v1/tenants/{tenant}/repositories"
                    path = root + f"/{repo}"
                    stage = tag + "/CRUD"
                    created = api.json(
                        "alice", "POST", root, value={"name": "http-" + uuid4().hex}, expected=201
                    )
                    temporary = created["repository"]["repository_id"]
                    temp = root + "/" + temporary
                    api.json(
                        "alice",
                        "PUT",
                        temp,
                        value={"name": "updated-" + uuid4().hex, "config": {"language": "es"}},
                    )
                    api.json(
                        "alice", "PUT", temp + f"/acl/{actors['bob']}", value={"role": "editor"}
                    )
                    api.json("bob", "GET", temp)
                    api.json(
                        "bob",
                        "PUT",
                        temp + f"/acl/{actors['bob']}",
                        value={"role": "owner"},
                        expected=403,
                    )
                    api.json("alice", "DELETE", temp + f"/acl/{actors['bob']}")
                    api.json("bob", "GET", temp, expected=403)
                    api.json("alice", "DELETE", temp)
                    api.json("alice", "GET", temp, expected=403)
                    api.json("bob", "POST", root, value={"name": "forbidden"}, expected=403)

                    stage = tag + "/FORMATS"
                    for extension, mime, body in formats():
                        stage = tag + "/FORMAT_" + extension.upper()
                        key = f"f03-http-{fixture['name']}-{extension}"
                        headers = {"Content-Type": mime, "Idempotency-Key": key}
                        endpoint = path + "/documents?filename=http-fixture." + extension
                        first_raw, _ = api.call(
                            "alice",
                            "POST",
                            endpoint,
                            body=body,
                            headers=headers,
                            expected=(200, 201),
                        )
                        first = json.loads(first_raw)["document"]
                        repeated = api.json("alice", "POST", endpoint, body=body, headers=headers)[
                            "document"
                        ]
                        check(
                            first == repeated
                            and first["sha256"] == hashlib.sha256(body).hexdigest(),
                            "IDEMPOTENCY",
                        )
                        doc = first["document_id"]
                        original = path + f"/documents/{doc}/original"
                        returned, response_headers = api.call("carol", "GET", original)
                        check(returned == body, "ORIGINAL_BYTES")
                        check(
                            response_headers.get("X-Content-Type-Options") == "nosniff"
                            and response_headers.get("Content-Disposition", "").startswith(
                                "attachment;"
                            )
                            and "filename*=UTF-8''http-fixture."
                            in response_headers.get("Content-Disposition", ""),
                            "DOWNLOAD_HEADERS",
                        )
                        check(int(response_headers["Content-Length"]) == len(body), "LENGTH")
                        api.json(None, "GET", original, expected=401)
                        api.json("dave", "GET", original, expected=403)
                        api.json("carol", "GET", path + f"/documents/{doc}")
                        records.append(
                            {
                                "tenant": str(tenant),
                                "repository": str(repo),
                                "document": doc,
                                "version": first["version_id"],
                                "format": extension,
                            }
                        )
                        if extension == "txt":
                            api.json(
                                "alice",
                                "POST",
                                endpoint,
                                body=body + b"different",
                                headers=headers,
                                expected=409,
                            )

                    stage = tag + "/NEGATIVES"
                    baseline = totals(services, actors["alice"], tenant)
                    bad = path + "/documents?filename=http-fixture.txt"
                    headers = {
                        "Content-Type": "text/plain",
                        "Idempotency-Key": "f03-http-invalid-" + fixture["name"],
                    }
                    for body in (b"\xff", b"%PDF-1.7\n%%EOF\n"):
                        api.json("alice", "POST", bad, body=body, headers=headers, expected=422)
                    api.json("carol", "POST", bad, body=b"synthetic", headers=headers, expected=403)
                    api.json("dave", "POST", bad, body=b"synthetic", headers=headers, expected=403)
                    api.json("alice", "GET", root + "/" + fixture["private"], expected=403)
                    foreign = next(f for f in fixtures if f["tenant"] != fixture["tenant"])
                    api.json("alice", "GET", root + "/" + foreign["repository"], expected=403)

                    # Enforce actual chunked bytes, without trusting a declared total.
                    def oversized():
                        for _ in range(MAX_BYTES // 65536):
                            yield b"x" * 65536
                        yield b"x"

                    api.json(
                        "alice",
                        "POST",
                        bad,
                        body=oversized(),
                        headers=headers,
                        expected=413,
                        chunked=True,
                    )
                    check(
                        totals(services, actors["alice"], tenant) == baseline,
                        "NEGATIVE_CREATED_ROWS",
                    )

                    stage = tag + "/CURSOR"
                    listing = api.json("alice", "GET", path + "/documents?limit=1")
                    check(len(listing["items"]) == 1 and listing["next_cursor"], "PAGINATION")
                    from urllib.parse import quote

                    cursor = quote(listing["next_cursor"], safe="")
                    api.json(
                        "bob", "GET", path + "/documents?limit=1&cursor=" + cursor, expected=422
                    )
                    next_page = api.json(
                        "alice", "GET", path + "/documents?limit=1&cursor=" + cursor
                    )
                    check(
                        next_page["items"][0]["document_id"] != listing["items"][0]["document_id"],
                        "CURSOR_DUPLICATE",
                    )
                    print(f"PASS T006 {tag}: CRUD/ACL HTTPS; formatos/replay/original correctos.")
                    print(f"PASS T006 {tag}: denegaciones y cursor correctos.")

                stage = "DELIVERY"
                first_fixture = fixtures[0]
                tenant, repo = first_fixture["tenant"], first_fixture["repository"]
                path = f"/api/v1/tenants/{tenant}/repositories/{repo}/documents"
                source = DELIVERY / NAME
                paused = DELIVERY / "api-check-paused.json"
                source.rename(paused)
                try:
                    api.json("alice", "GET", path, expected=503)
                finally:
                    paused.rename(source)
                api.json("alice", "GET", path)
                token = read_record(source)["token"]
                with ApplicationSecretStore(ENDPOINT, CA) as revoker:
                    revoker.attach_application(token)
                    revoker.revoke()
                api.json("alice", "GET", path, expected=503)
                ensure(day, DELIVERY, replace=True)
                api.json("alice", "GET", path)
                check(
                    day._request("GET", "/v1/auth/token/lookup-self")["data"]["meta"]["role_name"]
                    == "f01-dev-day",
                    "DAY_CHANGED",
                )
                print(
                    "PASS T006: ausente/revocado bloquean pools; reemplazo recupera; día intacto."
                )
                check(
                    snapshot(catalog) == before
                    and identity_snapshot(services.control, [UUID(f["tenant"]) for f in fixtures])
                    == identities_before,
                    "LEGACY_CHANGED",
                )
                print(
                    "F03 HTTP FIXTURES "
                    + json.dumps({"version": 1, "documents": records}, sort_keys=True)
                )
    except (Exception, KeyboardInterrupt) as error:
        code = str(error) if isinstance(error, Failure) else "REFUSED"
        raise SystemExit(f"F03 T006 HTTP {stage}: {code}; sin detalles sensibles.") from None
    finally:
        if api is not None:
            api.close()
        humans.close()
        catalog.dispose()


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    prove()
