"""Administrative catalog resolution only; this is not end-user authorization."""

from dataclasses import dataclass
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session
from sqlalchemy.pool import QueuePool

from rag_platform.control.models import DbLocation, Instance, Tenant
from rag_platform.tenancy.contracts import SecretRef

VERSION = "f01_tenant_0001"


class TenantAccessError(RuntimeError):
    CODES = {
        "INVALID_CONTEXT",
        "INVALID_ROLE",
        "TENANT_UNAVAILABLE",
        "SCHEMA_INCOMPATIBLE",
        "CATALOG_UNAVAILABLE",
        "SECRET_UNAVAILABLE",
        "CAPACITY",
        "POOL_TIMEOUT",
        "CONNECTION_FAILED",
        "REGISTRY_CLOSED",
    }

    def __init__(self, code):
        self.code = code if code in self.CODES else "CONNECTION_FAILED"
        super().__init__(self.code)


@dataclass(frozen=True, slots=True)
class AdministrativeTenant:
    """Trusted CLI/service identity, never evidence of membership or JWT validation."""

    tenant_id: UUID

    def __post_init__(self):
        if not isinstance(self.tenant_id, UUID):
            raise TenantAccessError("INVALID_CONTEXT")


@dataclass(frozen=True, slots=True)
class ResolvedDatabase:
    tenant_id: UUID
    instance_id: UUID
    host: str
    port: int
    database: str
    role: str
    credential: SecretRef

    @property
    def username(self):
        return self.database + "_" + self.role


class CatalogResolver:
    def __init__(self, control_engine):
        self.control_engine = control_engine

    def resolve(self, context: AdministrativeTenant, role="app") -> ResolvedDatabase:
        if not isinstance(context, AdministrativeTenant):
            raise TenantAccessError("INVALID_CONTEXT")
        if role not in {"app", "readonly"}:
            # Migrations remain on their dedicated NullPool path.
            raise TenantAccessError("INVALID_ROLE")
        try:
            with Session(self.control_engine) as session:
                tenant = session.get(Tenant, context.tenant_id)
                if tenant is None or tenant.state != "READY":
                    raise TenantAccessError("TENANT_UNAVAILABLE")
                if (
                    tenant.migration_state != "READY"
                    or tenant.desired_version != VERSION
                    or tenant.observed_version != VERSION
                ):
                    raise TenantAccessError("SCHEMA_INCOMPATIBLE")
                location = session.get(DbLocation, tenant.id)
                instance = session.get(Instance, location.instance_id) if location else None
                if (
                    location is None
                    or instance is None
                    or location.ssl_mode != "verify-full"
                    or location.db_name != "rag_t_" + tenant.id.hex
                ):
                    raise TenantAccessError("TENANT_UNAVAILABLE")
                ref = getattr(location, role + "_secret_ref")
                version = getattr(location, role + "_secret_version")
                return ResolvedDatabase(
                    tenant.id,
                    instance.id,
                    instance.host,
                    instance.port,
                    location.db_name,
                    role,
                    SecretRef(ref, version),
                )
        except TenantAccessError:
            raise
        except Exception:
            raise TenantAccessError("CATALOG_UNAVAILABLE") from None


def control_engine(target, credential):
    """Dedicated control budget; never use a tenant engine for control queries."""
    return sa.create_engine(
        "postgresql+psycopg://",
        creator=lambda: target.connect("rag_control", credential),
        poolclass=QueuePool,
        pool_size=2,
        max_overflow=0,
        pool_timeout=5,
        pool_pre_ping=True,
        pool_reset_on_return="rollback",
        hide_parameters=True,
    )
