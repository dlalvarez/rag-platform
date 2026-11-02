"""F05 guards extend completion without weakening retained F04 provenance."""

from rag_platform.ingestion.guards_f04_0003 import VERSION_GUARD as F04_VERSION

VERSION_GUARD = (
    F04_VERSION.replace("ops.f04_version_guard()", "ops.f05_version_guard()")
    .replace(
        "    IF OLD.kind='ORIGINAL'",
        """
    IF OLD.state='READY_FOR_EMBEDDING' AND NEW.state='PUBLISHED' THEN
        IF (to_jsonb(NEW)-'state') IS DISTINCT FROM (to_jsonb(OLD)-'state') THEN
            RAISE EXCEPTION 'immutable published provenance' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.state='PUBLISHED' THEN
        RAISE EXCEPTION 'immutable published version' USING ERRCODE='23514';
    END IF;
    IF OLD.kind='ORIGINAL'""",
    )
    .replace(
        "current_version_id=NEW.original_version_id", "original_version_id=NEW.original_version_id"
    )
)

INTENT_GUARD = """
CREATE FUNCTION ops.f05_embedding_intent_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $f05$
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'embedding intent retained' USING ERRCODE='23514';
    END IF;
    IF TG_OP='UPDATE' THEN
        IF ROW(NEW.id,NEW.version_id,NEW.space_id,NEW.document_id,NEW.repository_id,
               NEW.actor_id,NEW.profile_fingerprint,NEW.version_kind,NEW.created_at)
           IS DISTINCT FROM
           ROW(OLD.id,OLD.version_id,OLD.space_id,OLD.document_id,OLD.repository_id,
               OLD.actor_id,OLD.profile_fingerprint,OLD.version_kind,OLD.created_at) THEN
            RAISE EXCEPTION 'immutable embedding identity' USING ERRCODE='23514';
        END IF;
        IF OLD.dispatch_state='DISPATCHED' AND
           ROW(NEW.dispatch_state,NEW.job_id,NEW.dispatched_at) IS DISTINCT FROM
           ROW(OLD.dispatch_state,OLD.job_id,OLD.dispatched_at) THEN
            RAISE EXCEPTION 'immutable embedding dispatch' USING ERRCODE='23514';
        END IF;
        IF OLD.status='COMPLETE' AND
           (to_jsonb(NEW)-ARRAY['dispatch_state','job_id','dispatched_at','updated_at'])
           IS DISTINCT FROM
           (to_jsonb(OLD)-ARRAY['dispatch_state','job_id','dispatched_at','updated_at']) THEN
            RAISE EXCEPTION 'immutable embedding outcome' USING ERRCODE='23514';
        END IF;
    END IF;
    RETURN NEW;
END
$f05$
"""

BATCH_GUARD = """
CREATE FUNCTION ops.f05_embedding_batch_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $f05$
DECLARE
    expected integer;
    maximum integer;
    token_limit integer;
BEGIN
    IF TG_OP<>'INSERT' THEN
        RAISE EXCEPTION 'embedding batch retained' USING ERRCODE='23514';
    END IF;
    PERFORM 1 FROM ops.embedding_intents WHERE id=NEW.intent_id
      AND status='RUNNING' AND attempt_token IS NOT NULL
      AND lease_until>clock_timestamp() FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'inactive embedding attempt' USING ERRCODE='23514';
    END IF;
    PERFORM 1 FROM knowledge.documents d JOIN knowledge.document_versions v
      ON v.document_id=d.id AND v.repository_id=d.repository_id
      WHERE v.id=NEW.version_id AND d.id=NEW.document_id AND d.repository_id=NEW.repository_id
      AND v.state IN ('READY_FOR_EMBEDDING','PUBLISHED') AND d.state='RECEIVED'
      AND d.original_version_id=v.original_version_id FOR SHARE OF d,v;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'inactive embedding version' USING ERRCODE='23514';
    END IF;
    PERFORM 1 FROM knowledge.repositories WHERE id=NEW.repository_id AND state='ACTIVE' FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'inactive repository' USING ERRCODE='23514';
    END IF;
    PERFORM 1 FROM security.repository_acl WHERE repository_id=NEW.repository_id
      AND principal_id=NEW.actor_id AND role IN ('owner','admin','editor') FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'repository authorization changed' USING ERRCODE='23514';
    END IF;
    SELECT max_batch,max_tokens INTO maximum,token_limit FROM knowledge.embedding_spaces
      WHERE id=NEW.space_id AND profile_fingerprint=NEW.profile_fingerprint;
    IF NOT FOUND OR cardinality(NEW.chunk_ids)>maximum
       OR NEW.input_tokens>token_limit*cardinality(NEW.chunk_ids) THEN
        RAISE EXCEPTION 'embedding batch limits' USING ERRCODE='23514';
    END IF;
    SELECT count(*) INTO expected FROM ops.embedding_batches WHERE intent_id=NEW.intent_id;
    IF NEW.ordinal<>expected OR cardinality(NEW.chunk_ids) IS DISTINCT FROM
       (SELECT count(DISTINCT u.chunk_id) FROM unnest(NEW.chunk_ids) AS u(chunk_id))
       OR EXISTS(
           SELECT 1 FROM unnest(NEW.chunk_ids) AS u(chunk_id)
           LEFT JOIN knowledge.chunks c ON c.id=u.chunk_id AND c.version_id=NEW.version_id
             AND c.document_id=NEW.document_id AND c.repository_id=NEW.repository_id
           WHERE c.id IS NULL
       ) OR EXISTS(
           SELECT 1 FROM ops.embedding_batches b WHERE b.intent_id=NEW.intent_id
             AND b.chunk_ids && NEW.chunk_ids
       ) THEN
        RAISE EXCEPTION 'invalid embedding batch coverage' USING ERRCODE='23514';
    END IF;
    IF NOT EXISTS(
        SELECT 1 FROM ops.embedding_intents WHERE id=NEW.intent_id AND status='RUNNING'
          AND attempt_token IS NOT NULL AND lease_until>clock_timestamp()
    ) THEN
        RAISE EXCEPTION 'expired embedding attempt' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END
$f05$
"""

PUBLICATION_GUARD = """
CREATE FUNCTION ops.f05_embedding_publication_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $f05$
DECLARE
    expected integer;
    actual bigint;
    distinct_chunks bigint;
    vector_count bigint;
    physical text;
BEGIN
    IF TG_OP<>'INSERT' THEN
        RAISE EXCEPTION 'publication retained' USING ERRCODE='23514';
    END IF;
    SELECT v.chunk_count INTO expected FROM knowledge.document_versions v
      JOIN knowledge.documents d ON d.id=v.document_id AND d.repository_id=v.repository_id
      WHERE v.id=NEW.version_id AND v.document_id=NEW.document_id
        AND v.repository_id=NEW.repository_id AND v.state='PUBLISHED'
        AND d.state='RECEIVED' AND d.current_version_id=v.id
        AND d.current_version_kind='PROCESSED' AND d.original_version_id=v.original_version_id
      FOR SHARE OF d,v;
    IF NOT FOUND OR expected IS DISTINCT FROM NEW.chunk_count THEN
        RAISE EXCEPTION 'incomplete published version' USING ERRCODE='23514';
    END IF;
    PERFORM 1 FROM knowledge.repositories WHERE id=NEW.repository_id AND state='ACTIVE' FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'inactive repository' USING ERRCODE='23514';
    END IF;
    PERFORM 1 FROM security.repository_acl WHERE repository_id=NEW.repository_id
      AND principal_id=NEW.actor_id AND role IN ('owner','admin','editor') FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'repository authorization changed' USING ERRCODE='23514';
    END IF;
    PERFORM 1 FROM ops.embedding_intents WHERE id=NEW.intent_id AND status='COMPLETE';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'incomplete embedding intent' USING ERRCODE='23514';
    END IF;
    SELECT count(*),count(DISTINCT u.chunk_id) INTO actual,distinct_chunks
      FROM ops.embedding_batches b CROSS JOIN LATERAL unnest(b.chunk_ids) AS u(chunk_id)
      WHERE b.intent_id=NEW.intent_id;
    IF actual IS DISTINCT FROM expected::bigint OR distinct_chunks IS DISTINCT FROM actual THEN
        RAISE EXCEPTION 'incomplete embedding usage' USING ERRCODE='23514';
    END IF;
    physical := 'embeddings_' || replace(NEW.space_id::text,'-','');
    EXECUTE format(
        'SELECT count(*) FROM knowledge.%I WHERE version_id=$1 AND document_id=$2 '
        'AND repository_id=$3 AND space_id=$4 AND profile_fingerprint=$5', physical
    ) INTO vector_count USING NEW.version_id,NEW.document_id,NEW.repository_id,
                              NEW.space_id,NEW.profile_fingerprint;
    IF vector_count IS DISTINCT FROM expected::bigint THEN
        RAISE EXCEPTION 'incomplete embedding vectors' USING ERRCODE='23514';
    END IF;
    PERFORM 1 FROM ops.audit_events WHERE target_id=NEW.intent_id
      AND repository_id=NEW.repository_id AND principal_id=NEW.actor_id
      AND action='EMBEDDING_PUBLISHED' AND outcome='OK';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'missing publication audit' USING ERRCODE='23514';
    END IF;
    RETURN NULL;
END
$f05$
"""

POINTER_GUARD = """
CREATE FUNCTION ops.f05_published_pointer_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $f05$
BEGIN
    IF TG_TABLE_SCHEMA='knowledge' AND TG_TABLE_NAME='documents' THEN
        IF NEW.current_version_kind='PROCESSED' AND NOT EXISTS(
            SELECT 1 FROM knowledge.document_versions v JOIN knowledge.embedding_publications p
              ON p.version_id=v.id AND p.document_id=v.document_id
              AND p.repository_id=v.repository_id
            WHERE v.id=NEW.current_version_id AND v.document_id=NEW.id
              AND v.repository_id=NEW.repository_id AND v.state='PUBLISHED'
        ) THEN
            RAISE EXCEPTION 'unpublished document pointer' USING ERRCODE='23514';
        END IF;
    ELSE
        IF NEW.state='PUBLISHED' AND NOT EXISTS(
            SELECT 1 FROM knowledge.embedding_publications p JOIN knowledge.documents d
              ON d.id=p.document_id AND d.repository_id=p.repository_id
            WHERE p.version_id=NEW.id AND p.document_id=NEW.document_id
              AND p.repository_id=NEW.repository_id AND d.current_version_id=NEW.id
              AND d.current_version_kind='PROCESSED'
        ) THEN
            RAISE EXCEPTION 'missing publication binding' USING ERRCODE='23514';
        END IF;
    END IF;
    RETURN NULL;
END
$f05$
"""

FUNCTIONS = (
    ("f05_version_guard", VERSION_GUARD),
    ("f05_embedding_intent_guard", INTENT_GUARD),
    ("f05_embedding_batch_guard", BATCH_GUARD),
    ("f05_embedding_publication_guard", PUBLICATION_GUARD),
    ("f05_published_pointer_guard", POINTER_GUARD),
)
