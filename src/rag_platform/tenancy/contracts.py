"""Opaque credential references for later tenant provisioning and resolution."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class SecretRef:
    id: UUID
    version: int

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID) or type(self.version) is not int or self.version < 1:
            raise ValueError("A UUID and positive secret version are required")


@dataclass(frozen=True, slots=True)
class TenantDatabase:
    tenant_id: UUID
    instance_id: UUID
    database: str
    app_credential: SecretRef
    migrator_credential: SecretRef

    def __post_init__(self) -> None:
        if not isinstance(self.tenant_id, UUID) or not isinstance(self.instance_id, UUID):
            raise ValueError("Internal UUID identities are required")
        if self.database != f"rag_t_{self.tenant_id.hex}":
            raise ValueError("Database must be derived from the internal tenant UUID")
        if self.app_credential.id == self.migrator_credential.id:
            raise ValueError("App and migrator require separate credentials")
