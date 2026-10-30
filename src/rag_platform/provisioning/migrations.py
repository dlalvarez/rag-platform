"""Initial tenant contract only; coordinated locks/failure recovery belong to T006."""

from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.pool import NullPool

from rag_platform.providers.secrets import Credential
from rag_platform.provisioning.postgres import Names, SqlProvisioningError, Target


def migrate_initial(target: Target, names: Names, credential: Credential, repository: Path):
    if credential.username != names.role("migrator"):
        raise SqlProvisioningError()
    engine = sa.create_engine(
        "postgresql+psycopg://",
        creator=lambda: target.connect(names.database, credential),
        poolclass=NullPool,
        hide_parameters=True,
    )
    try:
        with engine.begin() as connection:
            owner = connection.dialect.identifier_preparer.quote(names.role("owner"))
            connection.exec_driver_sql("SET ROLE " + owner)
            config = Config(str(repository / "alembic-tenant.ini"))
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            existing = connection.execute(
                sa.text("SELECT tenant_id FROM public.ops_identity")
            ).all()
            if existing and (len(existing) != 1 or str(existing[0][0]) != str(names.tenant)):
                raise SqlProvisioningError()
            if not existing:
                connection.execute(
                    sa.text(
                        "INSERT INTO public.ops_identity(singleton, tenant_id) VALUES (1, :id)"
                    ),
                    {"id": names.tenant},
                )
            # Default grants for future app tables must not expose operational identity/version.
            for kind in ("app", "readonly"):
                role = connection.dialect.identifier_preparer.quote(names.role(kind))
                connection.exec_driver_sql(
                    "REVOKE ALL ON public.ops_identity, public.alembic_version_tenant FROM " + role
                )
    finally:
        engine.dispose()
