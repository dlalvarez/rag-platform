"""F03 repositories, explicit ACL and durable private receipt, tenant-local only."""

from alembic import op

from rag_platform.documents.schema_f03_0002 import build_metadata

revision = "f03_tenant_0002"
down_revision = "f01_tenant_0001"
branch_labels = None
depends_on = None


def upgrade():
    for schema in ("knowledge", "security", "ops"):
        op.execute("CREATE SCHEMA " + schema)
        op.execute("REVOKE ALL ON SCHEMA " + schema + " FROM PUBLIC")
    build_metadata().create_all(op.get_bind(), checkfirst=False)


def downgrade():
    raise RuntimeError("Destructive document downgrade requires separate approval")
