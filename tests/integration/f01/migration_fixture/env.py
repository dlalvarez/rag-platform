"""Synthetic validation track, separate version table."""

from alembic import context

connection = context.config.attributes["connection"]
context.configure(
    connection=connection, version_table="alembic_version_fixture", version_table_schema="public"
)
with context.begin_transaction():
    context.run_migrations()
