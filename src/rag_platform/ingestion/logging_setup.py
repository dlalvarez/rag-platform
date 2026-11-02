"""Trusted per-role privacy defaults; no global logging changes or new credentials."""

import sqlalchemy as sa
from psycopg import sql

from rag_platform.provisioning.migrations import MigrationError

SETTINGS = {
    "log_statement": "none",
    "log_min_duration_statement": "-1",
    "log_duration": "off",
    "log_min_error_statement": "panic",
    "log_error_verbosity": "terse",
    "log_parameter_max_length": "0",
    "log_parameter_max_length_on_error": "0",
}


def local_private_logging(connection):
    # QA/bootstrap session only; called before any synthetic content probe.
    if connection.scalar(sa.text("SELECT current_setting('is_superuser')")) != "on":
        raise MigrationError("IDENTITY_CONFLICT")
    for setting, value in SETTINGS.items():
        connection.execute(
            sa.text("SELECT set_config(:name,:value,true)"), {"name": setting, "value": value}
        )


def apply_role_logging(connection, names):
    if connection.scalar(sa.text("SELECT current_setting('is_superuser')")) != "on":
        raise MigrationError("IDENTITY_CONFLICT")
    if connection.scalar(sa.text("SELECT current_database()")) != names.database:
        raise MigrationError("IDENTITY_CONFLICT")
    if connection.execute(sa.text("SELECT tenant_id FROM public.ops_identity")).all() != [
        (names.tenant,)
    ]:
        raise MigrationError("IDENTITY_CONFLICT")
    for kind in ("app", "readonly", "migrator"):
        role = names.role(kind)
        record = connection.execute(
            sa.text(
                "SELECT shobj_description(oid,'pg_authid'),rolsuper,rolcreatedb,rolcreaterole,"
                "rolreplication,rolbypassrls FROM pg_roles WHERE rolname=:name"
            ),
            {"name": role},
        ).first()
        if record is None or tuple(record) != (names.marker, False, False, False, False, False):
            raise MigrationError("IDENTITY_CONFLICT")
        # Identifiers derive only from Names(UUID), settings/values are fixed above.
        cursor = connection.connection.driver_connection.cursor()
        try:
            for setting, value in SETTINGS.items():
                cursor.execute(
                    sql.SQL("ALTER ROLE {} SET {} = {}").format(
                        sql.Identifier(role), sql.Identifier(setting), sql.Literal(value)
                    )
                )
        finally:
            cursor.close()
        configuration = (
            connection.scalar(
                sa.text("SELECT rolconfig FROM pg_roles WHERE rolname=:name"), {"name": role}
            )
            or []
        )
        actual = dict(value.split("=", 1) for value in configuration)
        if any(actual.get(key) != value for key, value in SETTINGS.items()):
            raise MigrationError("VERSION_MISMATCH")
