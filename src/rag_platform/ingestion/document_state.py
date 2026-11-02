"""Authorized logical document deletion; retain objects, versions and all chunks."""

import sqlalchemy as sa

from rag_platform.documents.errors import DocumentError
from rag_platform.documents.repositories import logical_id
from rag_platform.ingestion.schema import documents


class DocumentStateService:
    def __init__(self, repositories):
        if repositories.authority.profile != "ingestion":
            raise ValueError("Ingestion authority required")
        self.repositories = repositories

    def delete(self, context, trace, document):
        document = logical_id(document)

        def operation(c, checked):
            repo = c.scalar(sa.select(documents.c.repository_id).where(documents.c.id == document))
            if repo is None:
                raise DocumentError("NOT_FOUND")
            self.repositories._row(c, checked, repo, "delete", lock=True)
            row = c.execute(
                sa.select(documents)
                .where(documents.c.id == document, documents.c.repository_id == repo)
                .with_for_update()
            ).one_or_none()
            if row is None:
                raise DocumentError("NOT_FOUND")
            if row.state != "TOMBSTONED":
                c.execute(
                    sa.update(documents)
                    .where(documents.c.id == document)
                    .values(
                        state="TOMBSTONED",
                        tombstoned_at=sa.func.clock_timestamp(),
                        tombstoned_by=checked.principal_id,
                    )
                )
                self.repositories.event(c, checked, trace, repo, document, "DOCUMENT_TOMBSTONED")
            return {"document_id": str(document), "state": "TOMBSTONED"}

        return self.repositories._run(context, trace, "delete", operation)
