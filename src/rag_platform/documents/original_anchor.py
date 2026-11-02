"""Explicit schema profile chooses an original anchor; never probe/fallback by head."""

import sqlalchemy as sa

from rag_platform.documents.schema import documents
from rag_platform.tenancy.profiles import version_for


def pointer(profile):
    version_for(profile)
    if profile == "embedding_publication":
        return sa.literal_column("knowledge.documents.original_version_id", type_=sa.Uuid())
    return documents.c.current_version_id


def identity(connection, document, profile):
    version_for(profile)
    if profile != "embedding_publication":
        return document.current_version_id
    return connection.scalar(
        sa.select(pointer(profile))
        .select_from(documents)
        .where(
            documents.c.id == document.id,
            documents.c.repository_id == document.repository_id,
        )
    )
