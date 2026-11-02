"""Real SQLite transactions/authority; PostgreSQL guards and locking have separate QA."""

import hashlib
import math
import time
from contextlib import contextmanager
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4, uuid5

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Session

from rag_platform.control.identity_models import IdentityBase, Membership, TenantProfile, User
from rag_platform.control.models import Base, DbLocation, Instance, StorageLocation, Tenant
from rag_platform.embeddings import processing
from rag_platform.embeddings.contracts import EmbeddingError
from rag_platform.embeddings.fixture import DeterministicFixture, fixture_profile
from rag_platform.embeddings.publication_schema_f05_0006 import build_metadata
from rag_platform.embeddings.queue import EmbeddingQueue
from rag_platform.embeddings.queue_schema_f05_0007 import jobs
from rag_platform.embeddings.space_ddl import vector_table
from rag_platform.embeddings.worker import Worker
from rag_platform.ingestion.extraction import (
    CHUNKER,
    NORMALIZER,
    PARSERS,
    ChunkConfig,
    from_wire,
)
from rag_platform.ingestion.extraction import (
    chunks as make_chunks,
)
from rag_platform.tenancy.authorization import TenantAuthorizer
from rag_platform.tenancy.resolver import AdministrativeTenant


class UUIDList(sa.TypeDecorator):
    impl = sa.JSON
    cache_ok = True

    def process_bind_param(self, value, _dialect):
        return [str(v) for v in value]

    def process_result_value(self, value, _dialect):
        return [UUID(v) for v in value]


class Provider:
    def __init__(self, profile, engine):
        self.profile, self.engine = profile, engine
        self.base = DeterministicFixture(profile)
        self.calls = []
        self.callback = None

    def count_tokens(self, text, kind):
        return self.base.count_tokens(text, kind)

    def embed(self, texts, kind):
        # Tenant transactions must have ended before any potentially long inference.
        assert self.engine.pool.checkedout() == 0
        self.calls.append(tuple(texts))
        if self.callback is not None:
            response = self.callback(texts)
            if response is not None:
                return response
        return self.base.embed(texts, kind)


@pytest.fixture
def setup(tmp_path, monkeypatch, request):
    control = sa.create_engine("sqlite:///" + str(tmp_path / "control.db"))
    with control.connect() as c:
        c.exec_driver_sql("PRAGMA journal_mode=WAL")
    Base.metadata.create_all(control)
    IdentityBase.metadata.create_all(control)
    jobs.create(control)
    tenant, actor, instance, repo, doc, raw, version, source, space = (uuid4() for _ in range(9))
    with Session(control) as s, s.begin():
        s.add(
            Instance(
                id=instance,
                host="postgres",
                port=5432,
                admin_secret_ref=uuid4(),
                admin_secret_version=1,
            )
        )
        s.add(
            Tenant(
                id=tenant,
                state="READY",
                migration_state="READY",
                desired_version="f05_tenant_0006",
                observed_version="f05_tenant_0006",
            )
        )
        s.add(User(id=actor, issuer="https://synthetic.invalid", oidc_subject=str(actor)))
        s.flush()
        s.add(TenantProfile(tenant_id=tenant, kind="ORG"))
        s.add(Membership(user_id=actor, tenant_id=tenant, role="editor"))
        s.add(
            DbLocation(
                tenant_id=tenant,
                instance_id=instance,
                db_name="rag_t_" + tenant.hex,
                app_secret_ref=uuid4(),
                app_secret_version=1,
                readonly_secret_ref=uuid4(),
                readonly_secret_version=1,
                migrator_secret_ref=uuid4(),
                migrator_secret_version=1,
            )
        )
        s.add(
            StorageLocation(
                tenant_id=tenant,
                endpoint="https://synthetic.invalid",
                bucket="synthetic-" + tenant.hex,
                credential_ref=uuid4(),
                credential_version=1,
            )
        )
    engine = sa.create_engine("sqlite:///" + str(tmp_path / "tenant.db"))

    @sa.event.listens_for(engine, "connect")
    def attach(connection, _):
        for schema in ("knowledge", "security", "ops"):
            connection.execute(
                "ATTACH DATABASE ? AS " + schema, (str(tmp_path / (schema + ".db")),)
            )

    profile = fixture_profile(max_tokens=64, max_batch=2)
    md = build_metadata()
    vector = vector_table(md, space, profile)
    # SQLite proves application transactions/recovery, not PostgreSQL DDL guards.
    # All PostgreSQL check/trigger semantics are tested by the opt-in SQL probe.
    for table in md.tables.values():
        for constraint in tuple(table.constraints):
            if isinstance(constraint, sa.CheckConstraint):
                table.constraints.remove(constraint)
        for column in table.c:
            if isinstance(column.type, ARRAY):
                column.type = UUIDList()
            elif isinstance(column.type, JSONB):
                column.type = sa.JSON()
            if column.server_default is not None and "::jsonb" in str(column.server_default.arg):
                column.server_default = sa.DefaultClause(
                    sa.text(str(column.server_default.arg).replace("::jsonb", ""))
                )
    md.create_all(engine)
    for name in (
        "intents",
        "batches",
        "publications",
        "spaces",
        "versions",
        "documents",
        "chunks",
        "audit",
    ):
        key = {
            "intents": "ops.embedding_intents",
            "batches": "ops.embedding_batches",
            "publications": "knowledge.embedding_publications",
            "spaces": "knowledge.embedding_spaces",
            "versions": "knowledge.document_versions",
            "documents": "knowledge.documents",
            "chunks": "knowledge.chunks",
            "audit": "ops.audit_events",
        }[name]
        monkeypatch.setattr(processing, name, md.tables[key])
    text = (
        "PRIVATE_EMBED_FIXTURE documento con datos sintéticos para pruebas. "
        * getattr(request, "param", {}).get("repeats", 8)
    ).strip()
    data = from_wire(
        {
            "version": 1,
            "parser": PARSERS["text/plain"],
            "normalizer": NORMALIZER,
            "page_count": None,
            "blocks": [{"text": text, "page": None, "section": [], "kind": "text"}],
        },
        "text/plain",
    )
    config = ChunkConfig(128, 32)
    made = make_chunks(data, config)
    with engine.begin() as c:
        c.execute(
            md.tables["knowledge.repositories"]
            .insert()
            .values(
                id=repo,
                name="Synthetic worker",
                owner_id=actor,
                config={"language": "auto"},
            )
        )
        c.execute(
            md.tables["security.repository_acl"]
            .insert()
            .values(
                repository_id=repo,
                principal_id=actor,
                role="owner",
            )
        )
        c.execute(
            md.tables["knowledge.sources"]
            .insert()
            .values(
                id=source,
                repository_id=repo,
                created_by=actor,
            )
        )
        c.execute(
            processing.documents.insert().values(
                id=doc,
                repository_id=repo,
                source_id=source,
                current_version_id=raw,
                original_version_id=raw,
                created_by=actor,
            )
        )
        common = dict(
            document_id=doc,
            repository_id=repo,
            filename="fixture.txt",
            mime="text/plain",
            byte_size=len(text),
            content_hash=hashlib.sha256(text.encode()).hexdigest(),
        )
        c.execute(
            processing.versions.insert().values(
                **common,
                id=raw,
                blob_key="f03/" + repo.hex + "/" + raw.hex,
            )
        )
        c.execute(
            processing.versions.insert().values(
                **common,
                id=version,
                kind="PROCESSED",
                original_version_id=raw,
                blob_key=None,
                processing_actor_id=actor,
                parser_id=PARSERS["text/plain"],
                normalizer_id=NORMALIZER,
                chunker_id=CHUNKER,
                config_hash=config.fingerprint("text/plain"),
                chunk_size=config.size,
                chunk_overlap=config.overlap,
                state="READY_FOR_EMBEDDING",
                normalized_hash=hashlib.sha256(data.text.encode()).hexdigest(),
                character_count=len(data.text),
                block_count=len(data.blocks),
                chunk_count=len(made),
                completed_at=datetime.now(UTC),
            )
        )
        for b in data.blocks:
            c.execute(
                md.tables["knowledge.extracted_blocks"]
                .insert()
                .values(
                    version_id=version,
                    document_id=doc,
                    repository_id=repo,
                    ordinal=b.ordinal,
                    start_offset=b.start,
                    end_offset=b.end,
                    text=b.text,
                    page=b.page,
                    section=list(b.section),
                    kind=b.kind,
                )
            )
        for item in made:
            block = data.blocks[item.block_ordinal]
            c.execute(
                processing.chunks.insert().values(
                    id=uuid5(version, str(item.ordinal)),
                    version_id=version,
                    document_id=doc,
                    repository_id=repo,
                    ordinal=item.ordinal,
                    block_ordinal=item.block_ordinal,
                    block_start=block.start,
                    block_end=block.end,
                    start_offset=item.start,
                    end_offset=item.end,
                    text=item.text,
                    content_hash=item.content_hash,
                    page=item.page,
                    section=list(item.section),
                    kind=item.kind,
                )
            )
        c.execute(
            processing.spaces.insert().values(
                **asdict(profile),
                id=space,
                profile_fingerprint=profile.fingerprint(),
            )
        )
    if getattr(request, "param", {}).get("request_embedding", True):
        with engine.begin() as c:
            processing.request(c, actor, repo, doc, version, profile)
    authority = TenantAuthorizer(control, b"k" * 32, profile="embedding_publication")

    @contextmanager
    def authorized(context, trace):
        checked = authority.validate(context, trace)
        assert checked.tenant_id == tenant
        with engine.connect() as c:
            yield c

    @contextmanager
    def administrative(context, kind):
        assert (
            isinstance(context, AdministrativeTenant)
            and context.tenant_id == tenant
            and kind == "app"
        )
        with engine.connect() as c:
            yield c

    runtime = SimpleNamespace(
        authority=authority,
        scope=(tenant,),
        repositories=SimpleNamespace(connections=SimpleNamespace(connection=authorized)),
        registry=SimpleNamespace(connection=administrative),
        preflight=lambda: None,
        access_ready=lambda: True,
    )
    queue = EmbeddingQueue(
        control,
        tenant_scope=(tenant,),
        lease_seconds=180,
        max_attempts=3,
        profile_fingerprint=profile.fingerprint(),
    )
    provider = Provider(profile, engine)
    worker = Worker(runtime, queue, provider)
    worker.preflight()
    worker.relay()
    yield SimpleNamespace(
        engine=engine,
        control=control,
        queue=queue,
        provider=provider,
        worker=worker,
        runtime=runtime,
        actor=actor,
        tenant=tenant,
        repo=repo,
        doc=doc,
        raw=raw,
        version=version,
        vector=vector,
        chunks=len(made),
        requests=math.ceil(len(made) / profile.max_batch),
        md=md,
    )
    engine.dispose()
    control.dispose()


def count(s, table):
    with s.engine.connect() as c:
        return c.scalar(sa.select(sa.func.count()).select_from(table))


def state(s):
    with s.control.connect() as c:
        return c.execute(sa.select(jobs)).mappings().one()


def retry(s):
    with s.control.begin() as c:
        c.execute(jobs.update().values(available_at=datetime.now(UTC) - timedelta(seconds=5)))


def expire(s):
    with s.control.begin() as c:
        c.execute(jobs.update().values(lease_until=datetime.now(UTC) - timedelta(seconds=5)))


def test_worker_batches_real_transactions_and_publishes_once(setup):
    s = setup
    assert s.worker.step()
    assert state(s)["status"] == "SUCCEEDED"
    assert len(s.provider.calls) == s.requests
    assert count(s, s.vector) == s.chunks
    assert count(s, processing.batches) == s.requests
    assert count(s, processing.publications) == 1
    with s.engine.connect() as c:
        doc = c.execute(sa.select(processing.documents)).mappings().one()
        assert doc["current_version_id"] == s.version and doc["original_version_id"] == s.raw
    s.worker.relay()
    assert not s.worker.step() and len(s.provider.calls) == s.requests


class InjectedCrash(BaseException):
    pass


@pytest.mark.parametrize("stage", ["BATCH_COMMITTED", "RESULT_COMMITTED"])
def test_crash_resume_skips_persisted_inference_and_reconciles_ack(setup, stage):
    s = setup

    class Crash(Worker):
        def _stage(self, current, _claim):
            if current == stage:
                raise InjectedCrash()

    worker = Crash(s.runtime, s.queue, s.provider)
    with pytest.raises(InjectedCrash):
        worker.step()
    previous = len(s.provider.calls)
    if stage == "RESULT_COMMITTED":
        with Session(s.control) as session, session.begin():
            session.get(Membership, (s.actor, s.tenant)).state = "REVOKED"
    expire(s)
    assert s.worker.step()
    assert state(s)["status"] == "SUCCEEDED"
    assert len(s.provider.calls) == s.requests
    if stage == "RESULT_COMMITTED":
        assert len(s.provider.calls) == previous
    assert count(s, s.vector) == s.chunks


@pytest.mark.parametrize("revocation", ["acl", "membership", "tombstone"])
def test_revocation_during_inference_prevents_late_persistence(setup, revocation):
    s = setup

    def revoke(_texts):
        if revocation == "membership":
            with Session(s.control) as session, session.begin():
                session.get(Membership, (s.actor, s.tenant)).state = "REVOKED"
        else:
            with s.engine.begin() as c:
                if revocation == "acl":
                    c.execute(s.md.tables["security.repository_acl"].delete())
                else:
                    c.execute(
                        processing.documents.update().values(
                            state="TOMBSTONED",
                            tombstoned_at=datetime.now(UTC),
                            tombstoned_by=s.actor,
                        )
                    )

    s.provider.callback = revoke
    assert s.worker.step()
    assert state(s)["status"] == "FAILED"
    assert (
        count(s, s.vector) == count(s, processing.batches) == count(s, processing.publications) == 0
    )


def test_expired_read_context_is_reauthorized_after_inference(setup, monkeypatch):
    s = setup
    clock = [time.time()]
    monkeypatch.setattr(time, "time", lambda: clock[0])
    s.provider.callback = lambda _texts: clock.__setitem__(0, clock[0] + 31)
    assert s.worker.step()
    assert state(s)["status"] == "SUCCEEDED"
    assert count(s, s.vector) == s.chunks


def test_expired_control_lease_cannot_commit_inferred_result(setup):
    s = setup
    s.provider.callback = lambda _texts: expire(s)
    assert s.worker.step()
    assert state(s)["status"] == "RUNNING"
    assert count(s, s.vector) == count(s, processing.batches) == 0


def test_batch_write_failure_rolls_back_vectors_and_usage_together(setup):
    s = setup
    fail = [True]

    @sa.event.listens_for(s.engine, "before_cursor_execute")
    def interrupt(_c, _cursor, statement, _params, _context, _many):
        if fail[0] and statement.startswith("INSERT INTO ops.embedding_batches"):
            raise RuntimeError("PRIVATE_EMBED_FIXTURE injected write failure")

    assert s.worker.step()
    assert state(s)["status"] == "RETRY"
    assert count(s, s.vector) == count(s, processing.batches) == 0
    fail[0] = False
    retry(s)
    assert s.worker.step()
    assert state(s)["status"] == "SUCCEEDED"
    assert len(s.provider.calls) == s.requests + 1


@pytest.mark.parametrize("bad", ["dimension", "nan", "profile", "tokens"])
def test_invalid_provider_output_is_terminal_and_private(setup, caplog, bad):
    s = setup

    def invalid(texts):
        batch = s.provider.base.embed(texts, "passage")
        if bad == "dimension":
            return replace(batch, vectors=tuple((1.0,) for _ in texts))
        if bad == "nan":
            return replace(batch, vectors=tuple((float("nan"), 0.0, 1.0) for _ in texts))
        if bad == "profile":
            return replace(batch, profile_fingerprint="0" * 64)
        return replace(batch, input_tokens=tuple(1 for _ in texts))

    s.provider.callback = invalid
    assert s.worker.step()
    assert state(s)["status"] == "FAILED"
    assert count(s, s.vector) == count(s, processing.batches) == 0
    assert "PRIVATE_EMBED_FIXTURE" not in caplog.text


def test_dependency_retry_preserves_partial_batches_without_publication(setup):
    s = setup
    failed = [False]

    def unavailable(_texts):
        if len(s.provider.calls) == 2 and not failed[0]:
            failed[0] = True
            raise EmbeddingError("DEPENDENCY_UNAVAILABLE")

    s.provider.callback = unavailable
    assert s.worker.step()
    assert state(s)["status"] == "RETRY"
    assert count(s, processing.batches) == 1
    assert count(s, processing.publications) == 0
    retry(s)
    assert s.worker.step()
    assert state(s)["status"] == "SUCCEEDED"
    assert len(s.provider.calls) == s.requests + 1


def test_stop_during_inference_retains_no_uncommitted_vectors(setup):
    s = setup
    s.provider.callback = lambda _texts: s.worker.stop.set()
    assert s.worker.step()
    assert state(s)["status"] == "RETRY" and state(s)["error_code"] == "STOP_REQUESTED"
    assert count(s, s.vector) == count(s, processing.batches) == 0


def test_oversized_input_is_terminal_before_provider_request(setup):
    s = setup
    s.provider.count_tokens = lambda *_: s.provider.profile.max_tokens + 1
    assert s.worker.step()
    assert state(s)["status"] == "FAILED" and state(s)["error_code"] == "INPUT_TOO_LONG"
    assert not s.provider.calls and count(s, s.vector) == 0


def test_other_model_provider_cannot_process_same_dimension_space(setup):
    s = setup
    s.provider.profile = replace(s.provider.profile, query_prefix="different query: ")
    with pytest.raises(ValueError, match="Immutable embedding provider"):
        s.worker.step()
    assert state(s)["status"] == "PENDING"
    assert not s.provider.calls and count(s, s.vector) == 0


def test_raw_provider_exception_is_closed_in_control_and_logs(setup, caplog):
    import logging

    s = setup
    caplog.set_level(logging.INFO, logger="rag_platform.embeddings")

    def private(_texts):
        raise RuntimeError("PRIVATE_EMBED_FIXTURE supplier text and secret")

    s.provider.callback = private
    assert s.worker.step()
    assert state(s)["status"] == "RETRY"
    assert state(s)["error_code"] == "DEPENDENCY_UNAVAILABLE"
    assert "embedding_job" in caplog.text
    assert "PRIVATE_EMBED_FIXTURE" not in caplog.text and "supplier text" not in caplog.text


def test_wrong_runtime_or_broader_scope_is_rejected_before_claim(setup):
    s = setup
    s.runtime.authority.profile = "embeddings"
    with pytest.raises(ValueError, match="Explicit publication runtime"):
        Worker(s.runtime, s.queue, s.provider)
    assert state(s)["status"] == "PENDING"

    s.runtime.authority.profile = "embedding_publication"
    s.runtime.scope = (s.tenant, uuid4())
    with pytest.raises(ValueError, match="Explicit publication runtime"):
        Worker(s.runtime, s.queue, s.provider)
    assert state(s)["status"] == "PENDING"


@pytest.mark.parametrize("setup", [{"repeats": 120}], indirect=True)
def test_job_chunk_quota_fails_before_model_cost(setup):
    s = setup
    assert s.chunks > processing.MAX_JOB_CHUNKS
    assert s.worker.step()
    assert state(s)["status"] == "FAILED" and state(s)["error_code"] == "QUOTA_EXCEEDED"
    assert not s.provider.calls and count(s, s.vector) == 0


@pytest.mark.parametrize("setup", [{"request_embedding": False}], indirect=True)
def test_old_ready_history_requires_explicit_embedding_request(setup):
    s = setup
    assert not s.worker.step()
    assert not s.provider.calls
    with s.engine.begin() as c:
        plan = processing.request(c, s.actor, s.repo, s.doc, s.version, s.provider.profile)
        assert processing.request(c, s.actor, s.repo, s.doc, s.version, s.provider.profile) == plan
    s.worker.relay()
    assert s.worker.step()
    assert state(s)["status"] == "SUCCEEDED"


def test_worker_leaves_other_model_envelopes_pending(setup):
    s = setup
    other_queue = EmbeddingQueue(s.control, tenant_scope=(s.tenant,))
    other = other_queue.enqueue(s.tenant, s.actor, uuid4(), uuid4(), uuid4(), uuid4(), "0" * 64)
    assert s.worker.step()
    assert not s.worker.step()
    with s.control.connect() as c:
        assert c.scalar(sa.select(jobs.c.status).where(jobs.c.id == other)) == "PENDING"


def test_inferred_text_must_match_immutable_chunk_hashes(setup):
    s = setup
    claim, trace = s.queue.claim(), uuid4()
    with s.worker._transaction(claim, trace) as (c, guard, _):
        processing.start(c, guard, s.provider.profile)
        task = processing.next_batch(c, guard, s.provider.profile)
    forged = replace(task, texts=("different private input", *task.texts[1:]))
    response = s.provider.base.embed(forged.texts, "passage")
    with pytest.raises(processing.ProcessingError, match="STATE_CONFLICT"):
        with s.worker._transaction(claim, trace) as (c, guard, _):
            processing.save_batch(c, guard, s.provider.profile, forged, response, 1)
    assert count(s, s.vector) == count(s, processing.batches) == 0


def test_expiring_access_stops_before_claim_without_spending_attempt(setup):
    s = setup
    s.runtime.access_ready = lambda: False
    assert not s.worker.step()
    assert s.worker.stop.is_set() and state(s)["status"] == "PENDING"
    assert state(s)["attempts"] == 0 and not s.provider.calls


def test_access_window_closes_during_inference_and_resume_uses_new_delivery(setup):
    s = setup
    s.provider.callback = lambda _texts: setattr(s.runtime, "access_ready", lambda: False)
    assert s.worker.step()
    assert s.worker.stop.is_set() and state(s)["status"] == "RETRY"
    assert state(s)["error_code"] == "STOP_REQUESTED" and count(s, s.vector) == 0
    assert not s.worker.step()
    s.runtime.access_ready = lambda: True
    s.provider.callback = None
    retry(s)
    assert Worker(s.runtime, s.queue, s.provider).step()
    assert state(s)["status"] == "SUCCEEDED"
