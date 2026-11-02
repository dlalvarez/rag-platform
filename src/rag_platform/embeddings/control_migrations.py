"""Known F05 control target only; never initialize or accept an unknown source."""

from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext

from rag_platform.control.migrations import _upgrade
from rag_platform.embeddings.queue_schema_f05_0007 import VERSION, jobs
from rag_platform.provisioning.migrations import MigrationError


def upgrade_embedding_queue(connection, repository: Path):
    if tuple(connection.execute(sa.text("SELECT current_database(),current_user")).one()) != (
        "rag_control",
        "f01_control_migrator",
    ):
        raise MigrationError("IDENTITY_CONFLICT")
    context = MigrationContext.configure(
        connection, opts={"version_table": "alembic_version_control"}
    )
    if context.get_current_revision() not in ("f04_control_0006", VERSION):
        raise MigrationError("VERSION_MISMATCH")
    with connection.begin_nested():
        _upgrade(connection, repository, VERSION)
        if context.get_current_revision() != VERSION:
            raise MigrationError("VERSION_MISMATCH")
        inspector = sa.inspect(connection)
        found = {
            item["name"]: item for item in inspector.get_columns("job_envelopes", schema="public")
        }
        if set(found) != set(jobs.c.keys()):
            raise MigrationError("VERSION_MISMATCH")
        for column in jobs.c:
            actual = found[column.name]
            if actual["nullable"] != column.nullable or actual["type"].compile(
                dialect=connection.dialect
            ) != column.type.compile(dialect=connection.dialect):
                raise MigrationError("VERSION_MISMATCH")
        constraints = set(
            connection.scalars(
                sa.text(
                    "SELECT conname FROM pg_constraint "
                    "WHERE conrelid='public.job_envelopes'::regclass"
                )
            )
        )
        if not {item.name for item in jobs.constraints if item.name} <= constraints:
            raise MigrationError("VERSION_MISMATCH")
        for index in jobs.indexes:
            if not connection.scalar(
                sa.text("SELECT to_regclass(:name) IS NOT NULL"), {"name": "public." + index.name}
            ):
                raise MigrationError("VERSION_MISMATCH")
    return VERSION
