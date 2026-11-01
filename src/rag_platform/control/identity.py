"""Idempotent OIDC identity registration; no membership or role auto-assignment."""

import time
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from rag_platform.control.identity_models import IdentityAudit, User
from rag_platform.providers.identity import Identity


class AccessError(RuntimeError):
    def __init__(self, code="CATALOG_UNAVAILABLE"):
        self.code = (
            code
            if code
            in {
                "CATALOG_UNAVAILABLE",
                "IDENTITY_SUSPENDED",
                "MEMBERSHIP_REQUIRED",
                "TENANT_UNAVAILABLE",
                "ROLE_DENIED",
                "LAST_OWNER",
                "INPUT_INVALID",
                "STATE_CONFLICT",
            }
            else "CATALOG_UNAVAILABLE"
        )
        super().__init__(self.code)


def audit(
    connection,
    *,
    request_id,
    principal_id=None,
    target_user_id=None,
    tenant_id=None,
    event="AUTH_DENIED",
    outcome="DENIED",
    reason="NONE",
):
    connection.execute(
        IdentityAudit.__table__.insert().values(
            id=uuid4(),
            request_id=request_id,
            principal_id=principal_id,
            target_user_id=target_user_id,
            tenant_id=tenant_id,
            event_code=event,
            outcome=outcome,
            reason=reason,
        )
    )


def register(engine, identity: Identity, request_id: UUID) -> UUID:
    if (
        not isinstance(identity, Identity)
        or not isinstance(request_id, UUID)
        or type(identity.expires_at) is not int
        or identity.expires_at <= time.time()
        or not isinstance(identity.issuer, str)
        or not 1 <= len(identity.issuer) <= 2048
        or not isinstance(identity.subject, str)
        or not 1 <= len(identity.subject) <= 255
    ):
        raise AccessError("INPUT_INVALID")
    try:
        denied = False
        with engine.begin() as connection:
            insert = pg_insert if connection.dialect.name == "postgresql" else sqlite_insert
            connection.execute(
                insert(User.__table__)
                .values(
                    id=uuid4(),
                    issuer=identity.issuer,
                    oidc_subject=identity.subject,
                )
                .on_conflict_do_nothing(index_elements=["issuer", "oidc_subject"])
            )
            row = connection.execute(
                sa.select(User.id, User.state).where(
                    User.issuer == identity.issuer, User.oidc_subject == identity.subject
                )
            ).one()
            denied = row.state != "ACTIVE"
            audit(
                connection,
                request_id=request_id,
                principal_id=row.id,
                event="AUTH_DENIED" if denied else "AUTHENTICATED",
                outcome="DENIED" if denied else "OK",
                reason="IDENTITY_SUSPENDED" if denied else "NONE",
            )
        if denied:
            raise AccessError("IDENTITY_SUSPENDED")
        return row.id
    except AccessError:
        raise
    except Exception:
        raise AccessError() from None
