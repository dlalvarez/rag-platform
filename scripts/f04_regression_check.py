"""F01/F02/F03 regressions on F04 fixtures, with application-only credentials."""

import hashlib
import json
import logging
import re
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import sqlalchemy as sa
from f01_sql_check import expected_startup_rejection
from f02_testing import Humans
from f03_http_check import API
from f03_testing import real_actors
from f04_api_check import CA, OUT, ROOT, candidate, local

from rag_platform.identity_api import private_file
from rag_platform.ingestion.logging_setup import SETTINGS
from rag_platform.ingestion.runtime import Runtime
from rag_platform.ingestion.schema import chunks
from rag_platform.providers.secrets import Credential
from rag_platform.provisioning.postgres import Target
from rag_platform.provisioning.storage import StorageNames
from rag_platform.tenancy.resolver import AdministrativeTenant, control_engine

PHASE = "START"


def denied(function, allowed):
    try:
        result = function()
    except psycopg.Error as error:
        assert error.sqlstate in allowed
        return
    if hasattr(result, "close"):
        result.close()
    raise AssertionError("DENIAL_REQUIRED")


def denied_connect(target, database, credential, *, same_instance):
    try:
        with target.connect(database, credential):
            pass
    except psycopg.OperationalError as error:
        if same_instance:
            assert expected_startup_rejection(error, database, credential.username, "42501")
        else:
            signature = (
                r'FATAL:\s+password authentication failed for user "'
                + re.escape(credential.username)
                + r'"'
            )
            assert error.sqlstate in (None, "28P01", "28000") and re.search(signature, str(error))
        return
    raise AssertionError("CROSS_CONNECT_ALLOWED")


def sql_checks(runtime, fixture, fixtures):
    tenant = UUID(fixture["tenant"])
    resolver = runtime.registry.resolver
    for role in ("app", "readonly"):
        own = resolver.resolve(AdministrativeTenant(tenant), role)
        credential = runtime.store.read(own.credential)
        assert credential.username == own.username
        with Target(own.host, own.port, CA).connect(own.database, credential, autocommit=True) as c:
            assert c.execute(
                "SELECT current_database(),current_user,"
                "(SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid())"
            ).fetchone() == (own.database, own.username, True)
            assert (
                c.execute(
                    "SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls "
                    "FROM pg_roles WHERE rolname=current_user"
                ).fetchone()
                == (False,) * 5
            )
            assert c.execute("SELECT '[1,2,3]'::vector <-> '[1,2,4]'::vector").fetchone() == (1.0,)
            with c.transaction():
                denied(lambda: c.execute("DELETE FROM knowledge.documents WHERE false"), {"42501"})
            if role == "readonly":
                assert not c.execute(
                    "SELECT has_schema_privilege(current_user,'ops','USAGE')"
                ).fetchone()[0]
                with c.transaction():
                    denied(
                        lambda: c.execute("UPDATE knowledge.documents SET state=state WHERE false"),
                        {"42501"},
                    )
            for foreign in fixtures:
                if foreign["tenant"] == fixture["tenant"]:
                    continue
                target = resolver.resolve(AdministrativeTenant(UUID(foreign["tenant"])), "app")
                if own.host == target.host:
                    with c.transaction():
                        denied(
                            lambda c=c, target=target: c.execute(
                                psycopg.sql.SQL("SET ROLE {}").format(
                                    psycopg.sql.Identifier(target.username)
                                )
                            ),
                            {"42501"},
                        )
                if own.host == target.host:
                    assert c.execute(
                        "SELECT has_database_privilege(current_user,%s,'CONNECT')",
                        (target.database,),
                    ).fetchone() == (False,)
                denied_connect(
                    Target(target.host, target.port, CA),
                    target.database,
                    credential,
                    same_instance=own.host == target.host,
                )
        del credential


def s3_checks(runtime, actors, fixture, fixtures):
    item = next(i for i in fixture["documents"] if i["case"] == "atomic")
    trace = uuid4()
    ctx = runtime.authority.authorize(actors["alice"], UUID(fixture["tenant"]), trace)
    with runtime.gateway.client(ctx, trace, UUID(fixture["repository"]), "read") as (
        client,
        bucket,
    ):
        key = "f03/" + UUID(fixture["repository"]).hex + "/" + UUID(item["original"]).hex
        assert client.stat_object(bucket, key).size == item["byte_size"]
        response = client.get_object(bucket, key)
        try:
            data = response.read(1024 * 1024)
            assert (
                len(data) == item["byte_size"]
                and hashlib.sha256(data).hexdigest() == item["sha256"]
            )
        finally:
            response.close()
            response.release_conn()
        assert key in {x.object_name for x in client.list_objects(bucket, prefix=key)}
        from minio.error import S3Error

        for other in fixtures:
            if other["tenant"] == fixture["tenant"]:
                continue
            target_bucket = StorageNames(UUID(other["tenant"])).bucket
            foreign = next(i for i in other["documents"] if i["case"] == "atomic")
            foreign_key = (
                "f03/" + UUID(other["repository"]).hex + "/" + UUID(foreign["original"]).hex
            )
            for probe in (
                lambda target_bucket=target_bucket, foreign_key=foreign_key: client.stat_object(
                    target_bucket, foreign_key
                ),
                lambda target_bucket=target_bucket, foreign_key=foreign_key: client.get_object(
                    target_bucket, foreign_key
                ),
                lambda target_bucket=target_bucket, foreign_key=foreign_key: list(
                    client.list_objects(target_bucket, prefix=foreign_key)
                ),
            ):
                try:
                    result = probe()
                except S3Error as error:
                    assert error.code == "AccessDenied"
                else:
                    if hasattr(result, "close"):
                        result.close()
                    raise AssertionError("S3_DENIAL_REQUIRED")


def privacy(runtime, actors, fixture):
    item = next(i for i in fixture["documents"] if i["case"] == "atomic")
    with local(runtime, actors, fixture) as c, c.begin():
        for name, value in SETTINGS.items():
            assert c.scalar(sa.text("SELECT current_setting(:name)"), {"name": name}) == value
        piece = (
            c.execute(sa.select(chunks).where(chunks.c.version_id == candidate(item)))
            .mappings()
            .first()
        )
        assert "F04_API_PRIVATE_CANARY" in piece["text"]
        c.execute(sa.text("DO $$ BEGIN RAISE LOG 'F04_T007_LOG_POSITIVE'; END $$"))
        try:
            with c.begin_nested():
                values = dict(piece)
                values["id"] = uuid4()
                c.execute(chunks.insert().values(**values))
        except sa.exc.DBAPIError as error:
            assert getattr(error.orig, "sqlstate", None) == "23514"
        else:
            raise AssertionError("LATE_INSERT_REQUIRED_DENIED")


def legacy(api):
    data = json.loads((ROOT / "ops/f03/http-fixture.json").read_text())["documents"]
    for item in data:
        prefix = "/api/v1/tenants/" + item["tenant"]
        base = prefix + "/repositories/" + item["repository"] + "/documents/" + item["document"]
        doc = api.json("carol", "GET", base)["document"]
        assert doc["version_id"] == item["version"]
        body, _ = api.call("carol", "GET", base + "/original")
        assert hashlib.sha256(body).hexdigest() == doc["sha256"] and len(body) == doc["byte_size"]
        page = api.json("carol", "GET", prefix + "/documents/" + item["document"] + "/versions")
        assert len(page["items"]) == 1 and page["items"][0]["kind"] == "ORIGINAL"
        assert page["items"][0]["version_id"] == item["version"]
        assert page["items"][0]["job_id"] is None
        api.json("dave", "GET", base + "/original", expected=403)
    print(
        "PASS T007 F03: historical originals/metadata/SHA/ACL retained; no retroactive ingestion",
        flush=True,
    )


def main():
    global PHASE
    humans, api, control, runtime = None, None, None, None
    try:
        humans = Humans()
        humans.ready()
        api = API(humans)
        control = control_engine(
            Target("postgres", 5432, CA),
            Credential(
                "f02_identity_app",
                private_file("/run/secrets/identity_app_password", 4096).decode(),
            ),
        )
        actors = real_actors(control, humans)
        runtime = Runtime(
            control,
            private_file("/run/secrets/api_authority_key", 32),
            Path("/run/f04-worker"),
            "https://openbao:8200",
            CA,
            ROOT / "ops/f03/application-scope.json",
        )
        runtime.preflight()
        manifest = json.loads(private_file(OUT / "manifest.json", 512 * 1024))
        assert manifest["actors"] == {k: str(v) for k, v in actors.items()}
        expected = json.loads((ROOT / "ops/f03/application-scope.json").read_text())["fixtures"]
        assert [(f["name"], f["tenant"]) for f in manifest["fixtures"]] == [
            (f["name"], f["tenant"]) for f in expected
        ]
        PHASE = "F02"
        api.json("alice", "GET", "/api/v1/me")
        api.json(None, "GET", "/api/v1/me", expected=401)
        api.json("alice", "GET", "/api/v1/tenants")
        api.json("alice", "GET", "/api/v1/tenants?host=untrusted", expected=422)
        print(
            "PASS T007 F02: real OIDC/global identity/tenant context; missing JWT/query denied",
            flush=True,
        )
        for fixture in manifest["fixtures"]:
            PHASE = fixture["name"] + "/SQL"
            sql_checks(runtime, fixture, manifest["fixtures"])
            PHASE = fixture["name"] + "/S3"
            s3_checks(runtime, actors, fixture, manifest["fixtures"])
            PHASE = fixture["name"] + "/PRIVACY"
            privacy(runtime, actors, fixture)
            print(
                "PASS T007 "
                + fixture["name"].upper()
                + ": SQL/TLS/vector/roles/cross CONNECT+SET ROLE and S3 own/cross; privacy probe",
                flush=True,
            )
        PHASE = "F03_HISTORY"
        legacy(api)
        assert runtime.registry.stats()["leases"] == 0
        print(
            "PASS T007 REGRESSION: no credentials/data rotated; all resources retained", flush=True
        )
    finally:
        if runtime is not None:
            runtime.close()
        if control is not None:
            control.dispose()
        if api is not None:
            api.close()
        if humans is not None:
            humans.close()


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    try:
        main()
    except Exception as error:
        state = getattr(getattr(error, "orig", error), "sqlstate", None)
        code = (
            "SQLSTATE_" + state
            if isinstance(state, str) and len(state) == 5 and state.isalnum()
            else "REFUSED"
        )
        print("F04-T007 " + PHASE + " " + type(error).__name__ + " " + code, flush=True)
        raise SystemExit(1) from None
