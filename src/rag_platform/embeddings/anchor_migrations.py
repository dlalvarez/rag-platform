"""Explicit anchor expansion only; unknown sources fail before DDL."""

from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from rag_platform.embeddings.migrations import _identity, _verify
from rag_platform.embeddings.original_anchor_f05_0005 import (
    ANCHOR_GUARD,
    PREVIOUS,
    VERSION,
    build_metadata,
)
from rag_platform.provisioning.migrations import MigrationError


def apply_original_anchor(connection, names, repository: Path):
    _identity(connection, names)
    head = connection.scalar(sa.text("SELECT version_num FROM public.alembic_version_tenant"))
    if head not in (PREVIOUS, VERSION):
        raise MigrationError("VERSION_MISMATCH")
    with connection.begin_nested():
        config = Config(str(repository / "alembic-tenant.ini"))
        config.attributes["connection"] = connection
        command.upgrade(config, VERSION)
        if (
            connection.scalar(sa.text("SELECT version_num FROM public.alembic_version_tenant"))
            != VERSION
        ):
            raise MigrationError("VERSION_MISMATCH")
        _verify(connection, names)
        found = {
            v["name"]: v
            for v in sa.inspect(connection).get_columns("documents", schema="knowledge")
        }
        for name in ("original_version_id", "original_version_kind"):
            column = build_metadata().tables["knowledge.documents"].c[name]
            if (
                name not in found
                or found[name]["nullable"]
                or found[name]["type"].compile(dialect=connection.dialect)
                != column.type.compile(dialect=connection.dialect)
            ):
                raise MigrationError("VERSION_MISMATCH")
        constraints = set(
            connection.scalars(
                sa.text(
                    "SELECT conname FROM pg_constraint "
                    "WHERE conrelid='knowledge.documents'::regclass"
                )
            )
        )
        if not {"f05_original_anchor", "f05_original_anchor_kind"} <= constraints:
            raise MigrationError("VERSION_MISMATCH")
        function = connection.execute(
            sa.text(
                "SELECT p.prosrc,pg_get_userbyid(p.proowner),p.prosecdef,p.proconfig "
                "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                "WHERE n.nspname='ops' AND p.proname='f05_original_anchor_guard' AND p.pronargs=0"
            )
        ).one_or_none()
        if function is None or tuple(function) != (
            ANCHOR_GUARD.split("$f05$")[1],
            names.role("owner"),
            False,
            ["search_path=pg_catalog"],
        ):
            raise MigrationError("VERSION_MISMATCH")
        trigger = connection.execute(
            sa.text(
                "SELECT t.tgtype,t.tgenabled,"
                "t.tgfoid='ops.f05_original_anchor_guard()'::regprocedure "
                "FROM pg_trigger t WHERE t.tgrelid='knowledge.documents'::regclass "
                "AND t.tgname='f05_original_anchor' AND NOT t.tgisinternal"
            )
        ).one_or_none()
        if trigger is None or tuple(trigger) != (23, "O", True):
            raise MigrationError("VERSION_MISMATCH")
    return VERSION
