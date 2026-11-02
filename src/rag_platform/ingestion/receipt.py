"""F04 receipt extension: durable processing intent in the original tenant commit."""

from rag_platform.documents.errors import DocumentError
from rag_platform.documents.receipt import ReceiptService
from rag_platform.ingestion import journal


class IngestionReceiptService(ReceiptService):
    def __init__(self, repositories, gateway, **kwargs):
        if repositories.authority.profile not in ("ingestion", "embeddings"):
            raise ValueError("Ingestion authority required")
        super().__init__(repositories, gateway, **kwargs)

    def _accepted(self, connection, checked, trace, plan):
        try:
            journal.request(
                connection, checked.principal_id, plan.repository_id, plan.document_id, trace
            )
        except journal.IngestionError as error:
            code = {
                "AUTHORIZATION_CHANGED": "ROLE_DENIED",
                "TOMBSTONED": "NOT_FOUND",
                "IDEMPOTENCY_CONFLICT": "STATE_CONFLICT",
            }.get(error.code, error.code)
            raise DocumentError(code) from None
