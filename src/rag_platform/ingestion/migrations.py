"""Trusted, explicitly targeted F04 migration; no runtime/admin fallback."""

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from rag_platform.ingestion.guards_f04_0003 import FUNCTIONS, TRIGGERS
from rag_platform.ingestion.schema import VERSION, metadata
from rag_platform.provisioning.migrations import MigrationError, migration_session

PREVIOUS = "f03_tenant_0002"


def apply_ingestion(connection, names, repository):
    expected_owner = names.role("owner")
    if connection.scalar(sa.text("SELECT current_user")) != expected_owner:
        raise MigrationError("IDENTITY_CONFLICT")
    if connection.scalar(sa.text("SELECT current_database()")) != names.database:
        raise MigrationError("IDENTITY_CONFLICT")
    if connection.execute(sa.text("SELECT tenant_id FROM public.ops_identity")).all() != [
        (names.tenant,)
    ]:
        raise MigrationError("IDENTITY_CONFLICT")
    before = connection.execute(
        sa.text("SELECT version_num FROM public.alembic_version_tenant")
    ).all()
    if before not in ([(PREVIOUS,)], [(VERSION,)]):
        raise MigrationError("VERSION_MISMATCH")
    config = Config(str(repository / "alembic-tenant.ini"))
    config.attributes["connection"] = connection
    command.upgrade(config, VERSION)
    if (
        connection.scalar(sa.text("SELECT version_num FROM public.alembic_version_tenant"))
        != VERSION
    ):
        raise MigrationError("VERSION_MISMATCH")
    for table in metadata.sorted_tables:
        if not connection.scalar(
            sa.text("SELECT to_regclass(:name) IS NOT NULL"), {"name": table.fullname}
        ):
            raise MigrationError("VERSION_MISMATCH")
    for name, ddl in FUNCTIONS:
        row = connection.execute(
            sa.text(
                "SELECT p.prosrc,pg_get_userbyid(p.proowner),p.prosecdef,p.proconfig "
                "FROM pg_proc p "
                "JOIN pg_namespace n ON n.oid=p.pronamespace "
                "WHERE n.nspname='ops' AND p.proname=:name AND p.pronargs=0"
            ),
            {"name": name},
        ).first()
        if row is None or tuple(row) != (
            ddl.split("$f04$")[1],
            expected_owner,
            False,
            ["search_path=pg_catalog"],
        ):
            raise MigrationError("VERSION_MISMATCH")
    for table in metadata.sorted_tables:
        existing = set(
            connection.scalars(
                sa.text("SELECT conname FROM pg_constraint WHERE conrelid=to_regclass(:name)"),
                {"name": table.fullname},
            )
        )
        required = {item.name for item in table.constraints if item.name is not None}
        if not required <= existing:
            raise MigrationError("VERSION_MISMATCH")
        for index in table.indexes:
            if not connection.scalar(
                sa.text("SELECT to_regclass(:name) IS NOT NULL"),
                {"name": table.schema + "." + index.name},
            ):
                raise MigrationError("VERSION_MISMATCH")
    expected_triggers = [
        (name, table, function, 31 if "UPDATE" in events else 7, False, False)
        for name, table, events, function in TRIGGERS
    ] + [
        ("f04_ready_audit", "knowledge.document_versions", "f04_ready_audit_guard", 17, True, True)
    ]
    for name, table, function, kind, deferred, initially in expected_triggers:
        found = connection.execute(
            sa.text(
                "SELECT p.proname,t.tgtype,t.tgdeferrable,t.tginitdeferred,t.tgenabled "
                "FROM pg_trigger t JOIN pg_proc p ON p.oid=t.tgfoid "
                "WHERE t.tgrelid=to_regclass(:table) AND t.tgname=:name AND NOT t.tgisinternal"
            ),
            {"table": table, "name": name},
        ).first()
        if found is None or tuple(found) != (function, kind, deferred, initially, "O"):
            raise MigrationError("VERSION_MISMATCH")
    quote = connection.dialect.identifier_preparer.quote
    app, readonly = (quote(names.role(k)) for k in ("app", "readonly"))
    for schema in ("knowledge", "security", "ops"):
        connection.exec_driver_sql(
            "REVOKE ALL ON ALL TABLES IN SCHEMA "
            + schema
            + " FROM PUBLIC, "
            + app
            + ", "
            + readonly
        )
        connection.exec_driver_sql(
            "REVOKE ALL ON SCHEMA " + schema + " FROM PUBLIC, " + app + ", " + readonly
        )
        connection.exec_driver_sql("GRANT USAGE ON SCHEMA " + schema + " TO " + app)
    for schema in ("knowledge", "security"):
        connection.exec_driver_sql("GRANT USAGE ON SCHEMA " + schema + " TO " + readonly)
        connection.exec_driver_sql(
            "GRANT SELECT ON ALL TABLES IN SCHEMA " + schema + " TO " + readonly
        )
    for table in ("knowledge.repositories", "ops.document_receipts"):
        connection.exec_driver_sql("GRANT SELECT, INSERT, UPDATE ON " + table + " TO " + app)
    connection.exec_driver_sql("GRANT SELECT, INSERT ON knowledge.documents TO " + app)
    connection.exec_driver_sql(
        "GRANT UPDATE(state,tombstoned_at,tombstoned_by) ON knowledge.documents TO " + app
    )
    for table in (
        "knowledge.sources",
        "knowledge.document_versions",
        "knowledge.extracted_blocks",
        "knowledge.chunks",
        "ops.audit_events",
        "ops.ingestion_intents",
    ):
        connection.exec_driver_sql("GRANT SELECT, INSERT ON " + table + " TO " + app)
    connection.exec_driver_sql(
        "GRANT UPDATE(state,normalized_hash,character_count,page_count,block_count,chunk_count,"
        "completed_at,error_code) ON knowledge.document_versions TO " + app
    )
    connection.exec_driver_sql(
        "GRANT UPDATE(dispatch_state,job_id,dispatched_at,attempt,attempt_token,lease_until,"
        "updated_at) ON ops.ingestion_intents TO " + app
    )
    connection.exec_driver_sql(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON security.repository_acl TO " + app
    )
    for name, _ in FUNCTIONS:
        connection.exec_driver_sql("GRANT EXECUTE ON FUNCTION ops." + name + "() TO " + app)
    for role in (app, readonly):
        connection.exec_driver_sql(
            "REVOKE ALL ON public.ops_identity,public.alembic_version_tenant FROM " + role
        )
    return VERSION


def migrate_ingestion(target, names, credential, repository):
    with migration_session(target, names, credential) as connection:
        return apply_ingestion(connection, names, repository)


def migrate_ingestion_controlled(engine, tenant_id, actor, store, ca, repository):
    from rag_platform.provisioning.migration_control import migrate_controlled

    return migrate_controlled(
        engine,
        tenant_id,
        actor,
        store,
        ca,
        repository,
        runner=migrate_ingestion,
        profile="ingestion",
    )
