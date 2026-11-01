"""Tenant-local upload journal: quota, fencing and forward recovery without object deletion."""

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, timedelta
from uuid import UUID, uuid4, uuid5

import sqlalchemy as sa

from rag_platform.documents.errors import DocumentError
from rag_platform.documents.schema import (
    document_receipts,
    document_versions,
    documents,
    sources,
)
from rag_platform.documents.storage import Blob
from rag_platform.documents.validation import ValidatedFile


@dataclass(frozen=True, slots=True, repr=False)
class Plan:
    id: UUID
    repository_id: UUID
    principal_id: UUID
    document_id: UUID
    version_id: UUID
    attempt_id: UUID
    state: str
    fingerprint: str

    def __repr__(self):
        return "ReceiptPlan(<private>)"


@dataclass(frozen=True, slots=True, repr=False)
class Received:
    document: dict
    created: bool

    def __repr__(self):
        return "Received(<private>)"


def quota_key(tenant):
    return int.from_bytes(
        hashlib.sha256(b"F03/quota:" + tenant.bytes).digest()[:8], "big", signed=True
    )


def as_plan(row):
    return Plan(
        row.id,
        row.repository_id,
        row.principal_id,
        row.candidate_document_id,
        row.version_id,
        row.attempt_id,
        row.state,
        row.fingerprint,
    )


def document_view(c, plan):
    row = c.execute(
        sa.select(
            documents.c.id,
            documents.c.repository_id,
            documents.c.source_id,
            document_versions.c.id.label("version_id"),
            document_versions.c.filename,
            document_versions.c.mime,
            document_versions.c.byte_size,
            document_versions.c.content_hash,
            document_versions.c.created_at,
        )
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
            documents.c.id == plan.document_id,
            documents.c.repository_id == plan.repository_id,
            document_versions.c.id == plan.version_id,
            documents.c.state == "RECEIVED",
            document_versions.c.state == "RECEIVED",
            sources.c.provider == "UPLOAD",
        )
    ).one_or_none()
    if row is None:
        raise DocumentError()
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


class ReceiptService:
    def __init__(
        self,
        repositories,
        gateway,
        *,
        tenant_bytes=100 * 1024 * 1024,
        lease_seconds=60,
        max_receipts=10000,
    ):
        if type(tenant_bytes) is not int or not 1 <= tenant_bytes <= 1024 * 1024 * 1024:
            raise ValueError("Invalid tenant quota")
        if type(lease_seconds) is not int or not 2 <= lease_seconds <= 60:
            raise ValueError("Invalid receipt lease")
        if type(max_receipts) is not int or not 1 <= max_receipts <= 10000:
            raise ValueError("Invalid receipt capacity")
        self.max_receipts = max_receipts
        self.repositories, self.gateway = repositories, gateway
        self.quota, self.lease = tenant_bytes, lease_seconds
        self.authority = repositories.authority

    def _stage(self, stage, plan):
        """Integration subclasses can stop a real process at durable boundaries."""

    def preflight(self, context, trace, repo):
        return self.repositories.require(context, trace, repo, "upload")

    def _lock(self, c, checked, repo):
        # Cross-repository reservations share a tenant quota lock, then row locks.
        c.execute(
            sa.text("SELECT pg_advisory_xact_lock(:key)"), {"key": quota_key(checked.tenant_id)}
        )
        self.repositories._row(c, checked, repo, "upload", lock=True)

    def _current(self, c, checked, plan):
        row = c.execute(
            sa.select(document_receipts)
            .where(
                document_receipts.c.id == plan.id,
                document_receipts.c.repository_id == plan.repository_id,
                document_receipts.c.principal_id == checked.principal_id,
            )
            .with_for_update()
        ).one_or_none()
        now = c.scalar(sa.select(sa.func.current_timestamp()))
        if (
            row is None
            or row.attempt_id != plan.attempt_id
            or row.state == "COMMITTED"
            or row.lease_until is None
            or row.lease_until <= now
            or row.fingerprint != plan.fingerprint
        ):
            raise DocumentError("STATE_CONFLICT")
        return row

    def _reserve(self, context, trace, repo, key, file):
        fingerprint = file.fingerprint(context.principal_id, repo)

        def operation(c, checked):
            self._lock(c, checked, repo)
            row = c.execute(
                sa.select(document_receipts)
                .where(
                    document_receipts.c.repository_id == repo,
                    document_receipts.c.principal_id == checked.principal_id,
                    document_receipts.c.idempotency_key == key,
                )
                .with_for_update()
            ).one_or_none()
            now = c.scalar(sa.select(sa.func.current_timestamp()))
            if row is not None:
                if row.fingerprint != fingerprint:
                    raise DocumentError("STATE_CONFLICT")
                if row.state == "COMMITTED":
                    return as_plan(row)
                if row.state != "FAILED" and row.lease_until is not None and row.lease_until > now:
                    raise DocumentError("OPERATION_IN_PROGRESS")
                # Existing reservations keep their byte charge, even if a prior
                # remote outcome was unknown. Never free quota based on HEAD alone.
                values = {
                    "attempt_id": uuid4(),
                    "lease_until": now + timedelta(seconds=self.lease),
                    "state": "OBJECT_STORED" if row.state == "OBJECT_STORED" else "PENDING",
                    "updated_at": sa.func.current_timestamp(),
                }
                return as_plan(
                    c.execute(
                        document_receipts.update()
                        .where(document_receipts.c.id == row.id)
                        .values(**values)
                        .returning(document_receipts)
                    ).one()
                )
            used, count = c.execute(
                sa.select(
                    sa.func.coalesce(sa.func.sum(document_receipts.c.byte_size), 0),
                    sa.func.count(),
                )
            ).one()
            if used + file.byte_size > self.quota or count >= self.max_receipts:
                raise DocumentError("QUOTA_EXCEEDED")
            return as_plan(
                c.execute(
                    document_receipts.insert()
                    .values(
                        id=uuid4(),
                        repository_id=repo,
                        principal_id=checked.principal_id,
                        idempotency_key=key,
                        fingerprint=fingerprint,
                        candidate_document_id=uuid4(),
                        version_id=uuid4(),
                        byte_size=file.byte_size,
                        state="PENDING",
                        attempt_id=uuid4(),
                        lease_until=now + timedelta(seconds=self.lease),
                    )
                    .returning(document_receipts)
                ).one()
            )

        return self.repositories._run(context, trace, "upload", operation)

    def _stored(self, context, trace, plan):
        def operation(c, checked):
            self._lock(c, checked, plan.repository_id)
            self._current(c, checked, plan)
            c.execute(
                document_receipts.update()
                .where(document_receipts.c.id == plan.id)
                .values(
                    state="OBJECT_STORED",
                    updated_at=sa.func.current_timestamp(),
                )
            )

        self.repositories._run(context, trace, "upload", operation)

    def _complete(self, context, trace, plan, file):
        def operation(c, checked):
            self._lock(c, checked, plan.repository_id)
            row = self._current(c, checked, plan)
            if row.state != "OBJECT_STORED":
                raise DocumentError("STATE_CONFLICT")
            source = uuid5(plan.id, "source")
            c.execute(
                sources.insert().values(
                    id=source,
                    repository_id=plan.repository_id,
                    provider="UPLOAD",
                    created_by=checked.principal_id,
                )
            )
            c.execute(
                documents.insert().values(
                    id=plan.document_id,
                    repository_id=plan.repository_id,
                    source_id=source,
                    current_version_id=plan.version_id,
                    state="RECEIVED",
                    created_by=checked.principal_id,
                )
            )
            c.execute(
                document_versions.insert().values(
                    id=plan.version_id,
                    document_id=plan.document_id,
                    repository_id=plan.repository_id,
                    filename=file.filename,
                    mime=file.mime,
                    byte_size=file.byte_size,
                    content_hash=file.content_hash,
                    blob_key=f"f03/{plan.repository_id.hex}/{plan.version_id.hex}",
                    state="RECEIVED",
                )
            )
            c.execute(
                document_receipts.update()
                .where(document_receipts.c.id == plan.id)
                .values(
                    state="COMMITTED",
                    committed_version_id=plan.version_id,
                    lease_until=None,
                    updated_at=sa.func.current_timestamp(),
                )
            )
            self.repositories.event(
                c, checked, trace, plan.repository_id, plan.document_id, "DOCUMENT_RECEIVED"
            )
            return Received(document_view(c, plan), True)

        return self.repositories._run(context, trace, "upload", operation)

    def _duplicate(self, context, trace, plan):
        def operation(c, checked):
            self.repositories._row(c, checked, plan.repository_id, "upload")
            return Received(document_view(c, plan), False)

        return self.repositories._run(context, trace, "upload", operation)

    def receive(self, context, trace, repo, key, file):
        self.preflight(context, trace, repo)
        if (
            not isinstance(repo, UUID)
            or not isinstance(key, str)
            or re.fullmatch("[A-Za-z0-9._:-]{16,128}", key) is None
            or not isinstance(file, ValidatedFile)
        ):
            raise DocumentError("INPUT_INVALID")
        context = self.authority.validate(context, trace)
        plan = self._reserve(context, trace, repo, key, file)
        blob = Blob(
            plan.id,
            repo,
            plan.version_id,
            plan.fingerprint,
            file.content_hash,
            file.byte_size,
            file.mime,
            file.md5,
        )
        if plan.state == "COMMITTED":
            if self.gateway.inspect(context, trace, blob) is None:
                raise DocumentError()  # No silent repair/adoption of a missing committed original.
            return self._duplicate(context, trace, plan)
        self._stage("RESERVED", plan)
        self.gateway.create(context, trace, blob, file)
        self._stage("OBJECT_AVAILABLE", plan)
        context = self.authority.validate(context, trace)
        self._stored(context, trace, plan)
        self._stage("JOURNALED", plan)
        if self.gateway.inspect(context, trace, blob) is None:
            raise DocumentError()
        context = self.authority.validate(context, trace)
        result = self._complete(context, trace, plan, file)
        self._stage("COMMITTED", plan)
        return result
