"""Prove pinned MinIO conditional writes against owned, durably received fixtures."""

import json
import logging
from uuid import UUID, uuid4

import sqlalchemy as sa
from f01_daily import session
from f02_common import engine
from f02_testing import Humans
from f03_fixtures import ROOT, snapshot
from f03_testing import Services, application, real_actors
from minio.error import S3Error

from rag_platform.documents.errors import DocumentError
from rag_platform.documents.receipt import as_plan
from rag_platform.documents.schema import document_receipts
from rag_platform.documents.storage import Blob, conditional_put, inspect_object
from rag_platform.documents.validation import UploadSpool

BODY = b"F03 conditional streaming fixture.\n"


def prove():
    humans, catalog = Humans(), engine("migrator")
    stage = "IDENTITY"
    try:
        humans.ready()
        fixtures = json.loads((ROOT / "ops/f03/repositories-fixture.json").read_text())
        with session() as (day, _, _):
            before = snapshot(catalog)
            with application(day) as store, Services(store=store) as services:
                actors = real_actors(services.control, humans)
                references = []
                for item in fixtures["fixtures"]:
                    tag = item["name"].upper().replace("-", "_")
                    tenant, repo = UUID(item["tenant"]), UUID(item["repository"])
                    stage = tag + "/RECEIVE"
                    trace = uuid4()
                    context = services.authority.authorize(actors["alice"], tenant, trace)
                    key = "f03-conditional-" + item["name"]
                    with UploadSpool("f03-conditional.txt", "text/plain") as spool:
                        spool.accept(BODY)
                        file = spool.finish()
                        first = services.receipts.receive(context, trace, repo, key, file)

                        def lookup(c, checked, repo=repo, key=key):
                            services.repositories._row(c, checked, repo, "read")
                            return as_plan(
                                c.execute(
                                    sa.select(document_receipts).where(
                                        document_receipts.c.repository_id == repo,
                                        document_receipts.c.principal_id == actors["alice"],
                                        document_receipts.c.idempotency_key == key,
                                    )
                                ).one()
                            )

                        plan = services.repositories._run(context, trace, "read", lookup)
                        manifest = Blob(
                            plan.id,
                            repo,
                            plan.version_id,
                            plan.fingerprint,
                            file.content_hash,
                            file.byte_size,
                            file.mime,
                            file.md5,
                        )
                        stage = tag + "/OPEN_CLIENT"
                        with services.gateway.client(context, trace, repo, "upload") as (
                            s3,
                            bucket,
                        ):
                            stage = tag + "/STAT_BEFORE"
                            etag = inspect_object(s3, bucket, manifest)
                            original = s3.stat_object(bucket, manifest.key).last_modified
                            stage = tag + "/PUT_EXISTING"
                            try:
                                # The exact same owned bytes are used: even an unsupported
                                # server could not overwrite a foreign resource in this probe.
                                conditional_put(s3, bucket, manifest, file)
                            except S3Error as error:
                                if error.code != "PreconditionFailed":
                                    raise RuntimeError("WRONG_CONDITIONAL_DENIAL") from None
                            else:
                                raise RuntimeError("CONDITIONAL_NOT_ENFORCED")
                            stage = tag + "/STAT_AFTER"
                            after = s3.stat_object(bucket, manifest.key)
                            if after.etag != etag or after.last_modified != original:
                                raise RuntimeError("CONDITIONAL_CHANGED_OBJECT")
                        stage = tag + "/REPEAT"
                        repeated = services.receipts.receive(context, trace, repo, key, file)
                        if repeated.created or repeated.document != first.document:
                            raise RuntimeError("DUPLICATE_DOCUMENT")
                    with UploadSpool("f03-conditional.txt", "text/plain") as spool:
                        spool.accept(BODY + b"different")
                        try:
                            services.receipts.receive(context, trace, repo, key, spool.finish())
                        except DocumentError as error:
                            if error.code != "STATE_CONFLICT":
                                raise RuntimeError("WRONG_CONTENT_CONFLICT") from None
                        else:
                            raise RuntimeError("CONFLICT_NOT_ENFORCED")
                    references.append(
                        {
                            "name": item["name"],
                            "tenant": item["tenant"],
                            "repository": str(repo),
                            "document": first.document["document_id"],
                            "version": first.document["version_id"],
                        }
                    )
                    print(f"PASS T005 CONDITIONAL {tag}: streaming firmado; colisión HTTP 412.")
                    print(f"PASS T005 CONDITIONAL {tag}: objeto intacto; replay sin duplicados.")
                if snapshot(catalog) != before:
                    raise RuntimeError("LEGACY_CHANGED")
                print(
                    "F03 CONDITIONAL FIXTURES "
                    + json.dumps({"version": 1, "fixtures": references}, sort_keys=True)
                )
    except (Exception, KeyboardInterrupt) as error:
        allowed = {
            "WRONG_CONDITIONAL_DENIAL",
            "CONDITIONAL_NOT_ENFORCED",
            "CONDITIONAL_CHANGED_OBJECT",
            "DUPLICATE_DOCUMENT",
            "WRONG_CONTENT_CONFLICT",
            "CONFLICT_NOT_ENFORCED",
            "LEGACY_CHANGED",
        }
        code = (
            str(error)
            if type(error) is RuntimeError and str(error) in allowed
            else (error.code if isinstance(error, DocumentError) else "REFUSED")
        )
        if isinstance(error, S3Error):
            code = "S3_" + (
                error.code
                if error.code
                in {
                    "AccessDenied",
                    "NoSuchKey",
                    "InvalidRequest",
                    "SignatureDoesNotMatch",
                    "BadDigest",
                    "PreconditionFailed",
                    "RequestTimeTooSkewed",
                }
                else "REFUSED"
            )
        elif type(error).__name__ in {
            "MaxRetryError",
            "ProtocolError",
            "ReadTimeoutError",
            "SSLError",
            "NewConnectionError",
            "InvalidResponseError",
            "ServerError",
        }:
            code = "TRANSPORT_" + type(error).__name__
        raise SystemExit(f"F03 T005 CONDITIONAL {stage}: {code}; sin detalles sensibles.") from None
    finally:
        humans.close()
        catalog.dispose()


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    prove()
