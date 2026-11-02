"""Scoped EMBED consumer; content is read only with a fresh actor authorization."""

import logging
import time
from contextlib import contextmanager
from threading import Event
from uuid import uuid4

import sqlalchemy as sa

from rag_platform.control.identity import AccessError
from rag_platform.documents.policy import tenant_allows
from rag_platform.embeddings import processing
from rag_platform.embeddings.contracts import EmbeddingError, EmbeddingProfile, inputs, validate
from rag_platform.embeddings.heartbeat import LeasePulse
from rag_platform.embeddings.queue import EmbeddingQueue
from rag_platform.embeddings.queue_schema_f05_0007 import ERRORS, jobs
from rag_platform.ingestion import journal
from rag_platform.ingestion.claims import ClaimExpired, locked_claim
from rag_platform.ingestion.worker_policy import StopRequested, before_commit, policy_guard
from rag_platform.tenancy.resolver import AdministrativeTenant

LOGGER = logging.getLogger("rag_platform.embeddings")


def queue_code(code):
    if isinstance(code, str) and code in ERRORS and code != "NONE":
        return code
    if code == "LIMIT_EXCEEDED":
        return "DEPENDENCY_UNAVAILABLE"
    return "EMBEDDING_FAILED"


class Worker:
    def __init__(self, runtime, queue, provider, *, stop=None, heartbeat_interval=None):
        if (
            runtime.authority.profile != "embedding_publication"
            or not isinstance(queue, EmbeddingQueue)
            or runtime.authority.engine is not queue.engine
            or not queue.scope
            or tuple(queue.scope) != tuple(runtime.scope)
            or not isinstance(provider.profile, EmbeddingProfile)
            or queue.profile_fingerprint != provider.profile.fingerprint()
        ):
            raise ValueError("Explicit publication runtime, provider and EMBED scope required")
        self.runtime, self.queue, self.provider = runtime, queue, provider
        self.profile = provider.profile
        self.stop = Event() if stop is None else stop
        self.heartbeat_interval = heartbeat_interval

    def preflight(self):
        self.runtime.preflight()
        # Version adoption is checked by the migrator deployment controller.
        # Runtime gets no additional grants on the control Alembic table.
        with self.queue.engine.connect() as c:
            c.execute(sa.select(jobs).limit(0))

    def _stage(self, stage, claim):
        """Trusted QA subclasses can stop a real process after a durable boundary."""

    def _emit(self, claim, code):
        LOGGER.info(
            "embedding_job job_id=%s code=%s",
            str(claim.id),
            "NONE" if code == "NONE" else queue_code(code),
        )

    def _authorize(self, claim, trace):
        context = self.runtime.authority.authorize(claim.actor_id, claim.tenant_id, trace)
        if len(context.roles) != 1 or not tenant_allows(context.roles[0], "upload"):
            raise AccessError("ROLE_DENIED")
        return context

    @contextmanager
    def _transaction(self, claim, trace, *, ack=False, stage="METADATA_COMMITTED"):
        self._access()
        context = self._authorize(claim, trace)
        with locked_claim(self.queue, claim) as guard:
            checked = policy_guard(guard, self.runtime.authority, context, trace)
            with self.runtime.repositories.connections.connection(checked, trace) as c:
                with c.begin():
                    if c.dialect.name == "postgresql":
                        c.exec_driver_sql("SET LOCAL lock_timeout='5s'")
                        c.exec_driver_sql("SET LOCAL statement_timeout='15s'")
                    yield c, guard, checked
                    self._access()
                    before_commit(guard, checked, self.stop.is_set)
            self._stage(stage, claim)
            if ack:
                guard.complete()

    def _access(self):
        if not self.runtime.access_ready():
            self.stop.set()
            raise StopRequested()

    def relay(self):
        for tenant in self.queue.scope:
            if self.stop.is_set() or not self.runtime.access_ready():
                self.stop.set()
                return
            try:
                with self.runtime.registry.connection(AdministrativeTenant(tenant), "app") as c:
                    with c.begin():
                        plans = processing.pending(c, profile=self.profile)
                for plan in plans:
                    if self.stop.is_set():
                        return
                    job = processing.enqueue(self.queue, tenant, plan)
                    with self.runtime.registry.connection(AdministrativeTenant(tenant), "app") as c:
                        with c.begin():
                            processing.dispatched(c, plan, job)
            except Exception:
                LOGGER.info("embedding_relay tenant_id=%s code=DEPENDENCY_UNAVAILABLE", str(tenant))

    def _reconcile(self, claim):
        with locked_claim(self.queue, claim) as guard:
            with self.runtime.registry.connection(
                AdministrativeTenant(claim.tenant_id), "app"
            ) as c:
                completed = processing.published(c, guard)
            if completed:
                guard.complete()
                return True
        return False

    def _failure(self, claim, trace, code, retryable):
        code = queue_code(code)
        try:
            with self._transaction(claim, trace, stage="FAILURE_COMMITTED") as (c, guard, _):
                processing.failure(c, guard, self.profile, code)
        except ClaimExpired:
            self._emit(claim, "LEASE_EXHAUSTED")
            return
        except AccessError as error:
            retryable = error.code in {"CATALOG_UNAVAILABLE", "TENANT_UNAVAILABLE"}
            code = "DEPENDENCY_UNAVAILABLE" if retryable else "AUTHORIZATION_CHANGED"
        except journal.IngestionError as error:
            code = queue_code(error.code)
            retryable = False
        except processing.ProcessingError as error:
            code, retryable = queue_code(error.code), False
        except StopRequested:
            code, retryable = "STOP_REQUESTED", True
        except Exception:
            code, retryable = "DEPENDENCY_UNAVAILABLE", True
        self.queue.fail(claim, code, retryable=retryable)
        self._emit(claim, code)

    def step(self):
        if self.stop.is_set() or not self.runtime.access_ready():
            self.stop.set()
            return False
        if self.provider.profile != self.profile:
            raise ValueError("Immutable embedding provider profile changed")
        claim = self.queue.claim()
        if claim is None:
            return False
        trace = uuid4()
        try:
            if self._reconcile(claim):
                return True
            if (
                claim.profile_fingerprint != self.profile.fingerprint()
                or self.provider.profile != self.profile
            ):
                raise EmbeddingError("PROFILE_MISMATCH")
            with self._transaction(claim, trace, stage="START_COMMITTED") as (c, guard, _):
                processing.start(c, guard, self.profile)
            while True:
                if self.stop.is_set():
                    raise StopRequested()
                with self._transaction(claim, trace) as (c, guard, _):
                    task = processing.next_batch(c, guard, self.profile)
                if task is None:
                    with self._transaction(claim, trace, ack=True, stage="RESULT_COMMITTED") as (
                        c,
                        guard,
                        _,
                    ):
                        processing.complete(c, guard, self.profile)
                    self._emit(claim, "NONE")
                    return True
                self._access()
                inputs(self.profile, task.texts, "passage")
                started = time.monotonic()
                with LeasePulse(
                    self.queue, claim, self.stop.is_set, interval=self.heartbeat_interval
                ) as pulse:
                    counts = tuple(
                        self.provider.count_tokens(text, "passage") for text in task.texts
                    )
                    if any(type(n) is not int or n < 1 for n in counts):
                        raise EmbeddingError("INPUT_INVALID")
                    if any(n > self.profile.max_tokens for n in counts):
                        raise EmbeddingError("INPUT_TOO_LONG")
                    if sum(counts) + task.used_tokens > processing.MAX_JOB_TOKENS:
                        raise processing.ProcessingError("QUOTA_EXCEEDED")
                    response = validate(
                        self.profile,
                        task.texts,
                        "passage",
                        self.provider.embed(task.texts, "passage"),
                    )
                    if response.input_tokens != counts:
                        raise EmbeddingError("INPUT_INVALID")
                    pulse.check()
                elapsed = max(0, int((time.monotonic() - started) * 1000))
                self._access()
                self._stage("INFERRED", claim)
                # New context after inference; never reuse the possibly expired read context.
                with self._transaction(claim, trace, stage="BATCH_COMMITTED") as (c, guard, _):
                    processing.save_batch(c, guard, self.profile, task, response, elapsed)
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
            self._failure(claim, trace, error.code, False)
        except processing.ProcessingError as error:
            self._failure(claim, trace, error.code, error.code == "DEPENDENCY_UNAVAILABLE")
        except EmbeddingError as error:
            self._failure(
                claim,
                trace,
                error.code,
                error.code in {"DEPENDENCY_UNAVAILABLE", "LIMIT_EXCEEDED"},
            )
        except Exception:
            self._failure(claim, trace, "DEPENDENCY_UNAVAILABLE", True)
        return True

    def run(self):
        while not self.stop.is_set():
            try:
                if not self.runtime.access_ready():
                    self.stop.set()
                    break
                self.relay()
                if not self.step():
                    self.stop.wait(0.5)
            except Exception:
                LOGGER.info("embedding_poll code=DEPENDENCY_UNAVAILABLE")
                self.stop.wait(1)
