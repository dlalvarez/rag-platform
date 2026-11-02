"""Authorized F04 metadata views; control queries never carry document content."""

from datetime import UTC
from uuid import uuid5

import sqlalchemy as sa

from rag_platform.documents.errors import DocumentError
from rag_platform.documents.repositories import logical_id
from rag_platform.ingestion.queue_schema import jobs
from rag_platform.ingestion.schema import documents, versions

VERSION_FIELDS = (
    "document_id",
    "kind",
    "original_version_id",
    "state",
    "byte_size",
    "mime",
    "parser_id",
    "normalizer_id",
    "chunker_id",
    "config_hash",
    "chunk_size",
    "chunk_overlap",
    "normalized_hash",
    "character_count",
    "block_count",
    "chunk_count",
    "page_count",
    "error_code",
)


def instant(value):
    return None if value is None else value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def binding(envelope, version):
    if (
        version["kind"] != "PROCESSED"
        or envelope["kind"] != "INGEST"
        or envelope["version_id"] != version["id"]
        or envelope["document_id"] != version["document_id"]
        or envelope["actor_id"] != version["processing_actor_id"]
        or envelope["idempotency_id"] != uuid5(version["id"], "F04/intent/v1")
    ):
        raise DocumentError("STATE_CONFLICT")


def version_view(row, envelope):
    result = {name: row[name] for name in VERSION_FIELDS}
    result.update(
        version_id=str(row["id"]),
        document_id=str(row["document_id"]),
        original_version_id=(
            None if row["original_version_id"] is None else str(row["original_version_id"])
        ),
        sha256=row["content_hash"],
        created_at=instant(row["created_at"]),
        job_id=None if envelope is None else str(envelope["id"]),
    )
    return result


class IngestionService:
    def __init__(self, repositories):
        if repositories.authority.profile not in ("ingestion", "embeddings"):
            raise ValueError("Ingestion authority required")
        self.repositories = repositories

    def _document(self, c, context, identity):
        row = c.execute(
            sa.select(documents.c.repository_id, documents.c.state).where(
                documents.c.id == identity
            )
        ).one_or_none()
        if row is None:
            raise DocumentError("NOT_FOUND")
        self.repositories._row(c, context, row.repository_id, "read")
        if row.state != "RECEIVED":
            raise DocumentError("NOT_FOUND")
        return row.repository_id

    def _envelopes(self, context, document, rows):
        processed = {row["id"]: row for row in rows if row["kind"] == "PROCESSED"}
        if not processed:
            return {}
        # Separate, bounded control lookup after tenant-local authorization.
        # Reader keeps its existing knowledge/security SELECT, without ops grants.
        with self.repositories.control.connect() as c:
            envelopes = (
                c.execute(
                    sa.select(jobs).where(
                        jobs.c.tenant_id == context.tenant_id,
                        jobs.c.document_id == document,
                        jobs.c.version_id.in_(tuple(processed)),
                        jobs.c.kind == "INGEST",
                    )
                )
                .mappings()
                .all()
            )
        result = {}
        for envelope in envelopes:
            row = processed[envelope["version_id"]]
            binding(envelope, row)
            if row["id"] in result:
                raise DocumentError("STATE_CONFLICT")
            result[row["id"]] = envelope
        return result

    def versions(self, context, trace, document, *, limit=50, cursor=None):
        document = logical_id(document)
        purpose = "F04/versions:" + str(document)
        last = self.repositories.pagination.decode(context, purpose, cursor, limit)

        def operation(c, checked):
            repo = self._document(c, checked, document)
            # Only select required metadata, never filename/blob_key or chunk text.
            names = ("id", "processing_actor_id", "content_hash", "created_at") + VERSION_FIELDS
            query = (
                sa.select(*(versions.c[name] for name in names))
                .where(versions.c.document_id == document, versions.c.repository_id == repo)
                .order_by(versions.c.id)
                .limit(limit + 1)
            )
            if last is not None:
                query = query.where(versions.c.id > last)
            rows = c.execute(query).mappings().all()
            envelopes = self._envelopes(checked, document, rows)
            return self.repositories.pagination.page(
                checked,
                purpose,
                rows,
                limit,
                key=lambda row: row["id"],
                serialize=lambda row: version_view(row, envelopes.get(row["id"])),
            )

        return self.repositories._run(context, trace, "read", operation)

    def job(self, context, trace, identity):
        identity = logical_id(identity)

        def operation(c, checked):
            with self.repositories.control.connect() as control:
                envelope = (
                    control.execute(
                        sa.select(jobs).where(
                            jobs.c.id == identity,
                            jobs.c.tenant_id == checked.tenant_id,
                            jobs.c.kind == "INGEST",
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
            if envelope is None:
                raise DocumentError("NOT_FOUND")
            repo = self._document(c, checked, envelope["document_id"])
            row = (
                c.execute(
                    sa.select(
                        versions.c.id,
                        versions.c.document_id,
                        versions.c.kind,
                        versions.c.processing_actor_id,
                        versions.c.state,
                    ).where(
                        versions.c.id == envelope["version_id"],
                        versions.c.document_id == envelope["document_id"],
                        versions.c.repository_id == repo,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise DocumentError("NOT_FOUND")
            binding(envelope, row)
            return {
                "job_id": str(envelope["id"]),
                "document_id": str(envelope["document_id"]),
                "version_id": str(envelope["version_id"]),
                "kind": envelope["kind"],
                "status": envelope["status"],
                "attempts": envelope["attempts"],
                "max_attempts": envelope["max_attempts"],
                "error_code": envelope["error_code"],
                "created_at": instant(envelope["created_at"]),
                "updated_at": instant(envelope["updated_at"]),
                "finished_at": instant(envelope["finished_at"]),
                "version_state": row["state"],
            }

        return self.repositories._run(context, trace, "read", operation)
