"""Known F05 publication target, with explicit verification and limited grants."""

from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from rag_platform.embeddings.anchor_migrations import apply_original_anchor
from rag_platform.embeddings.migrations import _identity, _register_space, _verify
from rag_platform.embeddings.original_anchor_f05_0005 import ANCHOR_GUARD
from rag_platform.embeddings.publication_guards_f05_0006 import FUNCTIONS
from rag_platform.embeddings.publication_schema_f05_0006 import VERSION, build_metadata
from rag_platform.provisioning.migrations import MigrationError

TABLES = ("ops.embedding_intents", "ops.embedding_batches", "knowledge.embedding_publications")


def apply_publication(connection, names, repository: Path):
    _identity(connection, names)
    current = connection.scalar(sa.text("SELECT version_num FROM public.alembic_version_tenant"))
    if current not in ("f05_tenant_0004", "f05_tenant_0005", VERSION):
        raise MigrationError("VERSION_MISMATCH")
    with connection.begin_nested():
        if current != VERSION:
            apply_original_anchor(connection, names, repository)
        config = Config(str(repository / "alembic-tenant.ini"))
        config.attributes["connection"] = connection
        command.upgrade(config, VERSION)
        if (
            connection.scalar(sa.text("SELECT version_num FROM public.alembic_version_tenant"))
            != VERSION
        ):
            raise MigrationError("VERSION_MISMATCH")
        _verify(connection, names)
        metadata = build_metadata()
        inspector = sa.inspect(connection)
        for name in TABLES:
            table = metadata.tables[name]
            columns = {c["name"]: c for c in inspector.get_columns(table.name, schema=table.schema)}
            if set(columns) != set(table.c.keys()):
                raise MigrationError("VERSION_MISMATCH")
            for column in table.c:
                actual = columns[column.name]
                if actual["nullable"] != column.nullable or actual["type"].compile(
                    dialect=connection.dialect
                ) != column.type.compile(dialect=connection.dialect):
                    raise MigrationError("VERSION_MISMATCH")
            found = set(
                connection.scalars(
                    sa.text("SELECT conname FROM pg_constraint WHERE conrelid=to_regclass(:table)"),
                    {"table": name},
                )
            )
            if not {c.name for c in table.constraints if c.name} <= found:
                raise MigrationError("VERSION_MISMATCH")
        for name, ddl in (*FUNCTIONS, ("f05_original_anchor_guard", ANCHOR_GUARD)):
            actual = connection.execute(
                sa.text(
                    "SELECT p.prosrc,pg_get_userbyid(p.proowner),p.prosecdef,p.proconfig "
                    "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                    "WHERE n.nspname='ops' AND p.proname=:name AND p.pronargs=0"
                ),
                {"name": name},
            ).one_or_none()
            delimiter = "$f04$" if name == "f05_version_guard" else "$f05$"
            if actual is None or tuple(actual) != (
                ddl.split(delimiter)[1],
                names.role("owner"),
                False,
                ["search_path=pg_catalog"],
            ):
                raise MigrationError("VERSION_MISMATCH")
        for trigger, table, function, kind, deferred in (
            ("f05_original_anchor", "knowledge.documents", "f05_original_anchor_guard", 23, False),
            ("f04_block_guard", "knowledge.extracted_blocks", "f04_block_guard", 7, False),
            ("f04_chunk_guard", "knowledge.chunks", "f04_chunk_guard", 7, False),
            ("f04_ready_audit", "knowledge.document_versions", "f04_ready_audit_guard", 17, True),
            ("f05_version_guard", "knowledge.document_versions", "f05_version_guard", 31, False),
            (
                "f05_embedding_intent",
                "ops.embedding_intents",
                "f05_embedding_intent_guard",
                31,
                False,
            ),
            (
                "f05_embedding_batch",
                "ops.embedding_batches",
                "f05_embedding_batch_guard",
                31,
                False,
            ),
            (
                "f05_publication_complete",
                "knowledge.embedding_publications",
                "f05_embedding_publication_guard",
                29,
                True,
            ),
            (
                "f05_document_pointer",
                "knowledge.documents",
                "f05_published_pointer_guard",
                21,
                True,
            ),
            (
                "f05_version_publication",
                "knowledge.document_versions",
                "f05_published_pointer_guard",
                17,
                True,
            ),
        ):
            actual = connection.execute(
                sa.text(
                    "SELECT tgtype,tgenabled,tgfoid=to_regprocedure(:function),"
                    "tgdeferrable,tginitdeferred "
                    "FROM pg_trigger WHERE tgrelid=to_regclass(:table) "
                    "AND tgname=:trigger AND NOT tgisinternal"
                ),
                {"table": table, "trigger": trigger, "function": "ops." + function + "()"},
            ).one_or_none()
            if actual is None or tuple(actual) != (kind, "O", True, deferred, deferred):
                raise MigrationError("VERSION_MISMATCH")
        quote = connection.dialect.identifier_preparer.quote
        app, readonly = (quote(names.role(k)) for k in ("app", "readonly"))
        for table in TABLES:
            connection.exec_driver_sql(
                "REVOKE ALL ON " + table + " FROM PUBLIC," + app + "," + readonly
            )
            connection.exec_driver_sql("GRANT SELECT,INSERT ON " + table + " TO " + app)
            connection.exec_driver_sql("GRANT SELECT ON " + table + " TO " + readonly)
        connection.exec_driver_sql(
            "GRANT UPDATE(dispatch_state,job_id,dispatched_at,status,attempt,attempt_token,"
            "lease_until,error_code,updated_at) ON ops.embedding_intents TO " + app
        )
        connection.exec_driver_sql(
            "GRANT UPDATE(current_version_id,current_version_kind) ON knowledge.documents TO " + app
        )
        for name, _ in FUNCTIONS:
            connection.exec_driver_sql("GRANT EXECUTE ON FUNCTION ops." + name + "() TO " + app)
    return VERSION


def register_publication_space(connection, names, space_id, profile):
    """Same immutable DDL/profile rules, only on the exact publication head."""
    with connection.begin_nested():
        return _register_space(connection, names, space_id, profile, expected_version=VERSION)
