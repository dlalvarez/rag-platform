"""Audited identity administration; OIDC claims never grant product roles."""

import hashlib
import logging
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from rag_platform.control.identity import AccessError, audit
from rag_platform.control.identity_models import (
    Membership,
    PlatformRole,
    TenantProfile,
    User,
)
from rag_platform.control.models import Tenant

GLOBAL_LOCK = 5927087775798362113


def upsert(connection, model, values, keys, changes):
    insert = pg_insert if connection.dialect.name == "postgresql" else sqlite_insert
    connection.execute(
        insert(model.__table__)
        .values(**values)
        .on_conflict_do_update(index_elements=keys, set_=changes)
    )


class IdentityAdministration:
    def __init__(self, engine, principal_id, request_id):
        if not isinstance(principal_id, UUID) or not isinstance(request_id, UUID):
            raise AccessError("INPUT_INVALID")
        self.engine, self.principal, self.request = engine, principal_id, request_id

    def _active(self, connection):
        if connection.scalar(sa.select(User.state).where(User.id == self.principal)) != "ACTIVE":
            raise AccessError("IDENTITY_SUSPENDED")

    def _operator(self, connection):
        self._active(connection)
        if (
            connection.scalar(
                sa.select(PlatformRole.state).where(
                    PlatformRole.user_id == self.principal, PlatformRole.role == "platform_operator"
                )
            )
            != "ACTIVE"
        ):
            raise AccessError("ROLE_DENIED")

    def _global_lock(self, connection):
        if connection.dialect.name == "postgresql":
            connection.execute(sa.text("SELECT pg_advisory_xact_lock(:k)"), {"k": GLOBAL_LOCK})

    def _tenant_lock(self, connection, tenant):
        if not isinstance(tenant, UUID):
            raise AccessError("INPUT_INVALID")
        if connection.dialect.name == "postgresql":
            digest = hashlib.sha256(b"rag-platform/f02/membership:" + tenant.bytes).digest()
            key = int.from_bytes(digest[:8], "big", signed=True)
            connection.execute(sa.text("SELECT pg_advisory_xact_lock(:k)"), {"k": key})

    def _target(self, connection, user, *, active=False):
        if not isinstance(user, UUID):
            raise AccessError("INPUT_INVALID")
        state = connection.scalar(sa.select(User.state).where(User.id == user))
        if state is None or (active and state != "ACTIVE"):
            raise AccessError("INPUT_INVALID")

    def _run(self, event, operation, *, target=None, tenant=None):
        try:
            with self.engine.begin() as c:
                self._active(c)
                result = operation(c)
                audit(
                    c,
                    request_id=self.request,
                    principal_id=self.principal,
                    target_user_id=target,
                    tenant_id=tenant,
                    event=event,
                    outcome="OK",
                )
                return result
        except Exception as error:
            failure = error if isinstance(error, AccessError) else AccessError()
            # Commit the denial separately after the business transaction rolls back.
            try:
                with self.engine.begin() as c:
                    principal = c.scalar(sa.select(User.id).where(User.id == self.principal))
                    known_target = (
                        c.scalar(sa.select(User.id).where(User.id == target))
                        if isinstance(target, UUID)
                        else None
                    )
                    audit(
                        c,
                        request_id=self.request,
                        principal_id=principal,
                        target_user_id=known_target,
                        tenant_id=tenant if isinstance(tenant, UUID) else None,
                        event="AUTH_DENIED",
                        outcome="DENIED",
                        reason=failure.code
                        if failure.code != "CATALOG_UNAVAILABLE"
                        else "DEPENDENCY_UNAVAILABLE",
                    )
            except Exception:
                # No business action succeeds if either transaction fails.
                logging.getLogger("rag_platform.identity").warning(
                    "identity_audit_unavailable request_id=%s code=%s",
                    str(self.request),
                    failure.code,
                )
            raise failure from None

    def bootstrap_operator(self, *, infrastructure_authorized=False):
        def operation(c):
            if infrastructure_authorized is not True:
                raise AccessError("ROLE_DENIED")
            self._global_lock(c)
            self._active(c)
            operators = c.execute(
                sa.select(PlatformRole.user_id, PlatformRole.state).where(
                    PlatformRole.role == "platform_operator"
                )
            ).all()
            if operators and operators != [(self.principal, "ACTIVE")]:
                raise AccessError("ROLE_DENIED")
            upsert(
                c,
                PlatformRole,
                {"user_id": self.principal, "role": "platform_operator", "state": "ACTIVE"},
                ["user_id", "role"],
                {"state": "ACTIVE"},
            )
            return {"principal_id": str(self.principal), "state": "ACTIVE"}

        return self._run("BOOTSTRAP", operation, target=self.principal)

    def bootstrap_owner(self, tenant, user, kind):
        def operation(c):
            self._operator(c)
            self._target(c, user, active=True)
            if not isinstance(tenant, UUID) or kind not in {"PERSONAL", "ORG"}:
                raise AccessError("INPUT_INVALID")
            self._tenant_lock(c, tenant)
            current = c.execute(
                sa.select(Tenant.state, Tenant.migration_state).where(Tenant.id == tenant)
            ).first()
            if current is None or current.state != "READY" or current.migration_state != "READY":
                raise AccessError("TENANT_UNAVAILABLE")
            self._operator(c)
            profile = c.scalar(
                sa.select(TenantProfile.kind).where(TenantProfile.tenant_id == tenant)
            )
            if profile is not None and profile != kind:
                raise AccessError("STATE_CONFLICT")
            owners = (
                c.execute(
                    sa.select(Membership.user_id).where(
                        Membership.tenant_id == tenant,
                        Membership.role == "owner",
                        Membership.state == "ACTIVE",
                    )
                )
                .scalars()
                .all()
            )
            if owners and user not in owners:
                raise AccessError("STATE_CONFLICT")
            if profile is None:
                c.execute(sa.insert(TenantProfile).values(tenant_id=tenant, kind=kind))
            upsert(
                c,
                Membership,
                {"user_id": user, "tenant_id": tenant, "role": "owner", "state": "ACTIVE"},
                ["user_id", "tenant_id"],
                {"role": "owner", "state": "ACTIVE"},
            )
            return {"tenant_id": str(tenant), "owner_id": str(user), "kind": kind}

        return self._run("BOOTSTRAP", operation, target=user, tenant=tenant)

    def membership(self, tenant, user, role, state="ACTIVE"):
        def operation(c):
            if (
                not isinstance(tenant, UUID)
                or role not in {"owner", "admin", "editor", "reader"}
                or state not in {"ACTIVE", "SUSPENDED", "REVOKED"}
            ):
                raise AccessError("INPUT_INVALID")
            authority = c.scalar(
                sa.select(Membership.role).where(
                    Membership.user_id == self.principal,
                    Membership.tenant_id == tenant,
                    Membership.state == "ACTIVE",
                )
            )
            if authority not in {"owner", "admin"}:
                raise AccessError("ROLE_DENIED")
            self._tenant_lock(c, tenant)
            if c.scalar(sa.select(Tenant.id).where(Tenant.id == tenant)) is None:
                raise AccessError("TENANT_UNAVAILABLE")
            # Recheck after acquiring the tenant lock; membership edits share this lock.
            self._active(c)
            authority = c.scalar(
                sa.select(Membership.role).where(
                    Membership.user_id == self.principal,
                    Membership.tenant_id == tenant,
                    Membership.state == "ACTIVE",
                )
            )
            if authority not in {"owner", "admin"}:
                raise AccessError("ROLE_DENIED")
            self._target(c, user, active=state == "ACTIVE")
            prior = c.execute(
                sa.select(Membership.role, Membership.state).where(
                    Membership.user_id == user, Membership.tenant_id == tenant
                )
            ).first()
            if authority == "admin" and (
                role in {"owner", "admin"} or (prior and prior.role in {"owner", "admin"})
            ):
                raise AccessError("ROLE_DENIED")
            if (
                prior
                and prior.role == "owner"
                and prior.state == "ACTIVE"
                and (role != "owner" or state != "ACTIVE")
                and c.scalar(sa.select(User.state).where(User.id == user)) == "ACTIVE"
            ):
                owners = c.scalar(
                    sa.select(sa.func.count())
                    .select_from(Membership)
                    .join(User, User.id == Membership.user_id)
                    .where(
                        Membership.tenant_id == tenant,
                        Membership.role == "owner",
                        Membership.state == "ACTIVE",
                        User.state == "ACTIVE",
                    )
                )
                if owners <= 1:
                    raise AccessError("LAST_OWNER")
            upsert(
                c,
                Membership,
                {"user_id": user, "tenant_id": tenant, "role": role, "state": state},
                ["user_id", "tenant_id"],
                {"role": role, "state": state},
            )
            return {"tenant_id": str(tenant), "user_id": str(user), "role": role, "state": state}

        return self._run("MEMBERSHIP_CHANGED", operation, target=user, tenant=tenant)

    def _operator_count(self, c):
        return c.scalar(
            sa.select(sa.func.count())
            .select_from(PlatformRole)
            .join(User, User.id == PlatformRole.user_id)
            .where(
                PlatformRole.role == "platform_operator",
                PlatformRole.state == "ACTIVE",
                User.state == "ACTIVE",
            )
        )

    def platform_role(self, user, role, state="ACTIVE"):
        def operation(c):
            self._global_lock(c)
            self._operator(c)
            self._target(c, user, active=state == "ACTIVE")
            if role not in {"platform_operator", "platform_support"} or state not in {
                "ACTIVE",
                "REVOKED",
            }:
                raise AccessError("INPUT_INVALID")
            prior = c.scalar(
                sa.select(PlatformRole.state).where(
                    PlatformRole.user_id == user, PlatformRole.role == role
                )
            )
            if (
                role == "platform_operator"
                and prior == "ACTIVE"
                and state != "ACTIVE"
                and self._operator_count(c) <= 1
            ):
                raise AccessError("LAST_OWNER")
            upsert(
                c,
                PlatformRole,
                {"user_id": user, "role": role, "state": state},
                ["user_id", "role"],
                {"state": state},
            )
            return {"user_id": str(user), "role": role, "state": state}

        return self._run("PLATFORM_ROLE_CHANGED", operation, target=user)

    def principal_state(self, user, state):
        def operation(c):
            self._global_lock(c)
            self._operator(c)
            self._target(c, user)
            if state not in {"ACTIVE", "SUSPENDED"}:
                raise AccessError("INPUT_INVALID")
            operator = c.scalar(
                sa.select(PlatformRole.state).where(
                    PlatformRole.user_id == user, PlatformRole.role == "platform_operator"
                )
            )
            if state == "SUSPENDED" and operator == "ACTIVE" and self._operator_count(c) <= 1:
                raise AccessError("LAST_OWNER")
            c.execute(sa.update(User).where(User.id == user).values(state=state))
            return {"user_id": str(user), "state": state}

        return self._run("PRINCIPAL_STATE_CHANGED", operation, target=user)

    def me(self):
        try:
            with self.engine.connect() as c:
                self._active(c)
                memberships = c.execute(
                    sa.select(Membership.tenant_id, Membership.role, Membership.state)
                    .where(Membership.user_id == self.principal)
                    .order_by(Membership.tenant_id)
                ).all()
                platform = (
                    c.execute(
                        sa.select(PlatformRole.role)
                        .where(
                            PlatformRole.user_id == self.principal, PlatformRole.state == "ACTIVE"
                        )
                        .order_by(PlatformRole.role)
                    )
                    .scalars()
                    .all()
                )
                return {
                    "principal_id": str(self.principal),
                    "platform_roles": platform,
                    "memberships": [
                        {"tenant_id": str(r.tenant_id), "role": r.role, "state": r.state}
                        for r in memberships
                    ],
                }
        except AccessError:
            raise
        except Exception:
            raise AccessError() from None
