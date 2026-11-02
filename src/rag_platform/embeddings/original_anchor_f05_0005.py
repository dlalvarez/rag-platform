"""Immutable original anchor, before publication can move the current pointer."""

import sqlalchemy as sa

from rag_platform.embeddings.space_ddl import build_metadata as previous

VERSION = "f05_tenant_0005"
PREVIOUS = "f05_tenant_0004"

ANCHOR_GUARD = """
CREATE FUNCTION ops.f05_original_anchor_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $f05$
BEGIN
    IF TG_OP='INSERT' AND NEW.original_version_id IS NULL THEN
        NEW.original_version_id := NEW.current_version_id;
    END IF;
    IF NEW.original_version_id IS NULL OR
       (TG_OP='UPDATE' AND NEW.original_version_id IS DISTINCT FROM OLD.original_version_id)
       OR (TG_OP='INSERT' AND NEW.original_version_id IS DISTINCT FROM NEW.current_version_id)
       OR NEW.original_version_kind IS DISTINCT FROM 'ORIGINAL' THEN
        RAISE EXCEPTION 'immutable original anchor' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END
$f05$
"""


def build_metadata():
    metadata = previous()
    documents = metadata.tables["knowledge.documents"]
    documents.append_column(sa.Column("original_version_id", sa.Uuid(), nullable=False))
    documents.append_column(
        sa.Column("original_version_kind", sa.String(16), nullable=False, server_default="ORIGINAL")
    )
    documents.append_constraint(
        sa.CheckConstraint("original_version_kind='ORIGINAL'", name="f05_original_anchor_kind")
    )
    documents.append_constraint(
        sa.ForeignKeyConstraint(
            ["original_version_id", "id", "repository_id", "original_version_kind"],
            [
                "knowledge.document_versions." + c
                for c in ("id", "document_id", "repository_id", "kind")
            ],
            name="f05_original_anchor",
            deferrable=True,
            initially="DEFERRED",
            use_alter=True,
        )
    )
    return metadata
