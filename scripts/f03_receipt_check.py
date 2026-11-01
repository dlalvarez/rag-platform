"""Trusted T005 proof: real SQL/S3, retained fixtures, application-only child identities."""

import hashlib
import io
import json
import logging
import multiprocessing as mp
import os
import time
import zipfile
from contextlib import contextmanager
from dataclasses import replace
from uuid import UUID, uuid4

import sqlalchemy as sa
from f01_daily import session
from f02_common import engine
from f02_testing import Humans
from f03_fixtures import ROOT, snapshot
from f03_testing import Services, application, real_actors
from minio import Minio
from minio.error import S3Error

from rag_platform.documents.errors import DocumentError
from rag_platform.documents.receipt import ReceiptService, as_plan
from rag_platform.documents.schema import document_receipts, document_versions, documents, sources
from rag_platform.documents.storage import Blob, conditional_put
from rag_platform.documents.validation import UploadSpool
from rag_platform.provisioning.storage import StorageNames

BODY = b"F03 retained receipt fault fixture.\n"
LEASE = 6


class Failure(RuntimeError):
    pass


def check(value, code):
    if not value:
        raise Failure(code)


@contextmanager
def upload(body=BODY, name="receipt.txt", mime="text/plain"):
    with UploadSpool(name, mime) as spool:
        for start in range(0, len(body), 17):
            spool.accept(body[start : start + 17])
        yield spool.finish()


def context(services, actor, tenant):
    trace = uuid4()
    return services.authority.authorize(actor, tenant, trace), trace


def receive(services, actor, tenant, repo, key, *, file=None, service=None):
    ctx, trace = context(services, actor, tenant)
    receiver = service or services.receipts
    if file is not None:
        return receiver.receive(ctx, trace, repo, key, file)
    with upload() as file:
        return receiver.receive(ctx, trace, repo, key, file)


def query(services, actor, tenant, operation):
    ctx, trace = context(services, actor, tenant)
    return services.repositories._run(ctx, trace, "upload", operation)


def reservation(services, actor, tenant, key):
    def read(c, _):
        return c.execute(
            sa.select(document_receipts).where(
                document_receipts.c.principal_id == actor,
                document_receipts.c.idempotency_key == key,
            )
        ).one()

    return query(services, actor, tenant, read)


def totals(services, actor, tenant):
    def read(c, _):
        return tuple(
            c.scalar(sa.select(sa.func.count()).select_from(table))
            for table in (document_receipts, sources, documents, document_versions)
        )

    return query(services, actor, tenant, read)


def expired(services, actor, tenant, key):
    deadline = time.monotonic() + LEASE + 15
    while time.monotonic() < deadline:

        def ready(c, _):
            row = c.execute(
                sa.select(
                    document_receipts.c.lease_until,
                    sa.func.current_timestamp().label("now"),
                ).where(
                    document_receipts.c.idempotency_key == key,
                    document_receipts.c.principal_id == actor,
                )
            ).one()
            return row.lease_until is not None and row.lease_until <= row.now

        if query(services, actor, tenant, ready):
            return
        time.sleep(0.15)
    raise Failure("LEASE_DID_NOT_EXPIRE")


def manifest(row, repo, file):
    plan = as_plan(row)
    return Blob(
        plan.id,
        repo,
        plan.version_id,
        plan.fingerprint,
        file.content_hash,
        file.byte_size,
        file.mime,
        file.md5,
    )


def denied(function, code):
    try:
        function()
    except DocumentError as error:
        check(error.code == code, "WRONG_DENIAL")
    else:
        raise Failure("DENIAL_MISSING")


def child(channel, bearer, actor, tenant, repo, key, stage, crash, quota):
    logging.disable(logging.CRITICAL)
    try:
        with Services(bearer=bearer, lease_seconds=LEASE) as services:

            class Paused(ReceiptService):
                def _stage(self, current, plan):
                    if current == stage:
                        channel.send(("STAGE", plan.document_id, plan.version_id))
                        if crash:
                            os._exit(71)
                        check(channel.recv() == "CONTINUE", "WORKER_PROTOCOL")

            receiver = Paused(
                services.repositories, services.gateway, lease_seconds=LEASE, tenant_bytes=quota
            )
            channel.send(("READY",))
            check(channel.recv() == "GO", "WORKER_PROTOCOL")
            result = receive(services, actor, tenant, repo, key, service=receiver)
            channel.send(("RESULT", result.document, result.created))
    except DocumentError as error:
        channel.send(("DENIED", error.code))
    except BaseException:
        channel.send(("ERROR",))
    finally:
        channel.close()


def message(channel, seconds=90):
    check(channel.poll(seconds), "WORKER_TIMEOUT")
    try:
        return channel.recv()
    except EOFError:
        raise Failure("WORKER_EOF") from None


@contextmanager
def worker(day, actor, tenant, repo, key, *, stage, crash=False, quota=100 * 1024 * 1024):
    # Only an application bearer crosses private multiprocessing IPC, never the day token.
    with application(day) as app:
        parent, remote = mp.get_context("spawn").Pipe()
        process = mp.get_context("spawn").Process(
            target=child,
            args=(remote, app._store._token, actor, tenant, repo, key, stage, crash, quota),
        )
        process.start()
        remote.close()
        try:
            check(message(parent) == ("READY",), "WORKER_NOT_READY")
            parent.send("GO")
            yield parent, process
        finally:
            process.join(3)
            if process.is_alive():
                process.terminate()
            process.join(10)
            check(not process.is_alive(), "WORKER_NOT_STOPPED")
            parent.close()
            # application() revokes the child's bearer even after os._exit.


def counts_for(services, actor, tenant, row):
    def read(c, _):
        return tuple(
            c.scalar(sa.select(sa.func.count()).select_from(table).where(column == value))
            for table, column, value in (
                (sources, sources.c.id, __import__("uuid").uuid5(row.id, "source")),
                (documents, documents.c.id, row.candidate_document_id),
                (document_versions, document_versions.c.id, row.version_id),
            )
        )

    return query(services, actor, tenant, read)


def prove():
    humans, catalog = Humans(), engine("migrator")
    phase = "START"
    run = uuid4().hex
    artifacts = []
    try:
        humans.ready()
        fixtures = json.loads((ROOT / "ops/f03/repositories-fixture.json").read_text())["fixtures"]
        with session() as (day, _, _):
            before = snapshot(catalog)
            with application(day) as app, Services(store=app, lease_seconds=LEASE) as services:
                actors = real_actors(services.control, humans)
                actor = actors["alice"]
                for item in fixtures:
                    tag = item["name"].upper().replace("-", "_")
                    tenant, repo = UUID(item["tenant"]), UUID(item["repository"])
                    second = UUID(item["second"])
                    phase = tag + "/FORMATS"
                    docx = io.BytesIO()
                    with zipfile.ZipFile(docx, "w", zipfile.ZIP_DEFLATED) as z:
                        z.writestr(
                            "[Content_Types].xml",
                            '<Types><Override ContentType="application/vnd.'
                            "openxmlformats-officedocument."
                            'wordprocessingml.document.main+xml"/></Types>',
                        )
                        z.writestr("word/document.xml", "<document/>")
                        z.writestr("_rels/.rels", "<Relationships/>")
                    formats = (
                        ("txt", "text/plain", BODY),
                        ("md", "text/markdown", b"# F03\nPrivate markdown.\n"),
                        (
                            "pdf",
                            "application/pdf",
                            b"%PDF-1.7\nsynthetic structural fixture\n%%EOF\n",
                        ),
                        (
                            "docx",
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            docx.getvalue(),
                        ),
                    )
                    for ext, mime, body in formats:
                        phase = tag + "/FORMAT_" + ext.upper()
                        key = f"f03-formats-{run}-{ext}"
                        with upload(body, "fixture." + ext, mime) as file:
                            first = receive(services, actor, tenant, repo, key, file=file)
                            repeat = receive(services, actor, tenant, repo, key, file=file)
                            check(
                                first.created
                                and not repeat.created
                                and first.document == repeat.document,
                                "FORMAT_IDEMPOTENCY",
                            )
                            row = reservation(services, actor, tenant, key)
                            blob = manifest(row, repo, file)
                            ctx, trace = context(services, actor, tenant)
                            with services.gateway.original(ctx, trace, blob) as response:
                                digest, size = hashlib.sha256(), 0
                                while part := response.read(65536):
                                    digest.update(part)
                                    size += len(part)
                            check(
                                size == file.byte_size and digest.hexdigest() == file.content_hash,
                                "ORIGINAL_HASH",
                            )
                            artifacts.append(
                                {
                                    "tenant": str(tenant),
                                    "document": first.document["document_id"],
                                    "version": first.document["version_id"],
                                    "case": ext,
                                }
                            )

                    phase = tag + "/S3_ISOLATION"
                    with services.gateway.client(ctx, trace, repo, "read") as (client, bucket):
                        other = UUID(
                            next(f["tenant"] for f in fixtures if f["tenant"] != str(tenant))
                        )
                        for target, target_bucket in (
                            (client, StorageNames(other).bucket),
                            (
                                Minio(
                                    "minio:9000",
                                    secure=True,
                                    region="us-east-1",
                                    http_client=client._http,
                                ),
                                bucket,
                            ),
                        ):
                            try:
                                target.stat_object(target_bucket, blob.key)
                            except S3Error as error:
                                check(error.code == "AccessDenied", "WRONG_S3_DENIAL")
                            else:
                                raise Failure("S3_ACCESS_NOT_DENIED")

                    phase = tag + "/INVALID_ACL_QUOTA"
                    baseline = totals(services, actor, tenant)
                    # Invalid input is rejected before it can enter a receipt/S3 operation.
                    for body, name, mime, code in (
                        (b"%PDF-1.7\n%%EOF\n", "x.txt", "text/plain", "INPUT_INVALID"),
                        (b"\xff", "x.txt", "text/plain", "INPUT_INVALID"),
                        (b"x" * 17, "x.txt", "text/plain", "TOO_LARGE"),
                    ):

                        def invalid(body=body, name=name, mime=mime):
                            with UploadSpool(name, mime, max_bytes=16) as spool:
                                spool.accept(body)
                                spool.finish()

                        denied(invalid, code)
                    key = "f03-denied-" + run
                    for name, target in (
                        ("carol", repo),
                        ("dave", repo),
                        ("alice", UUID(item["private"])),
                    ):
                        denied(
                            lambda name=name, target=target, key=key, tenant=tenant: receive(
                                services, actors[name], tenant, target, key
                            ),
                            "ROLE_DENIED",
                        )
                    # A repository from another tenant is not usable with this tenant's context.
                    foreign = UUID(
                        next(f["repository"] for f in fixtures if f["tenant"] != str(tenant))
                    )
                    denied(
                        lambda foreign=foreign, key=key, tenant=tenant: receive(
                            services, actor, tenant, foreign, key
                        ),
                        "ROLE_DENIED",
                    )
                    limited = ReceiptService(
                        services.repositories, services.gateway, tenant_bytes=1
                    )
                    denied(
                        lambda key=key, limited=limited, repo=repo, tenant=tenant: receive(
                            services, actor, tenant, repo, key, service=limited
                        ),
                        "QUOTA_EXCEEDED",
                    )
                    check(totals(services, actor, tenant) == baseline, "INVALID_LEFT_ROWS")
                    print(
                        f"PASS T005 {tag}: formatos privados; hash/replay; denegaciones sin altas."
                    )

                    for boundary in ("OBJECT_AVAILABLE", "COMMITTED"):
                        phase = tag + "/" + boundary
                        key = f"f03-crash-{run}-{boundary}"
                        with worker(day, actor, tenant, repo, key, stage=boundary, crash=True) as (
                            pipe,
                            process,
                        ):
                            signal = message(pipe)
                            check(signal[0] == "STAGE", "CRASH_BOUNDARY")
                            process.join(10)
                            check(process.exitcode == 71, "PROCESS_DID_NOT_CRASH")
                        row = reservation(services, actor, tenant, key)
                        check(
                            (row.candidate_document_id, row.version_id) == signal[1:],
                            "CRASH_IDS_CHANGED",
                        )
                        if boundary == "OBJECT_AVAILABLE":
                            check(
                                row.state == "PENDING"
                                and counts_for(services, actor, tenant, row) == (0, 0, 0),
                                "PREMATURE_RECEIVED",
                            )
                            with upload() as file:
                                ctx, trace = context(services, actor, tenant)
                                check(
                                    services.gateway.inspect(ctx, trace, manifest(row, repo, file))
                                    is not None,
                                    "CRASH_OBJECT_MISSING",
                                )
                            expired(services, actor, tenant, key)
                        replay = receive(services, actor, tenant, repo, key)
                        check(
                            replay.created == (boundary == "OBJECT_AVAILABLE"),
                            "CRASH_REPLAY_STATUS",
                        )
                        check(
                            (
                                UUID(replay.document["document_id"]),
                                UUID(replay.document["version_id"]),
                            )
                            == signal[1:],
                            "CRASH_DUPLICATE",
                        )
                        check(
                            counts_for(services, actor, tenant, row) == (1, 1, 1),
                            "CRASH_ROW_COUNTS",
                        )
                        check(
                            not receive(services, actor, tenant, repo, key).created,
                            "CRASH_SECOND_REPLAY",
                        )

                    phase = tag + "/CONCURRENCY"
                    key = "f03-race-" + run
                    with worker(day, actor, tenant, repo, key, stage="RESERVED") as (pipe, _):
                        check(message(pipe)[0] == "STAGE", "RACE_BOUNDARY")
                        denied(
                            lambda key=key, repo=repo, tenant=tenant: receive(
                                services, actor, tenant, repo, key
                            ),
                            "OPERATION_IN_PROGRESS",
                        )
                        pipe.send("CONTINUE")
                        check(message(pipe)[0] == "RESULT", "RACE_RESULT")
                    row = reservation(services, actor, tenant, key)
                    check(counts_for(services, actor, tenant, row) == (1, 1, 1), "RACE_DUPLICATED")

                    phase = tag + "/FENCING"
                    key = "f03-fence-" + run
                    with worker(day, actor, tenant, repo, key, stage="RESERVED") as (pipe, _):
                        check(message(pipe)[0] == "STAGE", "FENCE_BOUNDARY")
                        row = reservation(services, actor, tenant, key)
                        expired(services, actor, tenant, key)
                        accepted = receive(services, actor, tenant, repo, key)
                        check(
                            UUID(accepted.document["document_id"]) == row.candidate_document_id,
                            "FENCE_NEW_IDS",
                        )
                        pipe.send("CONTINUE")
                        check(
                            message(pipe) == ("DENIED", "STATE_CONFLICT"), "STALE_WORKER_ACCEPTED"
                        )
                    check(counts_for(services, actor, tenant, row) == (1, 1, 1), "FENCE_DUPLICATED")

                    phase = tag + "/SQL_ROLLBACK"
                    key = "f03-sql-fault-" + run
                    original_event = services.repositories.event

                    def fault(c, *_):
                        c.execute(sa.text("SELECT 1 / 0"))

                    services.repositories.event = fault
                    try:
                        denied(
                            lambda key=key, repo=repo, tenant=tenant: receive(
                                services, actor, tenant, repo, key
                            ),
                            "DEPENDENCY_UNAVAILABLE",
                        )
                    finally:
                        services.repositories.event = original_event
                    row = reservation(services, actor, tenant, key)
                    check(
                        row.state == "OBJECT_STORED"
                        and counts_for(services, actor, tenant, row) == (0, 0, 0),
                        "SQL_ROLLBACK_FAILED",
                    )
                    expired(services, actor, tenant, key)
                    recovered = receive(services, actor, tenant, repo, key)
                    check(
                        UUID(recovered.document["document_id"]) == row.candidate_document_id,
                        "SQL_RECOVERY_NEW_IDS",
                    )
                    check(
                        counts_for(services, actor, tenant, row) == (1, 1, 1),
                        "SQL_RECOVERY_DUPLICATED",
                    )

                    phase = tag + "/FOREIGN_OBJECT"
                    key = "f03-collision-" + run
                    collision = {}

                    class Collision(ReceiptService):
                        def _stage(
                            self, stage, plan, repo=repo, tenant=tenant, collision=collision
                        ):
                            if stage != "RESERVED":
                                return
                            with upload() as file:
                                blob = Blob(
                                    plan.id,
                                    repo,
                                    plan.version_id,
                                    plan.fingerprint,
                                    file.content_hash,
                                    file.byte_size,
                                    file.mime,
                                    file.md5,
                                )
                                foreign_blob = replace(blob, receipt_id=uuid4())
                                ctx, trace = context(services, actor, tenant)
                                with services.gateway.client(ctx, trace, repo, "upload") as (
                                    s3,
                                    bucket,
                                ):
                                    conditional_put(s3, bucket, foreign_blob, file)
                                    value = s3.stat_object(bucket, blob.key)
                                    collision["blob"] = blob
                                    collision["before"] = (
                                        value.etag,
                                        value.last_modified,
                                        {
                                            k.lower(): v
                                            for k, v in value.metadata.items()
                                            if k.lower().startswith("x-amz-meta-")
                                        },
                                    )

                    receiver = Collision(
                        services.repositories, services.gateway, lease_seconds=LEASE
                    )
                    denied(
                        lambda receiver=receiver, tenant=tenant, repo=repo, key=key: receive(
                            services, actor, tenant, repo, key, service=receiver
                        ),
                        "STATE_CONFLICT",
                    )
                    row = reservation(services, actor, tenant, key)
                    check(
                        row.state == "PENDING"
                        and counts_for(services, actor, tenant, row) == (0, 0, 0),
                        "COLLISION_ADOPTED",
                    )
                    expired(services, actor, tenant, key)
                    denied(
                        lambda tenant=tenant, repo=repo, key=key: receive(
                            services, actor, tenant, repo, key
                        ),
                        "STATE_CONFLICT",
                    )
                    ctx, trace = context(services, actor, tenant)
                    with services.gateway.client(ctx, trace, repo, "upload") as (s3, bucket):
                        value = s3.stat_object(bucket, collision["blob"].key)
                        check(
                            (
                                value.etag,
                                value.last_modified,
                                {
                                    k.lower(): v
                                    for k, v in value.metadata.items()
                                    if k.lower().startswith("x-amz-meta-")
                                },
                            )
                            == collision["before"],
                            "FOREIGN_OBJECT_CHANGED",
                        )

                    with services.gateway.client(ctx, trace, repo, "read") as (s3, bucket):
                        response = s3.get_object(bucket, collision["blob"].key)
                        digest = hashlib.sha256()
                        try:
                            while piece := response.read(65536):
                                digest.update(piece)
                        finally:
                            response.close()
                            response.release_conn()
                        check(
                            digest.hexdigest() == hashlib.sha256(BODY).hexdigest(),
                            "FOREIGN_BODY_CHANGED",
                        )

                    phase = tag + "/CROSS_REPOSITORY_QUOTA"
                    used = query(
                        services,
                        actor,
                        tenant,
                        lambda c, _: c.scalar(
                            sa.select(
                                sa.func.coalesce(sa.func.sum(document_receipts.c.byte_size), 0)
                            )
                        ),
                    )
                    quota = int(used) + len(BODY)
                    key = "f03-quota-a-" + run
                    with worker(day, actor, tenant, repo, key, stage="RESERVED", quota=quota) as (
                        pipe,
                        _,
                    ):
                        check(message(pipe)[0] == "STAGE", "QUOTA_BOUNDARY")
                        limited = ReceiptService(
                            services.repositories, services.gateway, tenant_bytes=quota
                        )
                        denied(
                            lambda limited=limited, second=second, tenant=tenant: receive(
                                services,
                                actor,
                                tenant,
                                second,
                                "f03-quota-b-" + run,
                                service=limited,
                            ),
                            "QUOTA_EXCEEDED",
                        )
                        pipe.send("CONTINUE")
                        check(message(pipe)[0] == "RESULT", "QUOTA_RESULT")
                    final = query(
                        services,
                        actor,
                        tenant,
                        lambda c, _: c.scalar(
                            sa.select(sa.func.sum(document_receipts.c.byte_size))
                        ),
                    )
                    check(final == quota, "QUOTA_OVERFLOW")
                    print(f"PASS T005 {tag}: caída tras PUT/COMMIT; mismos IDs y una versión.")
                    print(f"PASS T005 {tag}: SQL/cuota/fencing; colisión intacta; S3 denegado.")

                phase = "PRESERVATION"
                check(snapshot(catalog) == before, "LEGACY_CHANGED")
                print(
                    "F03 RECEIPT FIXTURES "
                    + json.dumps({"version": 1, "run": run, "documents": artifacts}, sort_keys=True)
                )
                print("PASS T005: identidades hijas revocadas; recursos conservados; F03 abierta.")
    except (Exception, KeyboardInterrupt) as error:
        code = (
            error.code
            if isinstance(error, DocumentError)
            else (str(error) if isinstance(error, Failure) else "REFUSED")
        )
        raise SystemExit(f"F03 T005 RECEIPT {phase}: {code}; sin detalles sensibles.") from None
    finally:
        humans.close()
        catalog.dispose()


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    prove()
