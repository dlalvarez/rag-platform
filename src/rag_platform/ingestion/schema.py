"""Current F04 data metadata; historical migrations retain frozen definitions."""

from rag_platform.ingestion.schema_f04_0003 import VERSION as VERSION
from rag_platform.ingestion.schema_f04_0003 import build_metadata

metadata = build_metadata()
versions = metadata.tables["knowledge.document_versions"]
documents = metadata.tables["knowledge.documents"]
repositories = metadata.tables["knowledge.repositories"]
repository_acl = metadata.tables["security.repository_acl"]
blocks = metadata.tables["knowledge.extracted_blocks"]
chunks = metadata.tables["knowledge.chunks"]
intents = metadata.tables["ops.ingestion_intents"]
audit = metadata.tables["ops.audit_events"]
