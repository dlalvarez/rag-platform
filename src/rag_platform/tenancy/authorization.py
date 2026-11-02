"""Request-bound membership authority. No secret lookup occurs in this module."""

import hashlib
import hmac
import json
import time
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from uuid import UUID

import sqlalchemy as sa

from rag_platform.control.identity import AccessError, audit
from rag_platform.control.identity_models import Membership, TenantProfile, User
from rag_platform.control.models import DbLocation, StorageLocation, Tenant
from rag_platform.tenancy.contracts import SecretRef
from rag_platform.tenancy.profiles import version_for
from rag_platform.tenancy.resolver import AdministrativeTenant


@dataclass(frozen=True, slots=True)
class AuthorizedTenantContext:
    principal_id: UUID
    tenant_id: UUID
    roles: tuple[str, ...]
    db_ref: SecretRef
    storage_ref: SecretRef
    trace_id: UUID
    expires_at: int
    _proof: str = field(repr=False, compare=False)


def payload(context):
    return json.dumps(
        [
            str(context.principal_id),
            str(context.tenant_id),
            context.roles,
            str(context.db_ref.id),
            context.db_ref.version,
            str(context.storage_ref.id),
            context.storage_ref.version,
            str(context.trace_id),
            context.expires_at,
        ],
        separators=(",", ":"),
    ).encode()


class TenantAuthorizer:
    def __init__(self, engine, key: bytes, *, profile="identity"):
        if not isinstance(key, bytes) or len(key) != 32:
            raise ValueError("Invalid authority configuration")
        self.engine, self._key = engine, key
        self.profile, self.version = profile, version_for(profile)

    def _sign(self, context):
        purpose = {
            "identity": b"F02/context/v1:",
            "documents": b"F03/context/v1:",
            "ingestion": b"F04/f04_tenant_0003/context/v1:",
        }[self.profile]
        return hmac.new(self._key, purpose + payload(context), hashlib.sha256).hexdigest()

    def _current(self, principal, tenant, trace):
        if not all(isinstance(v, UUID) for v in (principal, tenant, trace)):
            raise AccessError("INPUT_INVALID")
        with self.engine.connect() as c:
            if c.scalar(sa.select(User.state).where(User.id == principal)) != "ACTIVE":
                raise AccessError("IDENTITY_SUSPENDED")
            role = c.scalar(
                sa.select(Membership.role).where(
                    Membership.user_id == principal,
                    Membership.tenant_id == tenant,
                    Membership.state == "ACTIVE",
                )
            )
            if role not in {"owner", "admin", "editor", "reader"}:
                raise AccessError("MEMBERSHIP_REQUIRED")
            row = c.execute(
                sa.select(
                    Tenant.state,
                    Tenant.migration_state,
                    Tenant.desired_version,
                    Tenant.observed_version,
                    DbLocation.app_secret_ref,
                    DbLocation.app_secret_version,
                    DbLocation.readonly_secret_ref,
                    DbLocation.readonly_secret_version,
                    StorageLocation.credential_ref,
                    StorageLocation.credential_version,
                )
                .join(TenantProfile, TenantProfile.tenant_id == Tenant.id)
                .join(DbLocation, DbLocation.tenant_id == Tenant.id)
                .join(StorageLocation, StorageLocation.tenant_id == Tenant.id)
                .where(Tenant.id == tenant)
            ).first()
            if row is None or (
                row.state != "READY"
                or row.migration_state != "READY"
                or row.desired_version != self.version
                or row.observed_version != self.version
            ):
                raise AccessError("TENANT_UNAVAILABLE")
            db = (
                (row.readonly_secret_ref, row.readonly_secret_version)
                if role == "reader"
                else (row.app_secret_ref, row.app_secret_version)
            )
            if db[0] is None or db[1] is None:
                raise AccessError("TENANT_UNAVAILABLE")
            return AuthorizedTenantContext(
                principal,
                tenant,
                (role,),
                SecretRef(*db),
                SecretRef(row.credential_ref, row.credential_version),
                trace,
                int(time.time()) + 30,
                "",
            )

    def _denial(self, principal, tenant, trace, error):
        with self.engine.begin() as c:
            known = (
                c.scalar(sa.select(User.id).where(User.id == principal))
                if isinstance(principal, UUID)
                else None
            )
            audit(
                c,
                request_id=trace,
                principal_id=known,
                tenant_id=tenant if isinstance(tenant, UUID) else None,
                reason=error.code
                if error.code != "CATALOG_UNAVAILABLE"
                else "DEPENDENCY_UNAVAILABLE",
            )

    def authorize(self, principal, tenant, trace):
        try:
            context = self._current(principal, tenant, trace)
            return replace(context, _proof=self._sign(context))
        except Exception as error:
            failure = error if isinstance(error, AccessError) else AccessError()
            try:
                if isinstance(trace, UUID):
                    self._denial(principal, tenant, trace, failure)
            except Exception:
                raise AccessError() from None
            raise failure from None

    def validate(self, context, trace):
        try:
            valid = (
                isinstance(context, AuthorizedTenantContext)
                and isinstance(trace, UUID)
                and context.trace_id == trace
                and type(context.expires_at) is int
                and time.time() < context.expires_at <= time.time() + 31
                and hmac.compare_digest(context._proof, self._sign(context))
            )
        except Exception:
            valid = False
        if not valid:
            raise AccessError("INPUT_INVALID")
        current = self.authorize(context.principal_id, context.tenant_id, trace)
        if (current.roles, current.db_ref, current.storage_ref) != (
            context.roles,
            context.db_ref,
            context.storage_ref,
        ):
            error = AccessError("STATE_CONFLICT")
            try:
                self._denial(context.principal_id, context.tenant_id, trace, error)
            except Exception:
                raise AccessError() from None
            raise error
        return current


class AuthorizedConnections:
    """Only this checked boundary adapts user contexts to the existing F01 registry."""

    def __init__(self, authority, registry):
        self.authority, self.registry = authority, registry

    @contextmanager
    def connection(self, context, trace_id):
        checked = self.authority.validate(context, trace_id)
        role = "readonly" if checked.roles == ("reader",) else "app"
        with self.registry.connection(AdministrativeTenant(checked.tenant_id), role) as connection:
            yield connection
