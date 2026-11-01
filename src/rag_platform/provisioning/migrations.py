"""Tenant migrations: same-connection transaction lock, identity and verified version."""

import hashlib
from contextlib import contextmanager
from pathlib import Path
from threading import Lock

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.pool import NullPool

from rag_platform.providers.secrets import Credential
from rag_platform.provisioning.postgres import Names, Target

VERSION = "f01_tenant_0001"
_GATE = Lock()


class MigrationError(RuntimeError):
    CODES = {"MIGRATION_BUSY", "MIGRATION_FAILED", "IDENTITY_CONFLICT", "VERSION_MISMATCH"}

    def __init__(self, code="MIGRATION_FAILED"):
        self.code = code if code in self.CODES else "MIGRATION_FAILED"
        super().__init__(self.code)


def lock_key(tenant):
    return int.from_bytes(
        hashlib.sha256(("f01-tenant-migrate:" + str(tenant)).encode()).digest()[:8],
        "big",
        signed=True,
    )


@contextmanager
def migration_session(target: Target, names: Names, credential: Credential):
    if credential.username != names.role("migrator"):
        raise MigrationError("IDENTITY_CONFLICT")
    if not _GATE.acquire(timeout=5):
        raise MigrationError("MIGRATION_BUSY")
    engine = None
    try:
        engine = sa.create_engine(
            "postgresql+psycopg://",
            creator=lambda: target.connect(names.database, credential),
            poolclass=NullPool,
            hide_parameters=True,
        )
        with engine.begin() as connection:
            connection.execute(sa.text("SET LOCAL lock_timeout='5s'"))
            connection.execute(
                sa.text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key(names.tenant)}
            )
            row = connection.execute(
                sa.text(
                    "SELECT current_database(),current_user,pg_get_userbyid(datdba),"
                    "shobj_description(oid,'pg_database') FROM pg_database "
                    "WHERE datname=current_database()"
                )
            ).one()
            if tuple(row) != (
                names.database,
                names.role("migrator"),
                names.role("owner"),
                names.marker,
            ):
                raise MigrationError("IDENTITY_CONFLICT")
            owner = connection.dialect.identifier_preparer.quote(names.role("owner"))
            connection.exec_driver_sql("SET LOCAL ROLE " + owner)
            yield connection
    except MigrationError:
        raise
    except Exception as error:
        state = getattr(getattr(error, "orig", error), "sqlstate", None)
        raise MigrationError("MIGRATION_BUSY" if state == "55P03" else "MIGRATION_FAILED") from None
    finally:
        if engine is not None:
            engine.dispose()
        _GATE.release()


def apply_initial(connection, names: Names, repository: Path):
    present = connection.scalar(sa.text("SELECT to_regclass('public.ops_identity') IS NOT NULL"))
    if present:
        identity = connection.execute(sa.text("SELECT tenant_id FROM public.ops_identity")).all()
        if identity != [(names.tenant,)]:
            raise MigrationError("IDENTITY_CONFLICT")
    config = Config(str(repository / "alembic-tenant.ini"))
    config.attributes["connection"] = connection
    command.upgrade(config, VERSION)
    existing = connection.execute(sa.text("SELECT tenant_id FROM public.ops_identity")).all()
    if not existing:
        connection.execute(
            sa.text("INSERT INTO public.ops_identity(singleton, tenant_id) VALUES (1, :id)"),
            {"id": names.tenant},
        )
    elif existing != [(names.tenant,)]:
        raise MigrationError("IDENTITY_CONFLICT")
    for kind in ("app", "readonly"):
        role = connection.dialect.identifier_preparer.quote(names.role(kind))
        connection.exec_driver_sql(
            "REVOKE ALL ON public.ops_identity, public.alembic_version_tenant FROM " + role
        )
    versions = connection.execute(
        sa.text("SELECT version_num FROM public.alembic_version_tenant")
    ).all()
    if versions != [(VERSION,)]:
        raise MigrationError("VERSION_MISMATCH")
    return VERSION


def migrate_initial(target: Target, names: Names, credential: Credential, repository: Path):
    with migration_session(target, names, credential) as connection:
        return apply_initial(connection, names, repository)
