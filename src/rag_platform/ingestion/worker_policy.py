"""Cooperate with existing identity and provisioning locks without catalog UPDATE grants."""

import hashlib
import time

import sqlalchemy as sa

from rag_platform.control.identity import AccessError
from rag_platform.control.identity_admin import GLOBAL_LOCK
from rag_platform.documents.policy import tenant_allows
from rag_platform.ingestion.claims import ClaimExpired
from rag_platform.tenancy.authorization import AuthorizedTenantContext


def administrative_locks(c, tenant):
    if c.dialect.name == "postgresql":
        # Existing IdentityAdministration writers use exclusive global/membership
        # locks; controlled provisioning/migrations use the exclusive saga lock.
        membership = int.from_bytes(
            hashlib.sha256(b"rag-platform/f02/membership:" + tenant.bytes).digest()[:8],
            "big",
            signed=True,
        )
        saga = int.from_bytes(
            hashlib.sha256(("f01-saga-tenant:" + str(tenant)).encode()).digest()[:8],
            "big",
            signed=True,
        )
        for key in (GLOBAL_LOCK, membership, saga):
            if not c.scalar(sa.text("SELECT pg_try_advisory_xact_lock_shared(:key)"), {"key": key}):
                raise AccessError("CATALOG_UNAVAILABLE")


def policy_guard(guard, authority, context, trace):
    if (
        not guard.active
        or guard.connection.engine is not authority.engine
        or authority.profile not in ("ingestion", "embeddings", "embedding_publication")
        or not isinstance(context, AuthorizedTenantContext)
        or context.tenant_id != guard.claim.tenant_id
        or context.principal_id != guard.claim.actor_id
    ):
        raise AccessError("INPUT_INVALID")
    c = guard.connection
    administrative_locks(c, context.tenant_id)
    guard.check()
    checked = authority.validate(context, trace)
    if len(checked.roles) != 1 or not tenant_allows(checked.roles[0], "upload"):
        raise AccessError("ROLE_DENIED")
    return checked


def before_commit(guard, context, stopped):
    if stopped():
        raise StopRequested()
    guard.check()
    if time.time() >= context.expires_at:
        raise ClaimExpired()


class StopRequested(RuntimeError):
    def __init__(self):
        super().__init__("STOP_REQUESTED")
