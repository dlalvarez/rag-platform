"""Frozen metadata compatibility and local FK identities, no DB adoption."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from rag_platform.assistants.schema_f07_0007 import PREVIOUS, TABLES, VERSION, build_metadata
from rag_platform.embeddings.publication_schema_f05_0006 import build_metadata as previous


def ddl(table):
    return str(CreateTable(table).compile(dialect=postgresql.dialect()))


def test_assistant_schema_is_additive_and_does_not_change_existing_ddl():
    old, new = previous(), build_metadata()
    assert set(new.tables) - set(old.tables) == set(TABLES)
    assert all(ddl(table) == ddl(new.tables[name]) for name, table in old.tables.items())
    assert PREVIOUS == "f05_tenant_0006"
    assert VERSION == "f07_tenant_0007"


def test_all_foreign_keys_resolve_inside_the_tenant_metadata():
    metadata = build_metadata()
    for name in TABLES:
        table = metadata.tables[name]
        for fk in table.foreign_key_constraints:
            assert fk.ondelete == "RESTRICT"
            for element in fk.elements:
                assert element.column.table.metadata is metadata
                assert element.column.table.schema in {"assistant", "knowledge"}
    # Global ownership stays a logical UUID, never a FK into rag_control.
    assert not metadata.tables["assistant.assistants"].c.owner_id.foreign_keys
    assert not metadata.tables["assistant.audit_events"].c.principal_id.foreign_keys


def test_assistant_bounds_are_enforced_in_frozen_postgres_ddl():
    table = build_metadata().tables["assistant.assistants"]
    sql = ddl(table)
    for name in (
        "f07_assistant_name",
        "f07_assistant_purpose",
        "f07_assistant_profile",
        "f07_assistant_top_k",
        "f07_assistant_revision",
        "f07_assistant_state",
        "f07_assistant_timestamps",
        "f07_assistant_space_identity",
    ):
        assert name in sql
    assert "ON DELETE RESTRICT" in sql
    assert isinstance(table.c.revision.type, sa.BigInteger)
    assert not table.c.owner_id.nullable


def test_audit_and_link_tables_have_no_document_prompt_or_secret_payload():
    metadata = build_metadata()
    assert set(metadata.tables["assistant.repository_links"].c.keys()) == {
        "assistant_id",
        "repository_id",
    }
    assert set(metadata.tables["assistant.audit_events"].c.keys()) == {
        "id",
        "assistant_id",
        "principal_id",
        "request_id",
        "action",
        "created_at",
    }
    assert len(metadata.tables["assistant.repository_links"].primary_key.columns) == 2


def test_metadata_instances_do_not_share_mutable_tables():
    first, second = build_metadata(), build_metadata()
    assert first is not second
    assert first.tables["assistant.assistants"] is not second.tables["assistant.assistants"]
    first.tables["assistant.assistants"].c.name.info["canary"] = True
    assert not second.tables["assistant.assistants"].c.name.info
