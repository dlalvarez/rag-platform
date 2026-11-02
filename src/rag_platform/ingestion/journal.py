"""Tenant-local durable intent. Caller owns authorization and transaction boundaries."""

from dataclasses import dataclass
from uuid import UUID, uuid4, uuid5

import sqlalchemy as sa

from rag_platform.documents.policy import repository_allows
from rag_platform.ingestion.extraction import CHUNKER, NORMALIZER, PARSERS, ChunkConfig
from rag_platform.ingestion.schema import audit, documents, intents, metadata, versions

repositories = metadata.tables["knowledge.repositories"]
acl = metadata.tables["security.repository_acl"]


class IngestionError(RuntimeError):
    def __init__(self, code="DEPENDENCY_UNAVAILABLE"):
        allowed = {
            "INPUT_INVALID",
            "NOT_FOUND",
            "AUTHORIZATION_CHANGED",
            "TOMBSTONED",
            "IDEMPOTENCY_CONFLICT",
            "STATE_CONFLICT",
            "DEPENDENCY_UNAVAILABLE",
        }
        self.code = code if isinstance(code, str) and code in allowed else "DEPENDENCY_UNAVAILABLE"
        super().__init__(self.code)


@dataclass(frozen=True, slots=True, repr=False)
class Intent:
    id: UUID
    version_id: UUID
    document_id: UUID
    repository_id: UUID
    actor_id: UUID

    def __repr__(self):
        return "Intent(<private>)"


def identifiers(*values):
    if not all(isinstance(value, UUID) and value.int != 0 for value in values):
        raise IngestionError("INPUT_INVALID")


def require(c, actor, repository, document, *, allow_tombstone=False):
    """Serialize with existing F03 ACL/repository writes and F04 tombstones.

    This is a local policy check, not a substitute for a verified tenant context.
    The caller must also revalidate active user/membership/catalog at its boundary.
    """
    identifiers(actor, repository, document)
    repo = c.execute(
        sa.select(repositories.c.id, repositories.c.state)
        .where(repositories.c.id == repository)
        .with_for_update()
    ).first()
    role = c.scalar(
        sa.select(acl.c.role).where(acl.c.repository_id == repository, acl.c.principal_id == actor)
    )
    if repo is None or repo.state != "ACTIVE" or not repository_allows(role, "upload"):
        raise IngestionError("AUTHORIZATION_CHANGED")
    row = c.execute(
        sa.select(documents)
        .where(documents.c.id == document, documents.c.repository_id == repository)
        .with_for_update()
    ).first()
    if row is None:
        raise IngestionError("NOT_FOUND")
    if row.state != "RECEIVED" and not allow_tombstone:
        raise IngestionError("TOMBSTONED")
    return row


def _as_intent(row):
    return Intent(row.id, row.version_id, row.document_id, row.repository_id, row.actor_id)


def load(c, identity):
    identifiers(identity)
    row = c.execute(sa.select(intents).where(intents.c.id == identity)).first()
    if row is None:
        raise IngestionError("NOT_FOUND")
    return _as_intent(row)


def _same(row, plan):
    return row is not None and all(
        row[key] == getattr(plan, key)
        for key in ("id", "version_id", "document_id", "repository_id", "actor_id")
    )


def request(c, actor, repository, document, trace, config=None):
    """Create candidate and intent atomically, without network or control writes."""
    identifiers(actor, repository, document, trace)
    config = ChunkConfig() if config is None else config
    if not isinstance(config, ChunkConfig):
        raise IngestionError("INPUT_INVALID")
    doc = require(c, actor, repository, document)
    raw = c.execute(
        sa.select(versions).where(
            versions.c.id == doc.current_version_id,
            versions.c.document_id == document,
            versions.c.repository_id == repository,
            versions.c.kind == "ORIGINAL",
            versions.c.state == "RECEIVED",
        )
    ).first()
    if raw is None or raw.mime not in PARSERS:
        raise IngestionError("STATE_CONFLICT")
    fingerprint = config.fingerprint(raw.mime)
    version = uuid5(raw.id, "F04/processing/v1:" + fingerprint)
    identity = uuid5(version, "F04/intent/v1")
    existing = c.execute(
        sa.select(versions).where(
            versions.c.document_id == document,
            versions.c.original_version_id == raw.id,
            versions.c.config_hash == fingerprint,
            versions.c.kind == "PROCESSED",
        )
    ).first()
    plan = Intent(identity, version, document, repository, actor)
    if existing is not None:
        row = (
            c.execute(sa.select(intents).where(intents.c.version_id == existing.id))
            .mappings()
            .first()
        )
        if existing.id != version or existing.processing_actor_id != actor or not _same(row, plan):
            raise IngestionError("IDEMPOTENCY_CONFLICT")
        return plan
    c.execute(
        sa.insert(versions).values(
            id=version,
            document_id=document,
            repository_id=repository,
            filename=raw.filename,
            mime=raw.mime,
            byte_size=raw.byte_size,
            content_hash=raw.content_hash,
            blob_key=None,
            kind="PROCESSED",
            original_version_id=raw.id,
            processing_actor_id=actor,
            parser_id=PARSERS[raw.mime],
            normalizer_id=NORMALIZER,
            chunker_id=CHUNKER,
            config_hash=fingerprint,
            chunk_size=config.size,
            chunk_overlap=config.overlap,
        )
    )
    c.execute(
        sa.insert(intents).values(
            id=identity,
            version_id=version,
            document_id=document,
            repository_id=repository,
            actor_id=actor,
        )
    )
    c.execute(
        sa.insert(audit).values(
            id=uuid4(),
            principal_id=actor,
            repository_id=repository,
            target_id=version,
            request_id=trace,
            action="INGESTION_REQUESTED",
            outcome="OK",
        )
    )
    return plan


def pending(c, *, limit=25):
    """Bounded local relay batch, not a client-visible or cross-tenant query."""
    if type(limit) is not int or not 1 <= limit <= 100:
        raise IngestionError("INPUT_INVALID")
    rows = c.execute(
        sa.select(intents)
        .where(intents.c.dispatch_state == "PENDING")
        .order_by(intents.c.created_at, intents.c.id)
        .limit(limit)
    ).all()
    return tuple(_as_intent(row) for row in rows)


def enqueue(queue, tenant, plan):
    """Control commit may succeed before caller records local dispatch."""
    if not isinstance(plan, Intent):
        raise IngestionError("INPUT_INVALID")
    identifiers(
        tenant, plan.id, plan.version_id, plan.document_id, plan.repository_id, plan.actor_id
    )
    return queue.enqueue(tenant, plan.actor_id, plan.document_id, plan.version_id, plan.id)


def dispatched(c, plan, job):
    """Retry after a lost acknowledgement adopts only the exact original envelope."""
    if not isinstance(plan, Intent):
        raise IngestionError("INPUT_INVALID")
    identifiers(job, plan.id, plan.version_id, plan.document_id, plan.repository_id, plan.actor_id)
    require(c, plan.actor_id, plan.repository_id, plan.document_id)
    row = (
        c.execute(sa.select(intents).where(intents.c.id == plan.id).with_for_update())
        .mappings()
        .first()
    )
    if not _same(row, plan):
        raise IngestionError("IDEMPOTENCY_CONFLICT")
    if row["dispatch_state"] == "DISPATCHED":
        if row["job_id"] != job:
            raise IngestionError("IDEMPOTENCY_CONFLICT")
        return False
    c.execute(
        sa.update(intents)
        .where(intents.c.id == plan.id)
        .values(
            dispatch_state="DISPATCHED",
            job_id=job,
            dispatched_at=sa.func.clock_timestamp(),
            updated_at=sa.func.clock_timestamp(),
        )
    )
    return True
