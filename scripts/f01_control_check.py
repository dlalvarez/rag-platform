"""Real PostgreSQL/TLS control migration probe; never prints SQL/DSN/credential errors."""

import logging
import secrets
import uuid
from pathlib import Path

import psycopg
import sqlalchemy as sa
from psycopg import sql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import NullPool

from rag_platform.control.migrations import upgrade_control
from rag_platform.control.models import Base

REPOSITORY = Path(__file__).resolve().parents[1]


def run() -> None:
    params = dict(
        host="postgres",
        port=5432,
        dbname="rag_control",
        sslmode="verify-full",
        sslrootcert="/run/f01-ca.crt",
    )
    admin = Path("/run/secrets/postgres_password").read_text()
    migrator = Path("/run/secrets/control_migrator_password").read_text()
    with psycopg.connect(**params, user="f01_bootstrap", password=admin) as connection:
        with connection.cursor() as cur:
            if not cur.execute(
                "SELECT 1 FROM pg_roles WHERE rolname = %s", ("f01_control_migrator",)
            ).fetchone():
                cur.execute(
                    sql.SQL(
                        "CREATE ROLE f01_control_migrator LOGIN NOSUPERUSER "
                        "NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}"
                    ).format(sql.Literal(migrator))
                )
            cur.execute("REVOKE CONNECT ON DATABASE rag_control FROM PUBLIC")
            cur.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
            cur.execute("GRANT CONNECT ON DATABASE rag_control TO f01_control_migrator")
            cur.execute("GRANT USAGE, CREATE ON SCHEMA public TO f01_control_migrator")
    url = sa.URL.create(
        "postgresql+psycopg",
        username="f01_control_migrator",
        password=migrator,
        host="postgres",
        database="rag_control",
        query={"sslmode": "verify-full", "sslrootcert": "/run/f01-ca.crt"},
    )
    engine = sa.create_engine(url, poolclass=NullPool, hide_parameters=True)
    with engine.begin() as connection:
        assert connection.scalar(sa.text("SELECT current_database()")) == "rag_control"
        assert connection.scalar(sa.text("SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()"))
        assert not connection.scalar(
            sa.text(
                "SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolbypassrls "
                "FROM pg_roles WHERE rolname=current_user"
            )
        )
        upgrade_control(connection, REPOSITORY)
    with engine.begin() as connection:
        upgrade_control(connection, REPOSITORY)
        assert (
            connection.scalar(sa.text("SELECT version_num FROM alembic_version_control"))
            == "f01_control_0001"
        )
        assert set(sa.inspect(connection).get_table_names()) == set(Base.metadata.tables) | {
            "alembic_version_control"
        }
        # Rejected records run in SAVEPOINTs, without persistent tenant provisioning.
        tenants = Base.metadata.tables["tenants"]
        for values in ({"state": "INVALID"}, {"migration_state": "INVALID"}):
            try:
                with connection.begin_nested():
                    connection.execute(
                        tenants.insert().values(
                            id=uuid.uuid4(), desired_version="f01_tenant_0001", **values
                        )
                    )
            except IntegrityError:
                pass
            else:
                raise AssertionError("Catalog accepted invalid enum values")
        instances = Base.metadata.tables["instances"]
        try:
            with connection.begin_nested():
                connection.execute(
                    instances.insert().values(
                        id=uuid.uuid4(),
                        host="synthetic",
                        port=0,
                        admin_secret_ref=uuid.uuid4(),
                        admin_secret_version=1,
                    )
                )
        except IntegrityError:
            pass
        else:
            raise AssertionError("Catalog accepted invalid port")
    # Wrong password and untrusted CA must fail rather than fall back to a local socket.
    for changed in (
        {"password": secrets.token_urlsafe(32)},
        {"sslrootcert": "/no-such-ca"},
        {"sslmode": "disable"},
    ):
        try:
            with psycopg.connect(
                **(params | {"user": "f01_control_migrator", "password": migrator} | changed)
            ):
                pass
        except psycopg.OperationalError:
            pass
        else:
            raise AssertionError("PostgreSQL accepted an invalid credential or CA")
    engine.dispose()
    print("PASS V01 parcial: PostgreSQL/TLS, migrador limitado, constraints y Alembic repetible.")
    print("No tenants/roles tenant creados. AC-F01-01/06 siguen pendientes.")


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    try:
        run()
    except Exception:
        raise SystemExit("Control probe failed; sensitive exception details suppressed.") from None
