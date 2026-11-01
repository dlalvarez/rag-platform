"""Final F03 provider isolation and logical deletion with retained content, no cleanup purge."""

import json
import logging
from uuid import UUID, uuid4

import psycopg
import sqlalchemy as sa
from f01_daily import session
from f01_operator import CA
from f02_common import engine
from f02_isolation_check import expected_cross_rejection
from f02_testing import Humans
from f03_fixtures import ROOT, snapshot
from f03_http_check import API, formats
from f03_testing import Services, application, real_actors
from minio import Minio
from minio.error import S3Error
from psycopg import sql

from rag_platform.documents.schema import (
    audit_events,
    document_receipts,
    document_versions,
    documents,
    repositories,
    repository_acl,
    sources,
)
from rag_platform.provisioning.postgres import Target
from rag_platform.provisioning.storage import REGION, StorageNames
from rag_platform.tenancy.resolver import AdministrativeTenant


class Failure(RuntimeError):
    pass


def require(value, code):
    if not value:
        raise Failure(code)


def object_state(info):
    return (
        info.etag,
        info.size,
        info.last_modified,
        {k.lower(): v for k, v in info.metadata.items() if k.lower().startswith("x-amz-meta-")},
    )


def denied_object(client, bucket, key):
    for method in ("HEAD", "GET"):
        try:
            if method == "HEAD":
                client.stat_object(bucket, key)
            else:
                response = client.get_object(bucket, key)
                response.close()
                response.release_conn()
        except S3Error as error:
            try:
                require(
                    error.code == "AccessDenied" and error.response.status == 403,
                    "WRONG_S3_CROSS_DENIAL",
                )
            finally:
                error.response.close()
                error.response.release_conn()
                client._http.clear()
        else:
            raise Failure("S3_CROSS_ALLOWED")


def prove():
    humans, api, catalog = Humans(), None, engine("migrator")
    phase, retained = "START", []
    try:
        humans.ready()
        api = API(humans)
        fixtures = json.loads((ROOT / "ops/f03/repositories-fixture.json").read_text())["fixtures"]
        manifest = json.loads((ROOT / "ops/f03/http-fixture.json").read_text())["documents"]
        by_name = {f["name"]: f for f in fixtures}
        with session() as (day, _, _):
            before = snapshot(catalog)
            with application(day) as store, Services(store=store) as services:
                actors = real_actors(services.control, humans)
                for label, names in (
                    ("SAME_INSTANCE", ("same-a", "same-b")),
                    ("TWO_INSTANCES", ("two-a", "two-b")),
                ):
                    for source_name, destination_name in (names, names[::-1]):
                        own, other = by_name[source_name], by_name[destination_name]
                        tenant, foreign = UUID(own["tenant"]), UUID(other["tenant"])
                        for role in ("app", "readonly"):
                            phase = label + "/" + role.upper()
                            source = services.registry.resolver.resolve(
                                AdministrativeTenant(tenant), role
                            )
                            destination = services.registry.resolver.resolve(
                                AdministrativeTenant(foreign), role
                            )
                            credential = store.read(source.credential)
                            with Target(source.host, source.port, CA).connect(
                                source.database, credential
                            ) as connection:
                                current = connection.execute(
                                    "SELECT current_database(),current_user,"
                                    "(SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid())"
                                ).fetchone()
                                require(
                                    current == (source.database, source.username, True),
                                    "WRONG_SQL_DESTINATION",
                                )
                                flags = connection.execute(
                                    "SELECT rolsuper,rolcreatedb,rolcreaterole,rolbypassrls "
                                    "FROM pg_roles WHERE rolname=current_user"
                                ).fetchone()
                                require(flags == (False, False, False, False), "SQL_PRIVILEGED")
                                if role == "readonly":
                                    try:
                                        with connection.transaction():
                                            connection.execute(
                                                "UPDATE knowledge.documents "
                                                "SET state=state WHERE FALSE"
                                            )
                                    except psycopg.Error as error:
                                        require(error.sqlstate == "42501", "WRONG_READONLY_DENIAL")
                                    else:
                                        raise Failure("READONLY_WRITE_ALLOWED")
                                if source.host == destination.host:
                                    try:
                                        with connection.transaction():
                                            connection.execute(
                                                sql.SQL("SET ROLE {}").format(
                                                    sql.Identifier(destination.username)
                                                )
                                            )
                                    except psycopg.Error as error:
                                        require(error.sqlstate == "42501", "WRONG_ROLE_DENIAL")
                                    else:
                                        raise Failure("CROSS_ROLE_ALLOWED")
                            try:
                                cross = Target(destination.host, destination.port, CA).connect(
                                    destination.database, credential
                                )
                            except psycopg.Error as error:
                                require(
                                    expected_cross_rejection(
                                        error, source, destination, credential.username
                                    ),
                                    "WRONG_SQL_CROSS_DENIAL",
                                )
                            else:
                                cross.close()
                                raise Failure("SQL_CROSS_ALLOWED")
                        phase = label + "/S3"
                        own_record = next(
                            r
                            for r in manifest
                            if r["tenant"] == own["tenant"] and r["format"] == "txt"
                        )
                        other_record = next(
                            r
                            for r in manifest
                            if r["tenant"] == other["tenant"] and r["format"] == "txt"
                        )
                        trace = uuid4()
                        ctx = services.authority.authorize(actors["alice"], tenant, trace)
                        with services.gateway.client(
                            ctx, trace, UUID(own["repository"]), "read"
                        ) as (s3, bucket):
                            own_key = (
                                f"f03/{UUID(own['repository']).hex}/"
                                f"{UUID(own_record['version']).hex}"
                            )
                            other_key = (
                                f"f03/{UUID(other['repository']).hex}/"
                                f"{UUID(other_record['version']).hex}"
                            )
                            s3.stat_object(bucket, own_key)
                            response = s3.get_object(bucket, own_key)
                            try:
                                require(
                                    response.read(65536) == formats()[0][2], "WRONG_S3_ORIGINAL"
                                )
                            finally:
                                response.close()
                                response.release_conn()
                            denied_object(s3, StorageNames(foreign).bucket, other_key)
                            anonymous = Minio(
                                "minio:9000", secure=True, region=REGION, http_client=s3._http
                            )
                            denied_object(anonymous, bucket, own_key)
                    print(f"PASS T007 PROVIDERS {label}: TLS y SQL/S3 aislados.")

                for item in fixtures:
                    tag = item["name"].upper().replace("-", "_")
                    phase = tag + "/RETENTION"
                    tenant = UUID(item["tenant"])
                    root = f"/api/v1/tenants/{tenant}/repositories"
                    created = api.json(
                        "alice",
                        "POST",
                        root,
                        value={"name": "retained-" + uuid4().hex},
                        expected=201,
                    )
                    repo = UUID(created["repository"]["repository_id"])
                    path = root + "/" + str(repo)
                    received = api.json(
                        "alice",
                        "POST",
                        path + "/documents?filename=retained.txt",
                        body=b"F03 lifecycle retained original.\n",
                        headers={
                            "Content-Type": "text/plain",
                            "Idempotency-Key": "f03-lifecycle-" + uuid4().hex,
                        },
                        expected=201,
                    )["document"]
                    doc, version, source_id = (
                        UUID(received[k]) for k in ("document_id", "version_id", "source_id")
                    )
                    key = f"f03/{repo.hex}/{version.hex}"
                    trace = uuid4()
                    ctx = services.authority.authorize(actors["alice"], tenant, trace)
                    with services.gateway.client(ctx, trace, repo, "read") as (s3, bucket):
                        before_object = object_state(s3.stat_object(bucket, key))
                        api.json("alice", "DELETE", path)
                        api.json("alice", "GET", path + f"/documents/{doc}", expected=403)
                        api.json("alice", "GET", path + f"/documents/{doc}/original", expected=403)
                        require(
                            object_state(s3.stat_object(bucket, key)) == before_object,
                            "DELETE_CHANGED_OBJECT",
                        )
                    with services.connections.connection(ctx, trace) as c:
                        require(
                            c.scalar(
                                sa.select(repositories.c.state).where(repositories.c.id == repo)
                            )
                            == "DELETED",
                            "LOGICAL_DELETE_MISSING",
                        )
                        for table, column, value in (
                            (documents, documents.c.id, doc),
                            (document_versions, document_versions.c.id, version),
                            (sources, sources.c.id, source_id),
                            (repository_acl, repository_acl.c.repository_id, repo),
                        ):
                            require(
                                c.scalar(
                                    sa.select(sa.func.count())
                                    .select_from(table)
                                    .where(column == value)
                                )
                                == 1,
                                "CONTENT_HISTORY_LOST",
                            )
                        require(
                            c.scalar(
                                sa.select(document_receipts.c.state).where(
                                    document_receipts.c.committed_version_id == version
                                )
                            )
                            == "COMMITTED",
                            "RECEIPT_HISTORY_LOST",
                        )
                        require(
                            c.scalar(
                                sa.select(sa.func.count())
                                .select_from(audit_events)
                                .where(
                                    audit_events.c.target_id == repo,
                                    audit_events.c.action == "REPOSITORY_DELETED",
                                )
                            )
                            == 1,
                            "AUDIT_LOST",
                        )
                    retained.append(
                        {
                            "tenant": str(tenant),
                            "repository": str(repo),
                            "document": str(doc),
                            "version": str(version),
                            "source": str(source_id),
                            "state": "DELETED",
                        }
                    )
                    print(
                        f"PASS T007 RETENTION {tag}: documento/original/ACL/auditoría conservados."
                    )
                require(snapshot(catalog) == before, "LEGACY_CHANGED")
                print(
                    "F03 LIFECYCLE FIXTURES "
                    + json.dumps({"version": 1, "fixtures": retained}, sort_keys=True)
                )
                print("PASS T007 PROVIDERS: aislamiento y recursos conservados; sin purge.")
    except (Exception, KeyboardInterrupt) as error:
        code = str(error) if isinstance(error, Failure) else "REFUSED"
        raise SystemExit(f"F03 T007 PROVIDERS {phase}: {code}; sin detalles sensibles.") from None
    finally:
        if api is not None:
            api.close()
        humans.close()
        catalog.dispose()


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    prove()
