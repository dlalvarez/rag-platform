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

from rag_platform.control.identity_models import IdentityBase
from rag_platform.control.migrations import upgrade_control
from rag_platform.control.models import Base
from rag_platform.providers.secrets import Credential
from rag_platform.provisioning.postgres import (
    PROVISIONER,
    Names,
    Target,
    create_role,
    execute,
    grant_owner_memberships,
)

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
        version = connection.scalar(sa.text("SELECT version_num FROM alembic_version_control"))
        assert version in {"f01_control_0004", "f02_control_0005"}
        expected = set(Base.metadata.tables) | {"alembic_version_control"}
        if version == "f02_control_0005":
            expected |= set(IdentityBase.metadata.tables)
        assert set(sa.inspect(connection).get_table_names()) == expected
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
        # SQLite does not enforce VARCHAR lengths: prove a VALID location on PostgreSQL.
        with connection.begin_nested() as reservation:
            tenant_id, instance_id = uuid.uuid4(), uuid.uuid4()
            connection.execute(
                tenants.insert().values(id=tenant_id, desired_version="f01_tenant_0001")
            )
            connection.execute(
                instances.insert().values(
                    id=instance_id,
                    host="reserved-" + instance_id.hex,
                    port=5432,
                    admin_secret_ref=uuid.uuid4(),
                    admin_secret_version=1,
                )
            )
            locations = Base.metadata.tables["db_locations"]
            connection.execute(
                locations.insert().values(
                    tenant_id=tenant_id,
                    instance_id=instance_id,
                    db_name="rag_t_" + tenant_id.hex,
                    app_secret_ref=uuid.uuid4(),
                    app_secret_version=1,
                    migrator_secret_ref=uuid.uuid4(),
                    migrator_secret_version=1,
                    readonly_secret_ref=uuid.uuid4(),
                    readonly_secret_version=1,
                    ssl_mode="verify-full",
                )
            )
            assert (
                connection.scalar(
                    sa.select(locations.c.ssl_mode).where(locations.c.tenant_id == tenant_id)
                )
                == "verify-full"
            )
            reservation.rollback()
        print("PASS: reserva válida con verify-full insertada y revertida en PostgreSQL.")
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
    # When T002 bootstrap exists, prove non-superuser owner grants using only
    # NOLOGIN fixtures and rollback. No OpenBao credentials or persistent roles.
    target = Target("postgres", 5432, Path("/run/f01-ca.crt"))
    with target.connect(
        "rag_control", Credential("f01_bootstrap", admin), autocommit=True
    ) as connection:
        if connection.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (PROVISIONER,)).fetchone():
            execute(connection, "SET SESSION AUTHORIZATION {}", PROVISIONER)
            with connection.transaction(force_rollback=True):
                names = Names(uuid.uuid4())
                create_role(connection, names.role("owner"), names.marker)
                create_role(connection, names.role("migrator"), names.marker)
                grant_owner_memberships(connection, names)
            print(
                "PASS: concesiones owner sin ciclo ADMIN; SET permitido y sin herencia; rollback."
            )
    engine.dispose()
    print("PASS V01 parcial: PostgreSQL/TLS, migrador limitado, constraints y Alembic repetible.")
    print("No tenants/roles tenant creados. AC-F01-01/06 siguen pendientes.")


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    try:
        run()
    except Exception:
        raise SystemExit("Control probe failed; sensitive exception details suppressed.") from None
