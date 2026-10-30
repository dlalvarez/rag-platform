"""Run only control migrations with an already authenticated, explicit connection."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Connection


def upgrade_control(connection: Connection, repository: Path) -> None:
    config = Config(str(repository / "alembic-control.ini"))
    config.attributes["connection"] = connection
    command.upgrade(config, "head")
