"""Explicit phase migration targets; F01 callers never implicitly initiate F02."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.engine import Connection

F01_CONTROL = "f01_control_0004"
F02_CONTROL = "f02_control_0005"


def _upgrade(connection: Connection, repository: Path, target: str) -> None:
    config = Config(str(repository / "alembic-control.ini"))
    config.attributes["connection"] = connection
    current = MigrationContext.configure(
        connection, opts={"version_table": "alembic_version_control"}
    ).get_current_revision()
    if current is not None:
        # A compatible later phase is already installed: never downgrade it.
        scripts = ScriptDirectory.from_config(config)
        ancestors = {item.revision for item in scripts.walk_revisions(base="base", head=current)}
        if target in ancestors:
            return
    command.upgrade(config, target)


def upgrade_control(connection: Connection, repository: Path) -> None:
    _upgrade(connection, repository, F01_CONTROL)


def upgrade_identity(connection: Connection, repository: Path) -> None:
    _upgrade(connection, repository, F02_CONTROL)
