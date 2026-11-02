"""Explicit additive F05 space foundation; no publication or runtime fallback."""

from dataclasses import asdict
from uuid import UUID

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from rag_platform.embeddings.contracts import EmbeddingProfile
from rag_platform.embeddings.space_ddl import build_metadata, vector_table
from rag_platform.ingestion.guards_f04_0003 import FUNCTIONS
from rag_platform.provisioning.migrations import MigrationError, migration_session

VERSION = "f05_tenant_0004"
PREVIOUS = "f04_tenant_0003"
MAX_SPACES = 16


def _identity(connection, names):
    if connection.execute(sa.text("SELECT current_database(),current_user")).one() != (
        names.database,
        names.role("owner"),
    ):
        raise MigrationError("IDENTITY_CONFLICT")
    if connection.execute(sa.text("SELECT tenant_id FROM public.ops_identity")).all() != [
        (names.tenant,)
    ]:
        raise MigrationError("IDENTITY_CONFLICT")


def _verify(connection, names):
    metadata = build_metadata()
    for table in metadata.sorted_tables:
        row = connection.scalar(
            sa.text("SELECT to_regclass(:table) IS NOT NULL"), {"table": table.fullname}
        )
        if not row:
            raise MigrationError("VERSION_MISMATCH")
        constraints = set(
            connection.scalars(
                sa.text("SELECT conname FROM pg_constraint WHERE conrelid=to_regclass(:table)"),
                {"table": table.fullname},
            )
        )
        if not {item.name for item in table.constraints if item.name is not None} <= constraints:
            raise MigrationError("VERSION_MISMATCH")
    for name, ddl in FUNCTIONS:
        actual = connection.execute(
            sa.text(
                "SELECT p.prosrc,pg_get_userbyid(p.proowner),p.prosecdef,p.proconfig "
                "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                "WHERE n.nspname='ops' AND p.proname=:name AND p.pronargs=0"
            ),
            {"name": name},
        ).first()
        if actual is None or tuple(actual) != (
            ddl.split("$f04$")[1],
            names.role("owner"),
            False,
            ["search_path=pg_catalog"],
        ):
            raise MigrationError("VERSION_MISMATCH")


def _apply_spaces(connection, names, repository):
    _identity(connection, names)
    before = connection.scalar(sa.text("SELECT version_num FROM public.alembic_version_tenant"))
    if before not in (PREVIOUS, VERSION):
        raise MigrationError("VERSION_MISMATCH")
    if not connection.scalar(
        sa.text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='vector')")
    ):
        raise MigrationError("VERSION_MISMATCH")
    config = Config(str(repository / "alembic-tenant.ini"))
    config.attributes["connection"] = connection
    command.upgrade(config, VERSION)
    if (
        connection.scalar(sa.text("SELECT version_num FROM public.alembic_version_tenant"))
        != VERSION
    ):
        raise MigrationError("VERSION_MISMATCH")
    _verify(connection, names)
    quote = connection.dialect.identifier_preparer.quote
    for role in ("app", "readonly"):
        name = quote(names.role(role))
        connection.exec_driver_sql("REVOKE ALL ON knowledge.embedding_spaces FROM " + name)
        connection.exec_driver_sql("GRANT SELECT ON knowledge.embedding_spaces TO " + name)
    return VERSION


def _register_space(connection, names, space_id, profile, *, expected_version=VERSION):
    _identity(connection, names)
    if (
        not isinstance(space_id, UUID)
        or space_id.int == 0
        or not isinstance(profile, EmbeddingProfile)
    ):
        raise MigrationError("IDENTITY_CONFLICT")
    if expected_version not in (VERSION, "f05_tenant_0006") or (
        connection.scalar(sa.text("SELECT version_num FROM public.alembic_version_tenant"))
        != expected_version
    ):
        raise MigrationError("VERSION_MISMATCH")
    # Administrative per-tenant transaction lock serializes DDL/quota/idempotency.
    connection.execute(
        sa.text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
        {"key": "f05-spaces:" + str(names.tenant)},
    )
    metadata = build_metadata()
    try:
        table = vector_table(metadata, space_id, profile)
    except Exception:
        raise MigrationError("IDENTITY_CONFLICT") from None
    catalog = metadata.tables["knowledge.embedding_spaces"]
    values = asdict(profile) | {"id": space_id, "profile_fingerprint": profile.fingerprint()}
    existing = (
        connection.execute(
            sa.select(catalog).where(
                sa.or_(
                    catalog.c.id == space_id, catalog.c.profile_fingerprint == profile.fingerprint()
                )
            )
        )
        .mappings()
        .all()
    )
    if existing:
        if len(existing) != 1 or any(existing[0][key] != value for key, value in values.items()):
            raise MigrationError("IDENTITY_CONFLICT")
    else:
        if connection.scalar(sa.select(sa.func.count()).select_from(catalog)) >= MAX_SPACES:
            raise MigrationError("IDENTITY_CONFLICT")
        connection.execute(catalog.insert().values(**values))
    present = connection.scalar(
        sa.text("SELECT to_regclass(:table) IS NOT NULL"), {"table": table.fullname}
    )
    if not existing:
        if present:
            raise MigrationError("IDENTITY_CONFLICT")
        table.create(connection, checkfirst=False)
    elif not present:
        raise MigrationError("VERSION_MISMATCH")
    actual_type = connection.scalar(
        sa.text(
            "SELECT format_type(atttypid,atttypmod) FROM pg_attribute "
            "WHERE attrelid=to_regclass(:table) AND attname='embedding' AND NOT attisdropped"
        ),
        {"table": table.fullname},
    )
    if actual_type != f"vector({profile.dimension})":
        raise MigrationError("VERSION_MISMATCH")
    actual_constraints = set(
        connection.scalars(
            sa.text("SELECT conname FROM pg_constraint WHERE conrelid=to_regclass(:table)"),
            {"table": table.fullname},
        )
    )
    if not {item.name for item in table.constraints if item.name} <= actual_constraints:
        raise MigrationError("VERSION_MISMATCH")
    index = connection.scalar(
        sa.text("SELECT pg_get_indexdef(to_regclass(:index))"),
        {"index": "knowledge.hnsw_" + space_id.hex},
    )
    if not index or "USING hnsw (embedding vector_cosine_ops)" not in index:
        raise MigrationError("VERSION_MISMATCH")
    quote = connection.dialect.identifier_preparer.quote
    qualified = "knowledge." + quote(table.name)
    app, readonly = (quote(names.role(role)) for role in ("app", "readonly"))
    connection.exec_driver_sql(
        "REVOKE ALL ON " + qualified + " FROM PUBLIC," + app + "," + readonly
    )
    connection.exec_driver_sql("GRANT SELECT,INSERT ON " + qualified + " TO " + app)
    connection.exec_driver_sql("GRANT SELECT ON " + qualified + " TO " + readonly)
    return space_id


def apply_spaces(connection, names, repository):
    # A caller catching a verification error cannot commit partial DDL.
    with connection.begin_nested():
        return _apply_spaces(connection, names, repository)


def register_space(connection, names, space_id, profile):
    # Preserve the outer transaction while reverting a failed catalog/DDL attempt.
    with connection.begin_nested():
        return _register_space(connection, names, space_id, profile)


def migrate_spaces(target, names, credential, repository):
    with migration_session(target, names, credential) as connection:
        return apply_spaces(connection, names, repository)


def migrate_spaces_controlled(engine, tenant_id, actor, store, ca, repository):
    from rag_platform.provisioning.migration_control import migrate_controlled

    return migrate_controlled(
        engine,
        tenant_id,
        actor,
        store,
        ca,
        repository,
        runner=migrate_spaces,
        profile="embeddings",
    )
