"""Tenant migrations require an explicit connection with its own owner assumed."""

from alembic import context

connection = context.config.attributes.get("connection")
if connection is None:
    raise RuntimeError("Tenant migrations require an explicit trusted connection")
context.configure(
    connection=connection, version_table="alembic_version_tenant", version_table_schema="public"
)
with context.begin_transaction():
    context.run_migrations()
