"""One-at-a-time F04 consumer; runtime carries only limited application credentials."""

import logging
from contextlib import contextmanager
from threading import Event
from uuid import uuid4

from rag_platform.control.identity import AccessError
from rag_platform.documents.errors import DocumentError
from rag_platform.documents.policy import tenant_allows
from rag_platform.ingestion import journal, processing
from rag_platform.ingestion.claims import ClaimExpired, locked_claim
from rag_platform.ingestion.extraction import ExtractionError
from rag_platform.ingestion.extractor import extract
from rag_platform.ingestion.queue_schema import ERRORS
from rag_platform.ingestion.worker_policy import StopRequested, before_commit, policy_guard
from rag_platform.tenancy.resolver import AdministrativeTenant

LOGGER = logging.getLogger("rag_platform.ingestion")


def queue_code(code):
    if not isinstance(code, str):
        return "PROCESSING_FAILED"
    if code in ERRORS and code != "NONE":
        return code
    if code in {"PARSER_ENCRYPTED", "PARSER_UNSUPPORTED", "NO_TEXT", "INPUT_INVALID"}:
        return "PARSER_INVALID"
    if code == "SANDBOX_UNAVAILABLE":
        return "DEPENDENCY_UNAVAILABLE"
    return "PROCESSING_FAILED"


class Worker:
    def __init__(self, runtime, queue, *, stop=None, extractor=extract):
        if (
            getattr(queue, "_kind", None) != "INGEST"
            or runtime.authority.profile not in ("ingestion", "embeddings", "embedding_publication")
            or runtime.authority.engine is not queue.engine
            or not queue.scope
            or tuple(queue.scope) != tuple(runtime.scope)
        ):
            raise ValueError("Explicit ingestion runtime and tenant scope required")
        self.runtime, self.queue = runtime, queue
        self.stop = Event() if stop is None else stop
        self.extractor = extractor

    def _stage(self, stage, claim):
        """Trusted test subclasses can stop a real process at durable boundaries."""

    def _emit(self, claim, code):
        LOGGER.info(
            "ingestion_job job_id=%s code=%s",
            str(claim.id),
            "NONE" if code == "NONE" else queue_code(code),
        )

    def relay(self):
        # Fixed service scope plus catalog/limited AppRole, only ops intent IDs.
        # No content read or acting as its original user at this boundary.
        for tenant in self.queue.scope:
            if self.stop.is_set():
                return
            try:
                with self.runtime.registry.connection(AdministrativeTenant(tenant), "app") as c:
                    plans = journal.pending(c)
                for plan in plans:
                    if self.stop.is_set():
                        return
                    job = journal.enqueue(self.queue, tenant, plan)
                    with self.runtime.registry.connection(AdministrativeTenant(tenant), "app") as c:
                        with c.begin():
                            journal.dispatched(c, plan, job)
            except Exception:
                LOGGER.info("ingestion_relay tenant_id=%s code=DEPENDENCY_UNAVAILABLE", str(tenant))

    def _authorize(self, claim, trace):
        context = self.runtime.authority.authorize(claim.actor_id, claim.tenant_id, trace)
        if len(context.roles) != 1 or not tenant_allows(context.roles[0], "upload"):
            raise AccessError("ROLE_DENIED")
        return context

    @contextmanager
    def _transaction(self, claim, trace, *, ack=False, stage="METADATA_COMMITTED"):
        context = self._authorize(claim, trace)
        with locked_claim(self.queue, claim) as guard:
            checked = policy_guard(guard, self.runtime.authority, context, trace)
            connections = self.runtime.repositories.connections
            with connections.connection(checked, trace) as c:
                with c.begin():
                    c.exec_driver_sql("SET LOCAL lock_timeout='5s'")
                    c.exec_driver_sql("SET LOCAL statement_timeout='15s'")
                    yield c, guard, checked
                    before_commit(guard, checked, self.stop.is_set)
            # Tenant has committed. A crash/ack loss here is reconciled, not replayed.
            self._stage(stage, claim)
            if ack:
                guard.complete()

    def _reconcile(self, claim):
        # Inspect only immutable outcome metadata of a previously authorized result.
        # Never fetch text or perform new content work under the relay identity.
        with locked_claim(self.queue, claim) as guard:
            with self.runtime.registry.connection(
                AdministrativeTenant(claim.tenant_id), "app"
            ) as c:
                row = processing.inspect(c, guard)
            if row.state in ("READY_FOR_EMBEDDING", "PUBLISHED"):
                guard.complete()
                return True
            terminal = row.state in processing.FINAL
            code = row.error_code
        if terminal:
            self.queue.fail(claim, queue_code(code))
            return True
        return False

    def _record_failure(self, claim, trace, code, retryable):
        retry = retryable
        try:
            with self._transaction(claim, trace, stage="FAILURE_COMMITTED") as (c, guard, _checked):
                retry = retryable and claim.attempt < guard.max_attempts
                processing.failure(c, guard, code, retryable=retry)
        except ClaimExpired:
            self.queue.fail(claim, "DEPENDENCY_UNAVAILABLE", retryable=True)
            return
        except AccessError as error:
            retry = error.code in {"CATALOG_UNAVAILABLE", "TENANT_UNAVAILABLE"}
            code = "DEPENDENCY_UNAVAILABLE" if retry else "AUTHORIZATION_CHANGED"
        except journal.IngestionError as error:
            code = (
                error.code
                if error.code in {"TOMBSTONED", "AUTHORIZATION_CHANGED"}
                else "PROCESSING_FAILED"
            )
            retry = False
        except StopRequested:
            code, retry = "STOP_REQUESTED", True
        except Exception:
            code, retry = "DEPENDENCY_UNAVAILABLE", True
        self.queue.fail(claim, queue_code(code), retryable=retry)
        self._emit(claim, code)

    def step(self):
        if self.stop.is_set():
            return False
        claim = self.queue.claim()
        if claim is None:
            return False
        trace = uuid4()
        try:
            if self.stop.is_set():
                raise StopRequested()
            if self._reconcile(claim):
                return True
            with self._transaction(claim, trace, stage="START_COMMITTED") as (c, guard, _checked):
                task = processing.start(c, guard)
            self._stage("STARTED", claim)
            if task.version.state in processing.FINAL:
                self._reconcile(claim)
                return True
            if self.stop.is_set():
                raise StopRequested()
            if not self.queue.heartbeat(claim):
                raise ClaimExpired()
            context = self._authorize(claim, trace)
            download = self.runtime.documents.original(
                context, trace, task.plan.repository_id, task.plan.document_id
            )
            try:
                if download.file.content_hash != task.original.content_hash:
                    raise journal.IngestionError("STATE_CONFLICT")
                if self.stop.is_set():
                    raise StopRequested()
                if not self.queue.heartbeat(claim):
                    raise ClaimExpired()
                result = self.extractor(
                    download.file.file,
                    task.original.mime,
                    expected_size=task.original.byte_size,
                    expected_hash=task.original.content_hash,
                )
            finally:
                download.close()
            self._stage("PARSED", claim)
            if self.stop.is_set():
                raise StopRequested()
            if not self.queue.heartbeat(claim):
                raise ClaimExpired()
            with self._transaction(claim, trace, ack=True, stage="RESULT_COMMITTED") as (
                c,
                guard,
                _checked,
            ):
                processing.complete(c, guard, result)
                if self.runtime.authority.profile == "embedding_publication":
                    from rag_platform.embeddings import processing as embedding_processing
                    from rag_platform.embeddings.qwen import qwen_profile

                    embedding_processing.request(
                        c,
                        claim.actor_id,
                        task.plan.repository_id,
                        claim.document_id,
                        claim.version_id,
                        qwen_profile(),
                    )
            self._emit(claim, "NONE")
        except ClaimExpired:
            self._emit(claim, "LEASE_EXHAUSTED")
        except StopRequested:
            self.queue.fail(claim, "STOP_REQUESTED", retryable=True)
            self._emit(claim, "STOP_REQUESTED")
        except AccessError as error:
            retry = error.code in {"CATALOG_UNAVAILABLE", "TENANT_UNAVAILABLE"}
            code = "DEPENDENCY_UNAVAILABLE" if retry else "AUTHORIZATION_CHANGED"
            self.queue.fail(claim, code, retryable=retry)
            self._emit(claim, code)
        except journal.IngestionError as error:
            code = (
                error.code
                if error.code in {"TOMBSTONED", "AUTHORIZATION_CHANGED"}
                else "PROCESSING_FAILED"
            )
            self._record_failure(claim, trace, code, False)
        except ExtractionError as error:
            code = error.code
            if code == "INPUT_INVALID":
                code = "PARSER_INVALID"
            self._record_failure(claim, trace, code, code == "SANDBOX_UNAVAILABLE")
        except DocumentError as error:
            if error.code in {"ROLE_DENIED", "NOT_FOUND"}:
                self.queue.fail(claim, "AUTHORIZATION_CHANGED")
            else:
                self._record_failure(claim, trace, "DEPENDENCY_UNAVAILABLE", True)
        except Exception:
            self._record_failure(claim, trace, "DEPENDENCY_UNAVAILABLE", True)
        return True

    def run(self):
        while not self.stop.is_set():
            try:
                self.relay()
                if not self.step():
                    self.stop.wait(0.5)
            except Exception:
                LOGGER.info("ingestion_poll code=DEPENDENCY_UNAVAILABLE")
                self.stop.wait(1)
