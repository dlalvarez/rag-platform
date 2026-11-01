"""Current F03 tables built from an immutable historical schema definition."""

from rag_platform.documents.schema_f03_0002 import VERSION as VERSION
from rag_platform.documents.schema_f03_0002 import build_metadata

metadata = build_metadata()
repositories = metadata.tables["knowledge.repositories"]
repository_acl = metadata.tables["security.repository_acl"]
sources = metadata.tables["knowledge.sources"]
documents = metadata.tables["knowledge.documents"]
document_versions = metadata.tables["knowledge.document_versions"]
document_receipts = metadata.tables["ops.document_receipts"]
audit_events = metadata.tables["ops.audit_events"]
