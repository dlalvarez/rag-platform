"""Bounded identity views; physical catalog data never enters these responses."""

import base64
import hmac
import json
from uuid import UUID

import sqlalchemy as sa

from rag_platform.control.identity import AccessError
from rag_platform.control.identity_models import Membership, PlatformRole, TenantProfile, User
from rag_platform.control.models import Tenant
from rag_platform.tenancy.resolver import VERSION


class IdentityQueries:
    def __init__(self, engine, cursor_key):
        if not isinstance(cursor_key, bytes) or len(cursor_key) != 32:
            raise ValueError("Invalid cursor configuration")
        self.engine, self._key = engine, cursor_key

    def _cursor(self, principal, last):
        body = json.dumps([str(principal), str(last)], separators=(",", ":")).encode()
        mac = hmac.digest(self._key, b"F02/cursor/v1:" + body, "sha256")
        return base64.urlsafe_b64encode(body + mac).decode().rstrip("=")

    def _decode(self, principal, cursor):
        try:
            if not isinstance(cursor, str) or not 1 <= len(cursor) <= 256:
                raise ValueError()
            value = base64.b64decode(
                cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True
            )
            body, mac = value[:-32], value[-32:]
            if not hmac.compare_digest(
                mac, hmac.digest(self._key, b"F02/cursor/v1:" + body, "sha256")
            ):
                raise ValueError()
            owner, last = json.loads(body)
            if owner != str(principal):
                raise ValueError()
            return UUID(last)
        except Exception:
            raise AccessError("INPUT_INVALID") from None

    def _active(self, c, principal):
        if not isinstance(principal, UUID):
            raise AccessError("INPUT_INVALID")
        if c.scalar(sa.select(User.state).where(User.id == principal)) != "ACTIVE":
            raise AccessError("IDENTITY_SUSPENDED")

    def tenants(self, principal, *, limit=50, cursor=None):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise AccessError("INPUT_INVALID")
        last = self._decode(principal, cursor) if cursor is not None else None
        try:
            with self.engine.connect() as c:
                self._active(c, principal)
                statement = (
                    sa.select(Tenant.id, TenantProfile.kind, Membership.role)
                    .join(Membership, Membership.tenant_id == Tenant.id)
                    .join(TenantProfile, TenantProfile.tenant_id == Tenant.id)
                    .where(
                        Membership.user_id == principal,
                        Membership.state == "ACTIVE",
                        Tenant.state == "READY",
                        Tenant.migration_state == "READY",
                        Tenant.desired_version == VERSION,
                        Tenant.observed_version == VERSION,
                    )
                    .order_by(Tenant.id)
                    .limit(limit + 1)
                )
                if last:
                    statement = statement.where(Tenant.id > last)
                rows = c.execute(statement).all()
                return {
                    "items": [
                        {"tenant_id": str(r.id), "kind": r.kind, "role": r.role}
                        for r in rows[:limit]
                    ],
                    "next_cursor": self._cursor(principal, rows[limit - 1].id)
                    if len(rows) > limit
                    else None,
                }
        except AccessError:
            raise
        except Exception:
            raise AccessError() from None

    def me(self, principal):
        try:
            with self.engine.connect() as c:
                self._active(c, principal)
                roles = list(
                    c.scalars(
                        sa.select(PlatformRole.role)
                        .where(PlatformRole.user_id == principal, PlatformRole.state == "ACTIVE")
                        .order_by(PlatformRole.role)
                    )
                )
            page = self.tenants(principal)
            return {
                "principal_id": str(principal),
                "platform_roles": roles,
                "memberships": page["items"],
                "next_cursor": page["next_cursor"],
            }
        except AccessError:
            raise
        except Exception:
            raise AccessError() from None
