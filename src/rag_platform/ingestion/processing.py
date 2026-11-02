"""Atomic tenant result writes. Authorization/control fence are owned by the caller."""

import hashlib
from dataclasses import dataclass
from uuid import uuid4, uuid5

import sqlalchemy as sa

from rag_platform.ingestion import journal
from rag_platform.ingestion.claims import ClaimExpired
from rag_platform.ingestion.extraction import CHUNKER, NORMALIZER, PARSERS, ChunkConfig, Extraction
from rag_platform.ingestion.extraction import chunks as make_chunks
from rag_platform.ingestion.schema import audit, blocks, chunks, intents, versions
from rag_platform.ingestion.schema_f04_0003 import ERRORS

FINAL = {"READY_FOR_EMBEDDING", "FAILED_TERMINAL", "NEEDS_OCR", "TOMBSTONED"}


@dataclass(frozen=True, slots=True, repr=False)
class Task:
    plan: journal.Intent
    original: object
    version: object
    config: ChunkConfig

    def __repr__(self):
        return "ProcessingTask(<private>)"


def identity(c, guard):
    claim = guard.claim
    row = c.execute(
        sa.select(intents).where(
            intents.c.id == guard.intent_id,
            intents.c.version_id == claim.version_id,
            intents.c.document_id == claim.document_id,
            intents.c.actor_id == claim.actor_id,
        )
    ).first()
    if row is None or (row.job_id is not None and row.job_id != claim.id):
        raise journal.IngestionError("STATE_CONFLICT")
    return journal.Intent(row.id, row.version_id, row.document_id, row.repository_id, row.actor_id)


def inspect(c, guard):
    plan = identity(c, guard)
    row = c.execute(
        sa.select(versions.c.state, versions.c.error_code).where(
            versions.c.id == plan.version_id,
            versions.c.document_id == plan.document_id,
            versions.c.repository_id == plan.repository_id,
            versions.c.kind == "PROCESSED",
            versions.c.processing_actor_id == plan.actor_id,
        )
    ).first()
    if row is None:
        raise journal.IngestionError("STATE_CONFLICT")
    return row


def _task(c, guard):
    guard.check()
    plan = identity(c, guard)
    journal.require(c, plan.actor_id, plan.repository_id, plan.document_id)
    intent = c.execute(sa.select(intents).where(intents.c.id == plan.id).with_for_update()).first()
    row = c.execute(
        sa.select(versions)
        .where(
            versions.c.id == plan.version_id,
            versions.c.kind == "PROCESSED",
            versions.c.processing_actor_id == plan.actor_id,
        )
        .with_for_update()
    ).first()
    if row is None or intent is None:
        raise journal.IngestionError("STATE_CONFLICT")
    original = c.execute(
        sa.select(versions).where(
            versions.c.id == row.original_version_id,
            versions.c.kind == "ORIGINAL",
            versions.c.document_id == plan.document_id,
            versions.c.repository_id == plan.repository_id,
        )
    ).first()
    if original is None:
        raise journal.IngestionError("STATE_CONFLICT")
    config = ChunkConfig(row.chunk_size, row.chunk_overlap)
    if (
        row.parser_id != PARSERS.get(row.mime)
        or row.normalizer_id != NORMALIZER
        or row.chunker_id != CHUNKER
        or row.config_hash != config.fingerprint(row.mime)
    ):
        raise journal.IngestionError("STATE_CONFLICT")
    return Task(plan, original, row, config), intent


def start(c, guard):
    task, intent = _task(c, guard)
    claim = guard.claim
    if task.version.state in FINAL:
        return task
    if intent.attempt > claim.attempt or (
        intent.attempt == claim.attempt and intent.attempt_token != claim.token
    ):
        raise ClaimExpired()
    journal.dispatched(c, task.plan, claim.id)
    c.execute(
        sa.update(intents)
        .where(intents.c.id == task.plan.id)
        .values(
            attempt=claim.attempt,
            attempt_token=claim.token,
            lease_until=guard.check(),
            updated_at=sa.func.clock_timestamp(),
        )
    )
    c.execute(
        sa.update(versions)
        .where(versions.c.id == task.plan.version_id)
        .values(
            state="EXTRACTING",
            error_code="NONE",
            completed_at=None,
        )
    )
    c.execute(
        sa.insert(audit).values(
            id=uuid4(),
            principal_id=task.plan.actor_id,
            repository_id=task.plan.repository_id,
            target_id=task.plan.version_id,
            request_id=claim.id,
            action="INGESTION_STARTED",
            outcome="OK",
        )
    )
    return task


def _current(c, guard):
    task, intent = _task(c, guard)
    if intent.attempt != guard.claim.attempt or intent.attempt_token != guard.claim.token:
        raise ClaimExpired()
    if task.version.state not in FINAL and task.version.state != "EXTRACTING":
        raise journal.IngestionError("STATE_CONFLICT")
    return task


def _empty(c, task):
    for table in (blocks, chunks):
        if c.scalar(
            sa.select(sa.func.count())
            .select_from(table)
            .where(table.c.version_id == task.plan.version_id)
        ):
            raise journal.IngestionError("STATE_CONFLICT")


def complete(c, guard, extraction):
    task = _current(c, guard)
    if task.version.state == "READY_FOR_EMBEDDING":
        return False
    if task.version.state in FINAL:
        raise journal.IngestionError("STATE_CONFLICT")
    if not isinstance(extraction, Extraction) or extraction.parser != task.version.parser_id:
        raise journal.IngestionError("INPUT_INVALID")
    result = make_chunks(extraction, task.config)
    if not result:
        raise journal.IngestionError("STATE_CONFLICT")
    _empty(c, task)
    plan = task.plan
    c.execute(sa.update(versions).where(versions.c.id == plan.version_id).values(state="CHUNKING"))
    c.execute(
        sa.insert(blocks),
        [
            {
                "version_id": plan.version_id,
                "document_id": plan.document_id,
                "repository_id": plan.repository_id,
                "ordinal": b.ordinal,
                "start_offset": b.start,
                "end_offset": b.end,
                "text": b.text,
                "page": b.page,
                "section": list(b.section),
                "kind": b.kind,
            }
            for b in extraction.blocks
        ],
    )
    c.execute(
        sa.insert(chunks),
        [
            {
                "id": uuid5(plan.version_id, "F04/chunk/v1:" + str(item.ordinal)),
                "version_id": plan.version_id,
                "document_id": plan.document_id,
                "repository_id": plan.repository_id,
                "ordinal": item.ordinal,
                "block_ordinal": item.block_ordinal,
                "block_start": extraction.blocks[item.block_ordinal].start,
                "block_end": extraction.blocks[item.block_ordinal].end,
                "start_offset": item.start,
                "end_offset": item.end,
                "text": item.text,
                "content_hash": item.content_hash,
                "page": item.page,
                "section": list(item.section),
                "kind": item.kind,
            }
            for item in result
        ],
    )
    c.execute(
        sa.update(versions)
        .where(versions.c.id == plan.version_id)
        .values(
            state="READY_FOR_EMBEDDING",
            normalized_hash=hashlib.sha256(extraction.text.encode()).hexdigest(),
            character_count=len(extraction.text),
            page_count=extraction.page_count,
            block_count=len(extraction.blocks),
            chunk_count=len(result),
            error_code="NONE",
            completed_at=sa.func.clock_timestamp(),
        )
    )
    c.execute(
        sa.insert(audit).values(
            id=uuid4(),
            principal_id=plan.actor_id,
            repository_id=plan.repository_id,
            target_id=plan.version_id,
            request_id=guard.claim.id,
            action="INGESTION_READY",
            outcome="OK",
        )
    )
    c.exec_driver_sql("SET CONSTRAINTS ALL IMMEDIATE")
    c.exec_driver_sql("SET CONSTRAINTS ALL DEFERRED")
    guard.check()
    return True


def failure(c, guard, code, *, retryable=False):
    if (
        not isinstance(code, str)
        or code not in ERRORS
        or code == "NONE"
        or type(retryable) is not bool
    ):
        raise journal.IngestionError("INPUT_INVALID")
    task = _current(c, guard)
    if task.version.state in FINAL:
        return task.version.state
    _empty(c, task)
    state = (
        "FAILED_RETRYABLE"
        if retryable
        else ("NEEDS_OCR" if code == "NEEDS_OCR" else "FAILED_TERMINAL")
    )
    c.execute(
        sa.update(versions)
        .where(versions.c.id == task.plan.version_id)
        .values(
            state=state,
            error_code=code,
            completed_at=None if retryable else sa.func.clock_timestamp(),
        )
    )
    c.execute(
        sa.insert(audit).values(
            id=uuid4(),
            principal_id=task.plan.actor_id,
            repository_id=task.plan.repository_id,
            target_id=task.plan.version_id,
            request_id=guard.claim.id,
            action="INGESTION_FAILED",
            outcome="DENIED",
        )
    )
    guard.check()
    return state
