"""Authorized current-document views and verified private download spools, no journal reads."""

import time

import sqlalchemy as sa

from rag_platform.control.identity import AccessError
from rag_platform.documents.errors import DocumentError
from rag_platform.documents.repositories import logical_id
from rag_platform.documents.schema import document_versions, documents, sources
from rag_platform.documents.storage import Original
from rag_platform.documents.validation import UploadSpool


def selection():
    return (
        sa.select(
            documents.c.id,
            documents.c.repository_id,
            documents.c.source_id,
            document_versions.c.id.label("version_id"),
            document_versions.c.filename,
            document_versions.c.mime,
            document_versions.c.byte_size,
            document_versions.c.content_hash,
            document_versions.c.blob_key,
            document_versions.c.created_at,
        )
        .select_from(documents)
        .join(
            document_versions,
            sa.and_(
                document_versions.c.id == documents.c.current_version_id,
                document_versions.c.document_id == documents.c.id,
                document_versions.c.repository_id == documents.c.repository_id,
            ),
        )
        .join(
            sources,
            sa.and_(
                sources.c.id == documents.c.source_id,
                sources.c.repository_id == documents.c.repository_id,
            ),
        )
        .where(
            documents.c.state == "RECEIVED",
            document_versions.c.state == "RECEIVED",
            sources.c.provider == "UPLOAD",
        )
    )


def view(row):
    from datetime import UTC

    return {
        "document_id": str(row.id),
        "repository_id": str(row.repository_id),
        "source_id": str(row.source_id),
        "version_id": str(row.version_id),
        "filename": row.filename,
        "mime": row.mime,
        "byte_size": row.byte_size,
        "sha256": row.content_hash,
        "state": "RECEIVED",
        "created_at": row.created_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
    }


class Download:
    def __init__(self, spool, file):
        self.spool, self.file = spool, file

    def __repr__(self):
        return "Download(<private>)"

    def chunks(self):
        self.file.file.seek(0)
        while piece := self.file.file.read(65536):
            yield piece

    def close(self):
        self.spool.close()


class DocumentService:
    def __init__(self, repositories, gateway):
        self.repositories, self.gateway = repositories, gateway

    def list(self, context, trace, repo, *, limit=50, cursor=None):
        repo = logical_id(repo)
        purpose = "documents:" + str(repo)
        last = self.repositories.pagination.decode(context, purpose, cursor, limit)

        def operation(c, checked):
            self.repositories._row(c, checked, repo, "read")
            query = (
                selection()
                .where(documents.c.repository_id == repo)
                .order_by(documents.c.id)
                .limit(limit + 1)
            )
            if last is not None:
                query = query.where(documents.c.id > last)
            return self.repositories.pagination.page(
                checked,
                purpose,
                c.execute(query).all(),
                limit,
                key=lambda row: row.id,
                serialize=view,
            )

        return self.repositories._run(context, trace, "read", operation)

    def _row(self, context, trace, repo, document):
        repo, document = logical_id(repo), logical_id(document)

        def operation(c, checked):
            self.repositories._row(c, checked, repo, "read")
            row = c.execute(
                selection().where(documents.c.id == document, documents.c.repository_id == repo)
            ).one_or_none()
            if row is None:
                raise DocumentError("NOT_FOUND")
            return row

        return self.repositories._run(context, trace, "read", operation)

    def show(self, context, trace, repo, document):
        return view(self._row(context, trace, repo, document))

    def original(self, context, trace, repo, document):
        row = self._row(context, trace, repo, document)
        manifest = Original(repo, row.version_id, row.content_hash, row.byte_size, row.mime)
        if row.blob_key != manifest.key:
            raise DocumentError()
        spool = None
        deadline = time.monotonic() + 20
        try:
            spool = UploadSpool(row.filename, row.mime, max_bytes=row.byte_size)
            with self.gateway.download(context, trace, manifest) as response:
                while True:
                    if time.monotonic() >= deadline:
                        raise DocumentError()
                    piece = response.read(65536)
                    if not piece:
                        break
                    spool.accept(piece)
            file = spool.finish()
            if (
                file.byte_size != row.byte_size
                or file.content_hash != row.content_hash
                or time.monotonic() >= deadline
            ):
                raise DocumentError()
            # Check membership/ACL again after remote I/O, before releasing any bytes.
            self.repositories.require(context, trace, repo, "read")
            return Download(spool, file)
        except BaseException as error:
            if spool is not None:
                spool.close()
            if isinstance(error, AccessError) or (
                isinstance(error, DocumentError) and error.code in {"ROLE_DENIED", "NOT_FOUND"}
            ):
                raise
            if isinstance(error, Exception):
                raise DocumentError() from None
            raise
