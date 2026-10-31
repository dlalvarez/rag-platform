"""Non-tenant T006 calibration on the new instance; not a SecretStore fallback."""

import logging
import multiprocessing
import secrets
import time
from pathlib import Path
from uuid import uuid4

from f01_isolation_check import Fixture, fail_revision, fixture_snapshot, reversible
from psycopg import sql

from rag_platform.providers.secrets import Credential
from rag_platform.provisioning.migrations import (
    VERSION,
    MigrationError,
    migrate_initial,
    migration_session,
)
from rag_platform.provisioning.postgres import Names, Target, create_role, execute

CA = Path("/run/f01-ca.crt")
ROOT = Path(__file__).resolve().parents[1]


def holder(pipe, names):
    try:
        credential = pipe.recv()
        with migration_session(Target("postgres2", 5432, CA), names, credential):
            pipe.send("LOCKED")
            if not pipe.poll(30) or pipe.recv() != "GO":
                raise MigrationError()
        pipe.send("COMMITTED")
    except Exception:
        pipe.send("FAILED")
    finally:
        pipe.close()


def main():
    logging.disable(logging.CRITICAL)
    target = Target("postgres2", 5432, CA)
    bootstrap = Credential("f01_bootstrap", Path("/run/secrets/postgres2_password").read_text())
    names = Names(uuid4(), uuid4())
    credential = Credential(names.role("migrator"), secrets.token_urlsafe(36))
    created = False
    try:
        with target.connect("rag_control", bootstrap, autocommit=True) as connection:
            with connection.transaction():
                for kind in ("owner", "migrator", "app", "readonly"):
                    create_role(
                        connection,
                        names.role(kind),
                        names.marker,
                        credential.password if kind == "migrator" else None,
                    )
                execute(
                    connection,
                    "GRANT {} TO {} WITH ADMIN FALSE,INHERIT FALSE,SET TRUE",
                    names.role("owner"),
                    names.role("migrator"),
                )
            execute(
                connection,
                "CREATE DATABASE {} OWNER {} TEMPLATE template0 ALLOW_CONNECTIONS false",
                names.database,
                names.role("owner"),
            )
            created = True
            connection.execute(
                sql.SQL("COMMENT ON DATABASE {} IS {}").format(
                    sql.Identifier(names.database), sql.Literal(names.marker)
                )
            )
            execute(connection, "REVOKE ALL ON DATABASE {} FROM PUBLIC", names.database)
            execute(
                connection,
                "GRANT CONNECT ON DATABASE {} TO {}",
                names.database,
                names.role("migrator"),
            )
            execute(connection, "ALTER DATABASE {} ALLOW_CONNECTIONS true", names.database)
        with target.connect(names.database, bootstrap) as connection:
            connection.execute("CREATE EXTENSION vector WITH SCHEMA public")
            connection.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        assert migrate_initial(target, names, credential, ROOT) == VERSION
        fixture = Fixture(None, target, names, {"migrator": credential})
        reversible(fixture)
        before = fixture_snapshot(fixture)
        try:
            fail_revision(target, names, credential, ROOT)
        except MigrationError as error:
            assert error.code == "MIGRATION_FAILED"
        else:
            raise AssertionError("Invalid revision accepted")
        assert fixture_snapshot(fixture) == before
        assert migrate_initial(target, names, credential, ROOT) == VERSION
        context = multiprocessing.get_context("spawn")
        parent, remote = context.Pipe()
        process = context.Process(target=holder, args=(remote, names))
        process.start()
        remote.close()
        parent.send(credential)
        try:
            assert parent.poll(20) and parent.recv() == "LOCKED"
            started = time.monotonic()
            try:
                migrate_initial(target, names, credential, ROOT)
            except MigrationError as error:
                assert error.code == "MIGRATION_BUSY"
            else:
                raise AssertionError("Concurrent migration bypassed lock")
            assert 4 <= time.monotonic() - started <= 12
            parent.send("GO")
            assert parent.poll(20) and parent.recv() == "COMMITTED"
        finally:
            process.join(10)
            if process.is_alive():
                process.terminate()
                process.join(5)
            parent.close()
        assert process.exitcode == 0
        assert migrate_initial(target, names, credential, ROOT) == VERSION
        print(
            "PASS T006 calibration: TLS/migrator, real Alembic, "
            "reversible fixture and DDL rollback."
        )
        print("PASS T006 calibration: two processes; PostgreSQL lock timeout and retry.")
    finally:
        # Preserve the calibration DB/data; withdraw only this newly created login.
        if created:
            with target.connect("rag_control", bootstrap, autocommit=True) as connection:
                execute(connection, "ALTER ROLE {} NOLOGIN", names.role("migrator"))
                execute(connection, "ALTER DATABASE {} ALLOW_CONNECTIONS false", names.database)
            print(
                "Calibration fixture retained, access disabled; no tenant/control catalog touched."
            )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("T006 calibration failed; sensitive details suppressed.") from None
