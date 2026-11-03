"""Exact SQL retrieval component; synthetic embeddings and every DDL/data rolled back."""

import logging
import math
import re
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import f05_publication_check as battery
import sqlalchemy as sa
from f04_schema_check import complete, fingerprint, fixture, role, stage
from sqlalchemy.pool import NullPool

from rag_platform.embeddings import processing
from rag_platform.embeddings.fixture import DeterministicFixture, fixture_profile
from rag_platform.embeddings.publication_migrations import (
    apply_publication,
    register_publication_space,
)
from rag_platform.embeddings.queue import EmbeddingClaim
from rag_platform.embeddings.retrieval_sql import SearchError, exact
from rag_platform.embeddings.space_ddl import table_name
from rag_platform.ingestion.logging_setup import local_private_logging
from rag_platform.ingestion.schema import audit
from rag_platform.ingestion.schema_f04_0003 import build_metadata as historical

PHASE = "START"


def prove(target, names, bootstrap, *, retrieve=exact, after_publication=None):
    global PHASE
    engine = sa.create_engine(
        "postgresql+psycopg://",
        creator=lambda: target.connect(names.database, bootstrap),
        poolclass=NullPool,
        hide_parameters=True,
    )

    @sa.event.listens_for(engine, "handle_error")
    def diagnostic(context):
        state = getattr(context.original_exception, "sqlstate", None)
        if isinstance(state, str) and re.fullmatch("[A-Z0-9]{5}", state):
            print("F05 EXACT SQLSTATE " + state)

    tables = list(historical().tables.values())
    space = uuid4()
    try:
        with engine.connect() as c:
            transaction = c.begin()
            try:
                local_private_logging(c)
                c.exec_driver_sql("SET LOCAL lock_timeout='5s'")
                c.exec_driver_sql("SET LOCAL statement_timeout='20s'")
                before = fingerprint(c, tables)
                prior = c.scalar(sa.text("SELECT version_num FROM public.alembic_version_tenant"))
                assert prior in ("f05_tenant_0004", "f05_tenant_0006")
                role(c, names, "owner")
                PHASE = "TEMPORARY_SCHEMA"
                apply_publication(c, names, battery.ROOT)
                profile = fixture_profile(max_tokens=64, max_batch=2)
                register_publication_space(c, names, space, profile)
                role(c, names, "app")
                f = fixture(c)
                version, _, data, rows = stage(c, f)
                c.execute(complete(version, data, rows))
                c.execute(
                    audit.insert().values(
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
                plan = processing.request(c, f["actor"], f["repo"], f["doc"], version, profile)
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
                guard = SimpleNamespace(
                    claim=claim,
                    intent_id=plan.id,
                    check=lambda: datetime.now(UTC) + timedelta(seconds=180),
                )
                # Synthetic guard only: no claim of independent control/tenant commits.
                processing.start(c, guard, profile)
                provider = DeterministicFixture(profile)
                embedded = {}
                while True:
                    task = processing.next_batch(c, guard, profile)
                    if task is None:
                        break
                    response = provider.embed(task.texts, "passage")
                    processing.save_batch(c, guard, profile, task, response, 1)
                    embedded.update(zip(task.chunk_ids, response.vectors, strict=True))
                vector = next(iter(embedded.values()))
                PHASE = "UNPUBLISHED_HIDDEN"
                assert retrieve(c, f["actor"], (f["repo"],), space, profile, vector, 50) == ()
                processing.complete(c, guard, profile)
                if after_publication is not None:
                    after_publication(c, names, space, profile, f, embedded)
                PHASE = "EXACT_REFERENCE"
                hits = retrieve(c, f["actor"], (f["repo"],), space, profile, vector, 50)
                assert len(hits) == len(embedded)
                expected = sorted(
                    embedded,
                    key=lambda chunk: (
                        1.0
                        - math.fsum(a * b for a, b in zip(embedded[chunk], vector, strict=True))
                        / (
                            math.sqrt(math.fsum(v * v for v in embedded[chunk]))
                            * math.sqrt(math.fsum(v * v for v in vector))
                        ),
                        str(chunk),
                    ),
                )
                assert [h.chunk_id for h in hits] == expected
                assert all(
                    h.repository_id == f["repo"]
                    and h.document_id == f["doc"]
                    and h.version_id == version
                    and len(h.excerpt) <= 512
                    and -1.0 <= h.score <= 1.0
                    for h in hits
                )
                assert retrieve(c, f["actor"], (f["repo"],), space, profile, vector, 1) == hits[:1]
                PHASE = "ACL_FILTER"
                assert retrieve(c, uuid4(), (f["repo"],), space, profile, vector, 50) == ()
                assert retrieve(c, f["actor"], (uuid4(),), space, profile, vector, 50) == ()
                reader = uuid4()
                c.exec_driver_sql(
                    "INSERT INTO security.repository_acl(repository_id,principal_id,role) "
                    "VALUES(%s,%s,'reader')",
                    (f["repo"], reader),
                )
                role(c, names, "readonly")
                assert retrieve(c, reader, (f["repo"],), space, profile, vector, 50) == hits
                role(c, names, "app")
                with c.begin_nested() as revoked:
                    c.execute(
                        sa.text(
                            "DELETE FROM security.repository_acl WHERE repository_id=:repo "
                            "AND principal_id=:actor"
                        ),
                        {"repo": f["repo"], "actor": reader},
                    )
                    assert retrieve(c, reader, (f["repo"],), space, profile, vector, 50) == ()
                    revoked.rollback()
                PHASE = "TOMBSTONE"
                with c.begin_nested() as tombstone:
                    c.execute(
                        processing.documents.update()
                        .where(processing.documents.c.id == f["doc"])
                        .values(
                            state="TOMBSTONED",
                            tombstoned_at=sa.func.clock_timestamp(),
                            tombstoned_by=f["actor"],
                        )
                    )
                    c.exec_driver_sql("SET CONSTRAINTS ALL IMMEDIATE")
                    assert retrieve(c, f["actor"], (f["repo"],), space, profile, vector, 50) == ()
                    tombstone.rollback()
                c.exec_driver_sql("SET CONSTRAINTS ALL DEFERRED")
                PHASE = "MISSING_BINDING"
                with c.begin_nested() as missing:
                    role(c, names, "owner")
                    c.execute(
                        processing.publications.delete().where(
                            processing.publications.c.intent_id == plan.id
                        )
                    )
                    assert retrieve(c, f["actor"], (f["repo"],), space, profile, vector, 50) == ()
                    missing.rollback()
                role(c, names, "app")
                PHASE = "PROFILE_MISMATCH"
                try:
                    retrieve(
                        c,
                        f["actor"],
                        (f["repo"],),
                        space,
                        replace(profile, model="other-same-dimension-model"),
                        vector,
                        50,
                    )
                except SearchError as error:
                    assert error.code == "PROFILE_MISMATCH"
                else:
                    raise RuntimeError("MISMATCH_ACCEPTED")
                assert retrieve(c, f["actor"], (f["repo"],), space, profile, vector, 50) == hits
            finally:
                transaction.rollback()
            PHASE = "FINAL_ROLLBACK"
            assert (
                c.scalar(sa.text("SELECT version_num FROM public.alembic_version_tenant")) == prior
            )
            assert not c.scalar(
                sa.text("SELECT to_regclass(:name) IS NOT NULL"),
                {"name": "knowledge." + table_name(space)},
            )
            assert fingerprint(c, tables) == before
    finally:
        engine.dispose()


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    try:
        battery.run(probe=prove, sources=("f05_tenant_0004", "f05_tenant_0006"))
        print("PASS F05 EXACT: ACL/publication/profile/tombstone checks; rollback intact.")
    except Exception as error:
        state = getattr(getattr(error, "orig", error), "sqlstate", None)
        code = state if isinstance(state, str) and re.fullmatch("[A-Z0-9]{5}", state) else "REFUSED"
        print("F05 EXACT " + PHASE + " " + code + "; rollback/resources retained.")
        raise SystemExit(1) from None
