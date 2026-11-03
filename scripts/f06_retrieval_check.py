"""Synthetic F06 PostgreSQL proof; no model, S3, persistent DDL or documents."""

import logging
import re
from dataclasses import replace
from uuid import uuid4

import f05_publication_check as battery
import f05_retrieval_check as reference
import sqlalchemy as sa

from rag_platform.ingestion.schema import chunks
from rag_platform.retrieval.contracts import CitationRef, QueryFilters, RetrievalError
from rag_platform.retrieval.sql import candidate_statement, hybrid, resolve

COUNTS = dict(fixtures=0, comparisons=0, lexical_checks=0, metadata_checks=0, citation_checks=0)


def metadata_probe(c, names, space, profile, allowed, embedded):
    reference.PHASE = "F06_FTS_AND_FILTERS"
    vector = next(iter(embedded.values()))
    arguments = (
        c,
        names.tenant,
        allowed["actor"],
        (allowed["repo"],),
        space,
        profile,
        vector,
        "SELECT",
        50,
    )
    base = hybrid(*arguments, QueryFilters())
    assert len(base) == len(embedded)
    actual = (
        c.execute(
            candidate_statement(
                allowed["actor"],
                (allowed["repo"],),
                space,
                profile,
                vector,
                "SELECT",
                QueryFilters(),
            )
        )
        .mappings()
        .all()
    )
    lexical = {row["chunk_id"] for row in actual if row["modality"] == "lexical"}
    source = c.execute(sa.select(chunks).where(chunks.c.id.in_(tuple(embedded)))).mappings().all()
    expected = {row["id"] for row in source if re.search(r"\bSELECT\b", row["text"])}
    assert expected and lexical == expected
    assert all(
        hit.lexical_rank is not None for hit in base if hit.evidence.reference.chunk_id in expected
    )
    for hit in base:
        evidence = hit.evidence
        row = next(row for row in source if row["id"] == evidence.reference.chunk_id)
        assert (
            evidence.start_offset == row["start_offset"]
            and evidence.end_offset == row["end_offset"]
        )
        assert evidence.excerpt == row["text"][:512]
        assert evidence.reference.tenant_id == names.tenant
    COUNTS["lexical_checks"] += 1

    reference.PHASE = "F06_METADATA"
    version = source[0]["version_id"]
    assert (
        hybrid(*arguments, QueryFilters(document_ids=(allowed["doc"],), version_ids=(version,)))
        == base
    )
    assert hybrid(*arguments, QueryFilters(document_ids=(uuid4(),))) == ()
    assert hybrid(*arguments, QueryFilters(version_ids=(uuid4(),))) == ()
    assert hybrid(*arguments, QueryFilters(page_min=1)) == ()  # This text fixture has no pages.
    assert hybrid(*arguments, QueryFilters(section_prefix=("missing",))) == ()
    selected = hybrid(*arguments, QueryFilters(section_prefix=("Uno",)))
    assert selected and all(hit.evidence.section[:1] == ("Uno",) for hit in selected)
    assert len(selected) < len(base)
    COUNTS["metadata_checks"] += 1
    COUNTS["fixtures"] += 1


def prove(target, names, bootstrap):
    def compared(c, actor, repositories, space, profile, vector, top_k):
        baseline = reference.exact(c, actor, repositories, space, profile, vector, top_k)
        # Compare complete eligible sets; hybrid ordering is intentionally different.
        candidate = hybrid(
            c,
            names.tenant,
            actor,
            repositories,
            space,
            profile,
            vector,
            "SELECT",
            50,
            QueryFilters(),
        )
        if top_k == 50:
            assert {h.chunk_id for h in baseline} == {
                h.evidence.reference.chunk_id for h in candidate
            }
        for hit in candidate:
            assert resolve(c, names.tenant, actor, hit.evidence.reference, profile) == hit.evidence
            COUNTS["citation_checks"] += 1
        if candidate:
            reference_id = candidate[0].evidence.reference
            for field in ("document_id", "version_id", "chunk_id"):
                try:
                    resolve(
                        c, names.tenant, actor, replace(reference_id, **{field: uuid4()}), profile
                    )
                except RetrievalError as error:
                    assert error.code == "NOT_FOUND"
                else:
                    raise AssertionError("FABRICATED_CITATION")
                COUNTS["citation_checks"] += 1
        if not candidate:
            # IDs from this temporary fixture only; do not expose its text or bypass the resolver.
            identities = c.execute(
                sa.select(
                    chunks.c.repository_id, chunks.c.document_id, chunks.c.version_id, chunks.c.id
                ).where(chunks.c.repository_id.in_(repositories))
            ).all()
            for row in identities:
                ref = CitationRef(names.tenant, space, *row)
                try:
                    resolve(c, names.tenant, actor, ref, profile)
                except RetrievalError as error:
                    assert error.code == "NOT_FOUND"
                else:
                    raise AssertionError("INELIGIBLE_CITATION")
                COUNTS["citation_checks"] += 1
        COUNTS["comparisons"] += 1
        return baseline

    reference.prove(target, names, bootstrap, retrieve=compared, after_publication=metadata_probe)


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    try:
        battery.run(probe=prove, sources=("f05_tenant_0006",))
        assert COUNTS["fixtures"] == COUNTS["lexical_checks"] == COUNTS["metadata_checks"] == 4
        assert COUNTS["citation_checks"] >= 4
        print(
            "PASS F06 SQL: four fixtures/FTS/metadata/citations/ACL/publication/roles/tombstone; "
            "history/control/DDL rollback intact."
        )
        print("F06 SQL COUNTS " + str(COUNTS))
    except Exception as error:
        state = getattr(getattr(error, "orig", error), "sqlstate", None)
        code = state if isinstance(state, str) and re.fullmatch("[A-Z0-9]{5}", state) else "REFUSED"
        print(
            "F06 SQL "
            + reference.PHASE
            + " "
            + code
            + " "
            + type(error).__name__
            + "; rollback/resources retained."
        )
        raise SystemExit(1) from None
