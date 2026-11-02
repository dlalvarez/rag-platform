"""Tenant batch ledger operations. Caller owns fresh authorization and commit fencing."""

import hashlib
from dataclasses import asdict, dataclass
from uuid import UUID, uuid4, uuid5

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from rag_platform.embeddings.contracts import EmbeddingProfile, validate
from rag_platform.embeddings.publication_schema_f05_0006 import ERRORS, build_metadata
from rag_platform.embeddings.queue import EmbeddingClaim
from rag_platform.embeddings.space_ddl import vector_table
from rag_platform.ingestion import journal
from rag_platform.ingestion.claims import ClaimExpired
from rag_platform.ingestion.queue import _now

MAX_JOB_CHUNKS = 64
MAX_JOB_TOKENS = 32768

metadata = build_metadata()
intents = metadata.tables["ops.embedding_intents"]
batches = metadata.tables["ops.embedding_batches"]
publications = metadata.tables["knowledge.embedding_publications"]
spaces = metadata.tables["knowledge.embedding_spaces"]
versions = metadata.tables["knowledge.document_versions"]
documents = metadata.tables["knowledge.documents"]
chunks = metadata.tables["knowledge.chunks"]
audit = metadata.tables["ops.audit_events"]


class ProcessingError(RuntimeError):
    CODES = {
        "INPUT_INVALID",
        "STATE_CONFLICT",
        "PROFILE_MISMATCH",
        "QUOTA_EXCEEDED",
        "AUTHORIZATION_CHANGED",
        "TOMBSTONED",
        "DEPENDENCY_UNAVAILABLE",
    }

    def __init__(self, code="DEPENDENCY_UNAVAILABLE"):
        self.code = (
            code if isinstance(code, str) and code in self.CODES else "DEPENDENCY_UNAVAILABLE"
        )
        super().__init__(self.code)


@dataclass(frozen=True, slots=True, repr=False)
class Intent:
    id: UUID
    version_id: UUID
    document_id: UUID
    repository_id: UUID
    actor_id: UUID
    space_id: UUID
    profile_fingerprint: str

    def __repr__(self):
        return "EmbeddingIntent(<private metadata>)"


@dataclass(frozen=True, slots=True, repr=False)
class Batch:
    plan: Intent
    ordinal: int
    chunk_ids: tuple[UUID, ...]
    texts: tuple[str, ...]
    hashes: tuple[str, ...]
    used_tokens: int

    def __repr__(self):
        return "EmbeddingInputs(<private>)"


def _plan(row):
    return Intent(
        *(
            row[name]
            for name in (
                "id",
                "version_id",
                "document_id",
                "repository_id",
                "actor_id",
                "space_id",
                "profile_fingerprint",
            )
        )
    )


def _values(plan):
    return {
        name: getattr(plan, name)
        for name in (
            "version_id",
            "document_id",
            "repository_id",
            "actor_id",
            "space_id",
            "profile_fingerprint",
        )
    }


def _space(c, space, profile):
    if not isinstance(profile, EmbeddingProfile):
        raise ProcessingError("INPUT_INVALID")
    row = c.execute(sa.select(spaces).where(spaces.c.id == space)).mappings().one_or_none()
    expected = asdict(profile) | {"profile_fingerprint": profile.fingerprint()}
    if row is None or any(row[k] != v for k, v in expected.items()):
        raise ProcessingError("PROFILE_MISMATCH")


def request(c, actor, repository, document, version_id, profile):
    """Explicit authorized request, also used by new F05 ingestion completion."""
    if not isinstance(profile, EmbeddingProfile):
        raise ProcessingError("INPUT_INVALID")
    journal.identifiers(version_id)
    doc = journal.require(c, actor, repository, document)
    version = c.execute(
        sa.select(versions.c.id, versions.c.original_version_id).where(
            versions.c.id == version_id,
            versions.c.document_id == document,
            versions.c.repository_id == repository,
            versions.c.kind == "PROCESSED",
            versions.c.state.in_(("READY_FOR_EMBEDDING", "PUBLISHED")),
        )
    ).one_or_none()
    anchor = c.scalar(sa.select(documents.c.original_version_id).where(documents.c.id == doc.id))
    if version is None or version.original_version_id != anchor:
        raise ProcessingError("STATE_CONFLICT")
    space = c.scalar(
        sa.select(spaces.c.id).where(spaces.c.profile_fingerprint == profile.fingerprint())
    )
    if space is None:
        raise ProcessingError("PROFILE_MISMATCH")
    _space(c, space, profile)
    plan = Intent(
        uuid5(space, "F05/intent/v1:" + str(version_id)),
        version_id,
        document,
        repository,
        actor,
        space,
        profile.fingerprint(),
    )
    insert = pg_insert if c.dialect.name == "postgresql" else sqlite_insert
    c.execute(insert(intents).values(id=plan.id, **_values(plan)).on_conflict_do_nothing())
    row = (
        c.execute(
            sa.select(intents).where(
                intents.c.version_id == version_id, intents.c.space_id == space
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None or _plan(row) != plan:
        raise ProcessingError("STATE_CONFLICT")
    return plan


def pending(c, *, limit=25, profile=None):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ProcessingError("INPUT_INVALID")
    return tuple(
        _plan(r)
        for r in c.execute(
            sa.select(intents)
            .where(
                intents.c.dispatch_state == "PENDING",
                intents.c.profile_fingerprint == profile.fingerprint()
                if profile is not None
                else sa.true(),
            )
            .order_by(intents.c.created_at, intents.c.id)
            .limit(limit)
        ).mappings()
    )


def enqueue(queue, tenant, plan):
    if not isinstance(plan, Intent):
        raise ProcessingError("INPUT_INVALID")
    return queue.enqueue(
        tenant,
        plan.actor_id,
        plan.document_id,
        plan.version_id,
        plan.id,
        plan.space_id,
        plan.profile_fingerprint,
    )


def dispatched(c, plan, job):
    row = (
        c.execute(sa.select(intents).where(intents.c.id == plan.id).with_for_update())
        .mappings()
        .one_or_none()
    )
    if row is None or _plan(row) != plan:
        raise ProcessingError("STATE_CONFLICT")
    if row["dispatch_state"] == "DISPATCHED":
        if row["job_id"] != job:
            raise ProcessingError("STATE_CONFLICT")
        return False
    c.execute(
        intents.update()
        .where(intents.c.id == plan.id)
        .values(
            dispatch_state="DISPATCHED",
            job_id=job,
            dispatched_at=_now(c),
            updated_at=_now(c),
        )
    )
    return True


def identity(c, guard, *, lock=False):
    guard.check()
    claim = guard.claim
    if not isinstance(claim, EmbeddingClaim):
        raise ProcessingError("INPUT_INVALID")
    query = sa.select(intents).where(
        intents.c.id == guard.intent_id,
        intents.c.version_id == claim.version_id,
        intents.c.document_id == claim.document_id,
        intents.c.actor_id == claim.actor_id,
        intents.c.space_id == claim.space_id,
        intents.c.profile_fingerprint == claim.profile_fingerprint,
    )
    if lock:
        query = query.with_for_update()
    row = c.execute(query).mappings().one_or_none()
    if row is None or (row["job_id"] is not None and row["job_id"] != claim.id):
        raise ProcessingError("STATE_CONFLICT")
    return _plan(row), row


def published(c, guard):
    """Metadata reconciliation only, even when the original actor has since lost access."""
    plan, row = identity(c, guard)
    found = (
        c.execute(
            sa.select(publications).where(
                publications.c.version_id == plan.version_id,
                publications.c.space_id == plan.space_id,
            )
        )
        .mappings()
        .one_or_none()
    )
    if found is None:
        return False
    if (
        row["status"] != "COMPLETE"
        or found["intent_id"] != plan.id
        or any(found[k] != v for k, v in _values(plan).items())
    ):
        raise ProcessingError("STATE_CONFLICT")
    return True


def _active(c, guard, profile):
    plan, row = identity(c, guard, lock=True)
    if plan.profile_fingerprint != profile.fingerprint():
        raise ProcessingError("PROFILE_MISMATCH")
    _space(c, plan.space_id, profile)
    doc = journal.require(c, plan.actor_id, plan.repository_id, plan.document_id)
    version = (
        c.execute(
            sa.select(versions)
            .where(
                versions.c.id == plan.version_id,
                versions.c.document_id == plan.document_id,
                versions.c.repository_id == plan.repository_id,
                versions.c.kind == "PROCESSED",
            )
            .with_for_update()
        )
        .mappings()
        .one_or_none()
    )
    anchor = c.scalar(
        sa.select(documents.c.original_version_id).where(documents.c.id == plan.document_id)
    )
    if (
        version is None
        or version["state"] not in ("READY_FOR_EMBEDDING", "PUBLISHED")
        or (version["original_version_id"] != anchor)
    ):
        raise ProcessingError("STATE_CONFLICT")
    if not 1 <= version["chunk_count"] <= MAX_JOB_CHUNKS:
        raise ProcessingError("QUOTA_EXCEEDED")
    return plan, row, doc, version


def _progress(c, plan, version, profile):
    ordered = tuple(
        c.scalars(
            sa.select(chunks.c.id)
            .where(
                chunks.c.version_id == plan.version_id,
                chunks.c.document_id == plan.document_id,
                chunks.c.repository_id == plan.repository_id,
            )
            .order_by(chunks.c.ordinal)
            .limit(10001)
        )
    )
    if len(ordered) != version["chunk_count"]:
        raise ProcessingError("STATE_CONFLICT")
    saved = c.execute(
        sa.select(batches.c.ordinal, batches.c.chunk_ids, batches.c.input_tokens)
        .where(batches.c.intent_id == plan.id)
        .order_by(batches.c.ordinal)
        .limit(10001)
    ).all()
    done = []
    used_tokens = 0
    for ordinal, batch in enumerate(saved):
        if batch.ordinal != ordinal or not 1 <= len(batch.chunk_ids) <= profile.max_batch:
            raise ProcessingError("STATE_CONFLICT")
        if type(
            batch.input_tokens
        ) is not int or not 1 <= batch.input_tokens <= profile.max_tokens * len(batch.chunk_ids):
            raise ProcessingError("STATE_CONFLICT")
        used_tokens += batch.input_tokens
        done.extend(batch.chunk_ids)
    if tuple(done) != ordered[: len(done)] or len(done) > len(ordered):
        raise ProcessingError("STATE_CONFLICT")
    vectors = vector_table(build_metadata(), plan.space_id, profile)
    count = c.scalar(
        sa.select(sa.func.count())
        .select_from(vectors)
        .where(
            vectors.c.version_id == plan.version_id,
            vectors.c.document_id == plan.document_id,
            vectors.c.repository_id == plan.repository_id,
        )
    )
    if count != len(done):
        raise ProcessingError("STATE_CONFLICT")
    if used_tokens > MAX_JOB_TOKENS:
        raise ProcessingError("QUOTA_EXCEEDED")
    return ordered, len(saved), len(done), vectors, used_tokens


def start(c, guard, profile):
    plan, row, _doc, version = _active(c, guard, profile)
    claim = guard.claim
    if row["status"] == "COMPLETE":
        raise ProcessingError("STATE_CONFLICT")
    if row["attempt"] > claim.attempt or (
        row["attempt"] == claim.attempt and row["attempt_token"] not in (None, claim.token)
    ):
        raise ClaimExpired()
    _progress(c, plan, version, profile)
    c.execute(
        intents.update()
        .where(intents.c.id == plan.id)
        .values(
            status="RUNNING",
            attempt=claim.attempt,
            attempt_token=claim.token,
            lease_until=guard.check(),
            error_code="NONE",
            updated_at=_now(c),
        )
    )


def _attempt(c, guard, row, plan):
    if (row["status"], row["attempt"], row["attempt_token"]) != (
        "RUNNING",
        guard.claim.attempt,
        guard.claim.token,
    ):
        raise ClaimExpired()
    c.execute(
        intents.update()
        .where(intents.c.id == plan.id)
        .values(
            lease_until=guard.check(),
            updated_at=_now(c),
        )
    )


def next_batch(c, guard, profile):
    plan, row, _doc, version = _active(c, guard, profile)
    _attempt(c, guard, row, plan)
    ordered, ordinal, done, _vectors, used_tokens = _progress(c, plan, version, profile)
    if done == len(ordered):
        return None
    rows = c.execute(
        sa.select(chunks.c.id, chunks.c.text, chunks.c.content_hash)
        .where(
            chunks.c.id.in_(ordered[done : done + profile.max_batch]),
            chunks.c.version_id == plan.version_id,
            chunks.c.document_id == plan.document_id,
            chunks.c.repository_id == plan.repository_id,
        )
        .order_by(chunks.c.ordinal)
    ).all()
    if tuple(r.id for r in rows) != ordered[done : done + len(rows)] or not rows:
        raise ProcessingError("STATE_CONFLICT")
    return Batch(
        plan,
        ordinal,
        tuple(r.id for r in rows),
        tuple(r.text for r in rows),
        tuple(r.content_hash for r in rows),
        used_tokens,
    )


def save_batch(c, guard, profile, task, response, elapsed_ms):
    if (
        not isinstance(task, Batch)
        or type(elapsed_ms) is not int
        or not 0 <= elapsed_ms <= 86400000
    ):
        raise ProcessingError("INPUT_INVALID")
    result = validate(profile, task.texts, "passage", response)
    if (
        tuple(hashlib.sha256(text.encode("utf-8")).hexdigest() for text in task.texts)
        != task.hashes
    ):
        raise ProcessingError("STATE_CONFLICT")
    plan, row, _doc, version = _active(c, guard, profile)
    _attempt(c, guard, row, plan)
    ordered, ordinal, done, vectors, used_tokens = _progress(c, plan, version, profile)
    if used_tokens + result.total_tokens > MAX_JOB_TOKENS:
        raise ProcessingError("QUOTA_EXCEEDED")
    if (
        plan != task.plan
        or task.ordinal != ordinal
        or task.chunk_ids != ordered[done : done + len(task.chunk_ids)]
    ):
        raise ProcessingError("STATE_CONFLICT")
    current = c.execute(
        sa.select(chunks.c.id, chunks.c.content_hash)
        .where(
            chunks.c.id.in_(task.chunk_ids),
            chunks.c.version_id == plan.version_id,
        )
        .order_by(chunks.c.ordinal)
    ).all()
    if tuple(r.content_hash for r in current) != task.hashes:
        raise ProcessingError("STATE_CONFLICT")
    c.execute(
        vectors.insert(),
        [
            dict(
                chunk_id=chunk,
                version_id=plan.version_id,
                document_id=plan.document_id,
                repository_id=plan.repository_id,
                space_id=plan.space_id,
                dimension=profile.dimension,
                profile_fingerprint=profile.fingerprint(),
                embedding=vector,
            )
            for chunk, vector in zip(task.chunk_ids, result.vectors, strict=True)
        ],
    )
    c.execute(
        batches.insert().values(
            **_values(plan),
            intent_id=plan.id,
            ordinal=ordinal,
            chunk_ids=list(task.chunk_ids),
            input_tokens=result.total_tokens,
            requests=1,
            elapsed_ms=elapsed_ms,
        )
    )
    guard.check()
    return len(task.chunk_ids)


def complete(c, guard, profile):
    plan, row, doc, version = _active(c, guard, profile)
    _attempt(c, guard, row, plan)
    ordered, _ordinal, done, _vectors, _used_tokens = _progress(c, plan, version, profile)
    if done != len(ordered):
        raise ProcessingError("STATE_CONFLICT")
    if doc.current_version_kind == "PROCESSED" and doc.current_version_id != plan.version_id:
        current_time = c.scalar(
            sa.select(versions.c.created_at).where(versions.c.id == doc.current_version_id)
        )
        if current_time is not None and current_time > version["created_at"]:
            raise ProcessingError("STATE_CONFLICT")
    if version["state"] != "PUBLISHED":
        c.execute(
            versions.update().where(versions.c.id == plan.version_id).values(state="PUBLISHED")
        )
    c.execute(
        documents.update()
        .where(documents.c.id == plan.document_id)
        .values(
            current_version_id=plan.version_id,
            current_version_kind="PROCESSED",
        )
    )
    c.execute(
        intents.update()
        .where(intents.c.id == plan.id)
        .values(
            status="COMPLETE",
            attempt_token=None,
            lease_until=None,
            updated_at=_now(c),
        )
    )
    c.execute(
        publications.insert().values(
            **_values(plan),
            intent_id=plan.id,
            chunk_count=len(ordered),
        )
    )
    c.execute(
        audit.insert().values(
            id=uuid4(),
            principal_id=plan.actor_id,
            repository_id=plan.repository_id,
            target_id=plan.id,
            request_id=guard.claim.id,
            action="EMBEDDING_PUBLISHED",
            outcome="OK",
        )
    )
    if c.dialect.name == "postgresql":
        c.exec_driver_sql("SET CONSTRAINTS ALL IMMEDIATE")
        c.exec_driver_sql("SET CONSTRAINTS ALL DEFERRED")
    guard.check()


def failure(c, guard, profile, code):
    if not isinstance(code, str) or code not in ERRORS or code == "NONE":
        raise ProcessingError("INPUT_INVALID")
    plan, row, _doc, _version = _active(c, guard, profile)
    _attempt(c, guard, row, plan)
    c.execute(
        intents.update()
        .where(intents.c.id == plan.id)
        .values(
            status="FAILED",
            error_code=code,
            attempt_token=None,
            lease_until=None,
            updated_at=_now(c),
        )
    )
