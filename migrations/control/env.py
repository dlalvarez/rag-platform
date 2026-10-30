"""Connection supplied in memory; never read a DSN from ini, env or command arguments."""

from alembic import context

from rag_platform.control.models import Base

connection = context.config.attributes.get("connection")
if connection is None:
    raise RuntimeError("Control migrations require an explicit trusted connection")
context.configure(
    connection=connection,
    target_metadata=Base.metadata,
    compare_type=True,
    version_table="alembic_version_control",
)
with context.begin_transaction():
    context.run_migrations()
