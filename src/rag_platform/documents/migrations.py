"""Administrative F03 migration: tenant identity and same-connection lock are mandatory."""

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from rag_platform.documents.schema import VERSION, metadata
from rag_platform.provisioning.migrations import VERSION as BASELINE
from rag_platform.provisioning.migrations import MigrationError, migration_session


def apply_documents(connection, names, repository):
    identity = connection.execute(sa.text("SELECT tenant_id FROM public.ops_identity")).all()
    versions = connection.execute(
        sa.text("SELECT version_num FROM public.alembic_version_tenant")
    ).all()
    if identity != [(names.tenant,)]:
        raise MigrationError("IDENTITY_CONFLICT")
    if versions not in ([(BASELINE,)], [(VERSION,)]):
        raise MigrationError("VERSION_MISMATCH")
    config = Config(str(repository / "alembic-tenant.ini"))
    config.attributes["connection"] = connection
    command.upgrade(config, VERSION)
    if connection.execute(
        sa.text("SELECT version_num FROM public.alembic_version_tenant")
    ).all() != [(VERSION,)]:
        raise MigrationError("VERSION_MISMATCH")
    for table in metadata.sorted_tables:
        if not connection.scalar(
            sa.text("SELECT to_regclass(:name) IS NOT NULL"), {"name": table.fullname}
        ):
            raise MigrationError("VERSION_MISMATCH")
    quote = connection.dialect.identifier_preparer.quote
    app, readonly = (quote(names.role(role)) for role in ("app", "readonly"))
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
    for table in ("knowledge.repositories", "knowledge.documents", "ops.document_receipts"):
        connection.exec_driver_sql("GRANT SELECT, INSERT, UPDATE ON " + table + " TO " + app)
    for table in ("knowledge.sources", "knowledge.document_versions", "ops.audit_events"):
        connection.exec_driver_sql("GRANT SELECT, INSERT ON " + table + " TO " + app)
    connection.exec_driver_sql(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON security.repository_acl TO " + app
    )
    for role in (app, readonly):
        connection.exec_driver_sql(
            "REVOKE ALL ON public.ops_identity, public.alembic_version_tenant FROM " + role
        )
    return VERSION


def migrate_documents(target, names, credential, repository):
    with migration_session(target, names, credential) as connection:
        return apply_documents(connection, names, repository)


def migrate_documents_controlled(engine, tenant_id, actor, store, ca, repository):
    from rag_platform.provisioning.migration_control import migrate_controlled

    return migrate_controlled(
        engine,
        tenant_id,
        actor,
        store,
        ca,
        repository,
        runner=migrate_documents,
        profile="documents",
    )
