"""Synthetic publication SQL proof on F05 fixtures; all DDL/data rolled back."""

import json
import logging
import re
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import sqlalchemy as sa
from f02_common import credential, engine
from f04_schema_check import complete, fingerprint, fixture, role, stage
from sqlalchemy.pool import NullPool

from rag_platform.control.identity_models import IdentityBase
from rag_platform.control.models import Base, DbLocation, Instance, ProvisioningOperation, Tenant
from rag_platform.documents.content import selection
from rag_platform.documents.receipt import document_view
from rag_platform.documents.schema import documents
from rag_platform.embeddings.publication_migrations import (
    apply_publication,
    register_publication_space,
)
from rag_platform.embeddings.publication_schema_f05_0006 import VERSION, build_metadata
from rag_platform.embeddings.qwen import qwen_profile
from rag_platform.embeddings.space_ddl import table_name
from rag_platform.identity_api import private_file
from rag_platform.ingestion import journal
from rag_platform.ingestion.logging_setup import local_private_logging
from rag_platform.ingestion.schema import audit, versions
from rag_platform.ingestion.schema_f04_0003 import build_metadata as historical
from rag_platform.providers.secrets import Credential
from rag_platform.provisioning.postgres import Names, Target

ROOT = Path(__file__).resolve().parents[1]
CA = Path("/run/f01-ca.crt")
PHASE = "START"


metadata = build_metadata()
intents = metadata.tables["ops.embedding_intents"]
batches = metadata.tables["ops.embedding_batches"]
publications = metadata.tables["knowledge.embedding_publications"]


class ProbeDenial(RuntimeError):
    def __init__(self, state):
        self.sqlstate = state
        super().__init__("WRONG_SQL_DENIAL")


def denied(c, statement, expected="23514"):
    try:
        with c.begin_nested():
            statement() if callable(statement) else c.execute(statement)
    except sa.exc.DBAPIError as error:
        state = getattr(error.orig, "sqlstate", None)
        if state != expected:
            raise ProbeDenial(state) from None
    else:
        raise RuntimeError("UNEXPECTED_SQL_SUCCESS")


def worker_tenant_proof(c, names):
    global PHASE
    from datetime import UTC, datetime, timedelta

    from rag_platform.embeddings import processing as worker_processing
    from rag_platform.embeddings.fixture import DeterministicFixture, fixture_profile
    from rag_platform.embeddings.queue import EmbeddingClaim

    PHASE = "WORKER_TENANT_COMPONENT"
    with c.begin_nested() as synthetic:
        profile = fixture_profile(max_tokens=64, max_batch=2)
        space = uuid4()
        role(c, names, "owner")
        register_publication_space(c, names, space, profile)
        role(c, names, "app")
        f = fixture(c)
        version, _config, data, rows = stage(c, f)
        c.execute(complete(version, data, rows))
        c.execute(
            sa.insert(audit).values(
                id=uuid4(),
                principal_id=f["actor"],
                repository_id=f["repo"],
                target_id=version,
                request_id=uuid4(),
                action="INGESTION_READY",
                outcome="OK",
            )
        )
        c.exec_driver_sql("SET CONSTRAINTS ALL IMMEDIATE")
        c.exec_driver_sql("SET CONSTRAINTS ALL DEFERRED")
        plan = worker_processing.request(c, f["actor"], f["repo"], f["doc"], version, profile)
        assert (
            worker_processing.request(c, f["actor"], f["repo"], f["doc"], version, profile) == plan
        )
        assert plan in worker_processing.pending(c, profile=profile)
        assert plan not in worker_processing.pending(c, profile=qwen_profile())
        claim = EmbeddingClaim(
            uuid4(),
            names.tenant,
            f["actor"],
            f["doc"],
            version,
            1,
            uuid4(),
            space,
            profile.fingerprint(),
        )
        # Component probe only: actual control fencing is covered separately.
        guard = SimpleNamespace(
            claim=claim,
            intent_id=plan.id,
            check=lambda: datetime.now(UTC) + timedelta(seconds=180),
        )
        worker_processing.start(c, guard, profile)
        provider = DeterministicFixture(profile)
        requests = 0
        while True:
            task = worker_processing.next_batch(c, guard, profile)
            if task is None:
                break
            response = provider.embed(task.texts, "passage")
            worker_processing.save_batch(c, guard, profile, task, response, 1)
            requests += 1
        worker_processing.complete(c, guard, profile)
        assert worker_processing.published(c, guard)
        assert worker_processing.dispatched(c, plan, claim.id)
        assert not worker_processing.dispatched(c, plan, claim.id)
        assert (
            c.scalar(
                sa.select(sa.func.count())
                .select_from(worker_processing.batches)
                .where(worker_processing.batches.c.intent_id == plan.id)
            )
            == requests
        )
        synthetic.rollback()


def prove(target, names, bootstrap):
    global PHASE
    e = sa.create_engine(
        "postgresql+psycopg://",
        creator=lambda: target.connect(names.database, bootstrap),
        poolclass=NullPool,
        hide_parameters=True,
    )
    tables = list(historical().tables.values())
    try:
        with e.connect() as c:
            transaction = c.begin()
            try:
                local_private_logging(c)
                c.exec_driver_sql("SET LOCAL lock_timeout='5s'")
                before = fingerprint(c, tables)
                old_head = c.scalar(
                    sa.text("SELECT version_num FROM public.alembic_version_tenant")
                )
                assert old_head == "f05_tenant_0004"
                role(c, names, "owner")
                PHASE = "DDL_FAILURE_ROLLBACK"
                denied(
                    c,
                    lambda: (apply_publication(c, names, ROOT), c.exec_driver_sql("SELECT 1/0")),
                    "22012",
                )
                assert (
                    c.scalar(sa.text("SELECT version_num FROM public.alembic_version_tenant"))
                    == old_head
                )
                PHASE = "MIGRATION_REPEAT"
                assert apply_publication(c, names, ROOT) == VERSION
                assert apply_publication(c, names, ROOT) == VERSION
                assert fingerprint(c, tables) == before
                profile = qwen_profile()
                space = c.scalar(
                    sa.text(
                        "SELECT id FROM knowledge.embedding_spaces "
                        "WHERE profile_fingerprint=:profile"
                    ),
                    {"profile": profile.fingerprint()},
                )
                assert space is not None
                physical = "knowledge." + table_name(space)
                PHASE = "READONLY_NO_OPERATIONAL_LEDGER"
                role(c, names, "readonly")
                denied(c, sa.select(intents).limit(0), "42501")
                denied(c, sa.select(batches).limit(0), "42501")
                c.execute(sa.select(publications).limit(0))
                role(c, names, "app")
                PHASE = "SYNTHETIC_READY_VERSION"
                with c.begin_nested() as synthetic:
                    f = fixture(c)
                    version, _config, data, rows = stage(c, f)
                    c.execute(complete(version, data, rows))
                    c.execute(
                        sa.insert(audit).values(
                            id=uuid4(),
                            principal_id=f["actor"],
                            repository_id=f["repo"],
                            target_id=version,
                            request_id=uuid4(),
                            action="INGESTION_READY",
                            outcome="OK",
                        )
                    )
                    c.exec_driver_sql("SET CONSTRAINTS ALL IMMEDIATE")
                    c.exec_driver_sql("SET CONSTRAINTS ALL DEFERRED")
                    PHASE = "PUBLISHED_WITHOUT_BINDING"

                    def without_binding():
                        c.execute(
                            sa.update(versions)
                            .where(versions.c.id == version)
                            .values(state="PUBLISHED")
                        )
                        c.exec_driver_sql("SET CONSTRAINTS ALL IMMEDIATE")

                    denied(c, without_binding)
                    identity = dict(
                        version_id=version,
                        space_id=space,
                        document_id=f["doc"],
                        repository_id=f["repo"],
                        actor_id=f["actor"],
                        profile_fingerprint=profile.fingerprint(),
                    )
                    intent = uuid4()
                    c.execute(
                        intents.insert().values(
                            id=intent,
                            **identity,
                            status="RUNNING",
                            attempt=1,
                            attempt_token=uuid4(),
                            lease_until=sa.func.clock_timestamp() + sa.text("interval '1 hour'"),
                        )
                    )

                    def publish(*, audit_event=True):
                        if (
                            c.scalar(sa.select(versions.c.state).where(versions.c.id == version))
                            != "PUBLISHED"
                        ):
                            c.execute(
                                sa.update(versions)
                                .where(versions.c.id == version)
                                .values(state="PUBLISHED")
                            )
                        c.execute(
                            sa.text(
                                "UPDATE knowledge.documents SET current_version_id=:version,"
                                "current_version_kind='PROCESSED' WHERE id=:doc"
                            ),
                            {"version": version, "doc": f["doc"]},
                        )
                        c.execute(
                            intents.update()
                            .where(intents.c.id == intent)
                            .values(
                                status="COMPLETE",
                                attempt_token=None,
                                lease_until=None,
                            )
                        )
                        c.execute(
                            publications.insert().values(
                                **identity,
                                intent_id=intent,
                                chunk_count=len(rows),
                            )
                        )
                        if audit_event:
                            c.execute(
                                sa.insert(audit).values(
                                    id=uuid4(),
                                    principal_id=f["actor"],
                                    repository_id=f["repo"],
                                    target_id=intent,
                                    request_id=uuid4(),
                                    action="EMBEDDING_PUBLISHED",
                                    outcome="OK",
                                )
                            )
                        c.exec_driver_sql("SET CONSTRAINTS ALL IMMEDIATE")
                        c.exec_driver_sql("SET CONSTRAINTS ALL DEFERRED")

                    PHASE = "PUBLICATION_MISSING_USAGE"
                    denied(c, publish)
                    PHASE = "BATCH_NEGATIVES"
                    values = identity | dict(
                        intent_id=intent,
                        ordinal=0,
                        chunk_ids=[rows[0]["id"]],
                        input_tokens=1,
                        requests=1,
                        elapsed_ms=1,
                    )
                    PHASE = "INTENT_OUTCOME_NEGATIVES"
                    for changes in (
                        {"status": "COMPLETE"},
                        {"error_code": "AUTHORIZATION_CHANGED"},
                        {"status": "FAILED", "attempt_token": None, "lease_until": None},
                    ):
                        denied(
                            c,
                            lambda changes=changes: c.execute(
                                intents.update().where(intents.c.id == intent).values(**changes)
                            ),
                        )
                    PHASE = "EXPIRED_ATTEMPT"
                    with c.begin_nested() as expired:
                        c.execute(
                            intents.update()
                            .where(intents.c.id == intent)
                            .values(
                                lease_until=sa.func.clock_timestamp()
                                - sa.text("interval '1 second'")
                            )
                        )
                        denied(c, lambda: c.execute(batches.insert().values(**values)))
                        expired.rollback()
                    for index, changes in enumerate(
                        (
                            {"chunk_ids": [uuid4()]},
                            {"input_tokens": profile.max_tokens + 1},
                            {"chunk_ids": [rows[0]["id"], rows[0]["id"]]},
                            {"ordinal": 2},
                        )
                    ):
                        PHASE = "BATCH_NEGATIVE_" + str(index)
                        denied(
                            c,
                            lambda changes=changes: c.execute(
                                batches.insert().values(**(values | changes))
                            ),
                        )
                    for ordinal, offset in enumerate(range(0, len(rows), profile.max_batch)):
                        ids = [row["id"] for row in rows[offset : offset + profile.max_batch]]
                        c.execute(
                            batches.insert().values(
                                **(
                                    values
                                    | {
                                        "ordinal": ordinal,
                                        "chunk_ids": ids,
                                        "input_tokens": len(ids),
                                    }
                                )
                            )
                        )
                    denied(c, lambda: c.execute(batches.insert().values(**values)), "23514")
                    PHASE = "PUBLICATION_MISSING_VECTORS"

                    denied(c, publish)
                    PHASE = "SYNTHETIC_VECTORS"
                    insert = sa.text(
                        "INSERT INTO "
                        + physical
                        + "(chunk_id,version_id,document_id,repository_id,space_id,dimension,"
                        "profile_fingerprint,embedding) VALUES"
                        "(:chunk,:version,:document,:repository,:space,1024,"
                        ":profile,CAST(:vector AS vector))"
                    )
                    for row in rows:
                        c.execute(
                            insert,
                            {
                                "chunk": row["id"],
                                "version": version,
                                "document": f["doc"],
                                "repository": f["repo"],
                                "space": space,
                                "profile": profile.fingerprint(),
                                "vector": "[1," + ",".join(["0"] * 1023) + "]",
                            },
                        )
                    PHASE = "MISSING_AUDIT"
                    denied(c, lambda: publish(audit_event=False))
                    PHASE = "REVOKED_ACL"
                    with c.begin_nested() as revoked:
                        c.execute(
                            sa.text(
                                "DELETE FROM security.repository_acl WHERE repository_id=:repo "
                                "AND principal_id=:actor"
                            ),
                            {"repo": f["repo"], "actor": f["actor"]},
                        )
                        denied(c, publish)
                        revoked.rollback()
                    PHASE = "TOMBSTONED_DOCUMENT"
                    with c.begin_nested() as tombstone:
                        c.execute(
                            sa.text(
                                "UPDATE knowledge.documents SET state='TOMBSTONED',"
                                "tombstoned_at=clock_timestamp(),tombstoned_by=:actor WHERE id=:doc"
                            ),
                            {"doc": f["doc"], "actor": f["actor"]},
                        )
                        denied(c, publish)
                        tombstone.rollback()
                    PHASE = "ATOMIC_PUBLICATION"
                    publish()
                    assert c.scalar(
                        sa.select(publications.c.chunk_count).where(
                            publications.c.intent_id == intent
                        )
                    ) == len(rows)
                    assert (
                        c.scalar(
                            sa.text(
                                "SELECT original_version_id FROM knowledge.documents WHERE id=:doc"
                            ),
                            {"doc": f["doc"]},
                        )
                        == f["raw"]
                    )
                    denied(c, lambda: c.execute(publications.delete()), "42501")
                    denied(c, lambda: c.execute(batches.delete()), "42501")
                    denied(
                        c,
                        lambda: c.execute(
                            sa.update(versions)
                            .where(versions.c.id == version)
                            .values(state="READY_FOR_EMBEDDING")
                        ),
                    )
                    PHASE = "ORIGINAL_SELECTION"
                    original = c.execute(
                        selection("embedding_publication").where(documents.c.id == f["doc"])
                    ).one()
                    assert original.version_id == f["raw"] and original.blob_key is not None
                    PHASE = "ORIGINAL_RECEIPT_REPLAY"
                    replay = document_view(
                        c,
                        SimpleNamespace(
                            document_id=f["doc"], repository_id=f["repo"], version_id=f["raw"]
                        ),
                        profile="embedding_publication",
                    )
                    assert replay["version_id"] == str(f["raw"])
                    PHASE = "ORIGINAL_INGEST_REQUEST"
                    requested = journal.request(
                        c,
                        f["actor"],
                        f["repo"],
                        f["doc"],
                        uuid4(),
                        profile="embedding_publication",
                    )
                    PHASE = "ORIGINAL_INGEST_REPLAY"
                    again = journal.request(
                        c,
                        f["actor"],
                        f["repo"],
                        f["doc"],
                        uuid4(),
                        profile="embedding_publication",
                    )
                    assert requested.id == again.id
                    assert (
                        c.scalar(
                            sa.select(versions.c.original_version_id).where(
                                versions.c.id == requested.version_id
                            )
                        )
                        == f["raw"]
                    )
                    PHASE = "RELAY_AFTER_COMPLETE"
                    c.execute(
                        intents.update()
                        .where(intents.c.id == intent)
                        .values(
                            dispatch_state="DISPATCHED",
                            job_id=uuid4(),
                            dispatched_at=sa.func.clock_timestamp(),
                        )
                    )
                    denied(
                        c,
                        lambda: c.execute(
                            intents.update().where(intents.c.id == intent).values(job_id=uuid4())
                        ),
                    )
                    denied(
                        c,
                        lambda: c.execute(
                            intents.update().where(intents.c.id == intent).values(status="PENDING")
                        ),
                    )
                    PHASE = "NEW_SPACE_REINDEX"
                    old_space, old_physical = space, physical
                    profile = replace(profile, model_revision="synthetic-reindex-proof")
                    space = uuid4()
                    role(c, names, "owner")
                    assert register_publication_space(c, names, space, profile) == space
                    assert register_publication_space(c, names, space, profile) == space
                    role(c, names, "app")
                    assert c.scalar(
                        sa.select(publications.c.chunk_count).where(
                            publications.c.version_id == version,
                            publications.c.space_id == old_space,
                        )
                    ) == len(rows)
                    identity = identity | {
                        "space_id": space,
                        "profile_fingerprint": profile.fingerprint(),
                    }
                    intent = uuid4()
                    c.execute(
                        intents.insert().values(
                            id=intent,
                            **identity,
                            status="RUNNING",
                            attempt=1,
                            attempt_token=uuid4(),
                            lease_until=sa.func.clock_timestamp() + sa.text("interval '1 hour'"),
                        )
                    )
                    physical = "knowledge." + table_name(space)
                    new_insert = sa.text(str(insert).replace(old_physical, physical))
                    for ordinal, offset in enumerate(range(0, len(rows), profile.max_batch)):
                        batch_rows = rows[offset : offset + profile.max_batch]
                        c.execute(
                            batches.insert().values(
                                **identity,
                                intent_id=intent,
                                ordinal=ordinal,
                                chunk_ids=[r["id"] for r in batch_rows],
                                input_tokens=len(batch_rows),
                                requests=1,
                                elapsed_ms=1,
                            )
                        )
                        for row in batch_rows:
                            c.execute(
                                new_insert,
                                {
                                    "chunk": row["id"],
                                    "version": version,
                                    "document": f["doc"],
                                    "repository": f["repo"],
                                    "space": space,
                                    "profile": profile.fingerprint(),
                                    "vector": "[1," + ",".join(["0"] * 1023) + "]",
                                },
                            )
                    publish()
                    assert (
                        c.scalar(
                            sa.select(sa.func.count())
                            .select_from(publications)
                            .where(publications.c.version_id == version)
                        )
                        == 2
                    )
                    assert c.scalar(
                        sa.text(
                            "SELECT count(*) FROM " + old_physical + " WHERE version_id=:version"
                        ),
                        {"version": version},
                    ) == len(rows)
                    denied(
                        c,
                        lambda: c.execute(
                            publications.insert().values(
                                **identity, intent_id=intent, chunk_count=len(rows)
                            )
                        ),
                        "23505",
                    )
                    synthetic.rollback()
                worker_tenant_proof(c, names)
                assert fingerprint(c, tables) == before
            finally:
                transaction.rollback()
            PHASE = "FINAL_ROLLBACK"
            assert (
                c.scalar(sa.text("SELECT version_num FROM public.alembic_version_tenant"))
                == old_head
            )
            assert not c.scalar(
                sa.text("SELECT to_regclass('knowledge.embedding_publications') IS NOT NULL")
            )
            assert fingerprint(c, tables) == before
    finally:
        e.dispose()


def run(*, probe=prove, sources=("f05_tenant_0004",)):
    global PHASE
    if not sources or not set(sources) <= {"f05_tenant_0004", "f05_tenant_0006"}:
        raise ValueError("Unknown probe source")
    control = engine("migrator")
    try:
        ctables = list(Base.metadata.tables.values()) + list(IdentityBase.metadata.tables.values())
        with control.connect() as c:
            before = fingerprint(c, ctables)
        primary = Credential(*credential("bootstrap"))
        secondary = Credential(
            "f01_bootstrap", private_file("/run/secrets/postgres2_password", 4096).decode()
        )
        fixtures = json.loads((ROOT / "ops/f03/application-scope.json").read_text())["fixtures"]
        for fixture in fixtures:
            PHASE = "CATALOG"
            tenant = UUID(fixture["tenant"])
            with control.connect() as c:
                row = c.execute(
                    sa.select(
                        Tenant.state,
                        Tenant.migration_state,
                        Tenant.desired_version,
                        Tenant.observed_version,
                        Instance.host,
                        Instance.port,
                        ProvisioningOperation.id,
                        DbLocation.db_name,
                    )
                    .select_from(Tenant)
                    .join(DbLocation, DbLocation.tenant_id == Tenant.id)
                    .join(Instance, Instance.id == DbLocation.instance_id)
                    .join(ProvisioningOperation, ProvisioningOperation.tenant_id == Tenant.id)
                    .where(Tenant.id == tenant, ProvisioningOperation.state == "SUCCEEDED")
                ).one()
            assert row.state == row.migration_state == "READY"
            assert row.desired_version == row.observed_version and row.desired_version in sources
            assert row.host in ("postgres", "postgres2") and row.port == 5432
            names = Names(tenant, row.id)
            assert row.db_name == names.database
            probe(
                Target(row.host, row.port, CA),
                names,
                primary if row.host == "postgres" else secondary,
            )
            print(
                "PASS F05 PUBLICATION "
                + fixture["name"]
                + ": coverage/usage/audit/ACL/atomic pointer; rollback intact."
            )
        with control.connect() as c:
            assert fingerprint(c, ctables) == before
        print(
            "F05 PUBLICATION: four fixtures/two instances; no persistent adoption or publication."
        )
    finally:
        control.dispose()


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    try:
        run()
    except Exception as error:
        state = getattr(getattr(error, "orig", error), "sqlstate", None)
        code = (
            "SQLSTATE_" + state
            if isinstance(state, str) and re.fullmatch("[A-Z0-9]{5}", state)
            else "REFUSED"
        )
        print(
            "F05-PUBLICATION "
            + PHASE
            + " "
            + code
            + " "
            + type(error).__name__
            + "; rollback/resources retained."
        )
        raise SystemExit(1) from None
