"""Immutable F04 completion/retention guards, installed only by its migration."""

VERSION_GUARD = r"""
CREATE FUNCTION ops.f04_version_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $f04$
DECLARE
    actual_blocks bigint;
    actual_chunks bigint;
    first_ordinal integer;
    last_ordinal integer;
    actual_end integer;
    actual_hash text;
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'version retained' USING ERRCODE='23514';
    END IF;
    IF TG_OP='INSERT' THEN
        IF NEW.kind='PROCESSED' AND NEW.state<>'RECEIVED' THEN
            RAISE EXCEPTION 'initial version state' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.kind='ORIGINAL' OR OLD.state IN
       ('READY_FOR_EMBEDDING','FAILED_TERMINAL','NEEDS_OCR','TOMBSTONED') THEN
        RAISE EXCEPTION 'immutable version' USING ERRCODE='23514';
    END IF;
    IF ROW(NEW.id,NEW.document_id,NEW.repository_id,NEW.filename,NEW.mime,NEW.byte_size,
           NEW.content_hash,NEW.blob_key,NEW.created_at,NEW.kind,NEW.original_version_id,
           NEW.original_kind,NEW.processing_actor_id,NEW.parser_id,NEW.normalizer_id,
           NEW.chunker_id,NEW.config_hash,NEW.chunk_size,NEW.chunk_overlap)
       IS DISTINCT FROM
       ROW(OLD.id,OLD.document_id,OLD.repository_id,OLD.filename,OLD.mime,OLD.byte_size,
           OLD.content_hash,OLD.blob_key,OLD.created_at,OLD.kind,OLD.original_version_id,
           OLD.original_kind,OLD.processing_actor_id,OLD.parser_id,OLD.normalizer_id,
           OLD.chunker_id,OLD.config_hash,OLD.chunk_size,OLD.chunk_overlap) THEN
        RAISE EXCEPTION 'immutable provenance' USING ERRCODE='23514';
    END IF;
    IF NEW.state<>'READY_FOR_EMBEDDING' THEN
        RETURN NEW;
    END IF;
    IF OLD.state<>'CHUNKING' THEN
        RAISE EXCEPTION 'incomplete processing stage' USING ERRCODE='23514';
    END IF;
    PERFORM 1 FROM knowledge.repositories
      WHERE id=NEW.repository_id AND state='ACTIVE' FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'inactive repository' USING ERRCODE='23514';
    END IF;
    PERFORM 1 FROM knowledge.documents WHERE id=NEW.document_id
      AND repository_id=NEW.repository_id AND current_version_id=NEW.original_version_id
      AND state='RECEIVED' FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'inactive document' USING ERRCODE='23514';
    END IF;
    PERFORM 1 FROM security.repository_acl WHERE repository_id=NEW.repository_id
      AND principal_id=NEW.processing_actor_id AND role IN ('owner','admin','editor');
    IF NOT FOUND THEN
        RAISE EXCEPTION 'repository authorization changed' USING ERRCODE='23514';
    END IF;
    SELECT count(*),min(ordinal),max(ordinal),max(end_offset),
           encode(sha256(convert_to(string_agg(text,E'\n' ORDER BY ordinal),'UTF8')),'hex')
      INTO actual_blocks,first_ordinal,last_ordinal,actual_end,actual_hash
      FROM knowledge.extracted_blocks WHERE version_id=NEW.id;
    IF actual_blocks IS DISTINCT FROM NEW.block_count OR first_ordinal IS DISTINCT FROM 0
       OR last_ordinal IS DISTINCT FROM actual_blocks-1
       OR actual_end IS DISTINCT FROM NEW.character_count
       OR actual_hash IS DISTINCT FROM NEW.normalized_hash THEN
        RAISE EXCEPTION 'incomplete extracted blocks' USING ERRCODE='23514';
    END IF;
    IF EXISTS(
        SELECT 1 FROM (
            SELECT start_offset,
                   coalesce(lag(end_offset) OVER(ORDER BY ordinal),-1)+1 AS expected
              FROM knowledge.extracted_blocks WHERE version_id=NEW.id
        ) spans WHERE start_offset<>expected
    ) THEN
        RAISE EXCEPTION 'invalid block coverage' USING ERRCODE='23514';
    END IF;
    IF NEW.mime='application/pdf' THEN
        IF NEW.page_count IS DISTINCT FROM actual_blocks OR EXISTS(
            SELECT 1 FROM knowledge.extracted_blocks WHERE version_id=NEW.id
              AND (page IS DISTINCT FROM ordinal+1 OR kind NOT IN ('page','blank_page'))
        ) THEN
            RAISE EXCEPTION 'invalid page provenance' USING ERRCODE='23514';
        END IF;
    ELSIF EXISTS(
        SELECT 1 FROM knowledge.extracted_blocks WHERE version_id=NEW.id
          AND (page IS NOT NULL OR kind IN ('page','blank_page'))
    ) THEN
        RAISE EXCEPTION 'invented pagination' USING ERRCODE='23514';
    END IF;
    SELECT count(*),min(ordinal),max(ordinal) INTO actual_chunks,first_ordinal,last_ordinal
      FROM knowledge.chunks WHERE version_id=NEW.id;
    IF actual_chunks IS DISTINCT FROM NEW.chunk_count OR first_ordinal IS DISTINCT FROM 0
       OR last_ordinal IS DISTINCT FROM actual_chunks-1 THEN
        RAISE EXCEPTION 'incomplete chunks' USING ERRCODE='23514';
    END IF;
    IF EXISTS(
        SELECT 1 FROM (
            SELECT block_ordinal,lag(block_ordinal) OVER(ORDER BY ordinal) AS previous
              FROM knowledge.chunks WHERE version_id=NEW.id
        ) orderings WHERE block_ordinal<previous
    ) THEN
        RAISE EXCEPTION 'invalid chunk order' USING ERRCODE='23514';
    END IF;
    IF EXISTS(
        SELECT 1 FROM (
            SELECT start_offset,end_offset,block_start,text,
              lag(end_offset) OVER(PARTITION BY block_ordinal ORDER BY ordinal) AS previous
              FROM knowledge.chunks WHERE version_id=NEW.id
        ) spans WHERE char_length(text)>NEW.chunk_size
          OR (previous IS NULL AND start_offset<>block_start)
          OR (previous IS NOT NULL AND
              (start_offset<>previous-NEW.chunk_overlap OR end_offset<=previous))
    ) THEN
        RAISE EXCEPTION 'invalid chunk coverage' USING ERRCODE='23514';
    END IF;
    IF EXISTS(
        SELECT 1 FROM knowledge.extracted_blocks b
        LEFT JOIN knowledge.chunks c ON c.version_id=b.version_id AND c.block_ordinal=b.ordinal
        WHERE b.version_id=NEW.id
        GROUP BY b.version_id,b.ordinal,b.start_offset,b.end_offset,b.kind
        HAVING (b.kind='blank_page' AND count(c.id)<>0)
          OR (b.kind<>'blank_page' AND
              (count(c.id)=0 OR min(c.start_offset) IS DISTINCT FROM b.start_offset
                OR max(c.end_offset) IS DISTINCT FROM b.end_offset))
    ) THEN
        RAISE EXCEPTION 'missing block content' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END
$f04$
"""

BLOCK_GUARD = r"""
CREATE FUNCTION ops.f04_block_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $f04$
BEGIN
    PERFORM 1 FROM knowledge.document_versions WHERE id=NEW.version_id
      AND document_id=NEW.document_id AND repository_id=NEW.repository_id
      AND kind='PROCESSED' AND state='CHUNKING' FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'inactive processing version' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END
$f04$
"""

CHUNK_GUARD = r"""
CREATE FUNCTION ops.f04_chunk_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $f04$
DECLARE
    source knowledge.extracted_blocks%ROWTYPE;
BEGIN
    PERFORM 1 FROM knowledge.document_versions WHERE id=NEW.version_id
      AND document_id=NEW.document_id AND repository_id=NEW.repository_id
      AND kind='PROCESSED' AND state='CHUNKING' FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'inactive processing version' USING ERRCODE='23514';
    END IF;
    SELECT * INTO source FROM knowledge.extracted_blocks
      WHERE version_id=NEW.version_id AND ordinal=NEW.block_ordinal
        AND document_id=NEW.document_id AND repository_id=NEW.repository_id;
    IF NOT FOUND OR NEW.text IS DISTINCT FROM substring(source.text
          FROM NEW.start_offset-source.start_offset+1 FOR NEW.end_offset-NEW.start_offset)
       OR NEW.page IS DISTINCT FROM source.page OR NEW.section IS DISTINCT FROM source.section
       OR NEW.kind IS DISTINCT FROM source.kind THEN
        RAISE EXCEPTION 'invalid chunk provenance' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END
$f04$
"""

AUDIT_GUARD = r"""
CREATE FUNCTION ops.f04_ready_audit_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $f04$
BEGIN
    PERFORM 1 FROM ops.audit_events WHERE target_id=NEW.id
      AND repository_id=NEW.repository_id AND principal_id=NEW.processing_actor_id
      AND action='INGESTION_READY' AND outcome='OK';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'missing ready audit' USING ERRCODE='23514';
    END IF;
    RETURN NULL;
END
$f04$
"""

FUNCTIONS = (
    ("f04_version_guard", VERSION_GUARD),
    ("f04_block_guard", BLOCK_GUARD),
    ("f04_chunk_guard", CHUNK_GUARD),
    ("f04_ready_audit_guard", AUDIT_GUARD),
)
TRIGGERS = (
    (
        "f04_version_guard",
        "knowledge.document_versions",
        "INSERT OR UPDATE OR DELETE",
        "f04_version_guard",
    ),
    ("f04_block_guard", "knowledge.extracted_blocks", "INSERT", "f04_block_guard"),
    ("f04_chunk_guard", "knowledge.chunks", "INSERT", "f04_chunk_guard"),
)

READY_AUDIT_TRIGGER = """
CREATE CONSTRAINT TRIGGER f04_ready_audit
AFTER UPDATE ON knowledge.document_versions
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
WHEN (NEW.state='READY_FOR_EMBEDDING')
EXECUTE FUNCTION ops.f04_ready_audit_guard()
"""
