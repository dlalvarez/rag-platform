"""Connection supplied in memory; never read a DSN from ini, env or command arguments."""

from alembic import context

from rag_platform.control.identity_models import IdentityBase
from rag_platform.control.models import Base
from rag_platform.ingestion.queue_schema import metadata as ingestion_metadata

connection = context.config.attributes.get("connection")
if connection is None:
    raise RuntimeError("Control migrations require an explicit trusted connection")
context.configure(
    connection=connection,
    target_metadata=[Base.metadata, IdentityBase.metadata, ingestion_metadata],
    compare_type=True,
    version_table="alembic_version_control",
)
with context.begin_transaction():
    context.run_migrations()
