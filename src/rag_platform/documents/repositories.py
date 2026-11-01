"""Tenant-local repository CRUD and explicit ACL; platform roles never grant content."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert

from rag_platform.control.identity import AccessError, audit
from rag_platform.control.identity_models import Membership, User
from rag_platform.documents.errors import DocumentError
from rag_platform.documents.pagination import Pagination
from rag_platform.documents.policy import (
    may_assign,
    name_and_config,
    repository_allows,
    target_allows,
    tenant_allows,
)
from rag_platform.documents.schema import VERSION, audit_events, repositories, repository_acl


def logical_id(value):
    if not isinstance(value, UUID):
        raise DocumentError("INPUT_INVALID")
    return value


def view(row):
    def instant(value):
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise DocumentError()
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")

    return {
        "repository_id": str(row.id),
        "name": row.name,
        "owner_id": str(row.owner_id),
        "config": row.config,
        "state": row.state,
        "created_at": instant(row.created_at),
        "updated_at": instant(row.updated_at),
        "role": row.role,
    }


class RepositoryService:
    def __init__(self, connections, control_engine, cursor_key):
        if connections.authority.version != VERSION:
            raise ValueError("Document authority profile required")
        self.connections, self.control = connections, control_engine
        self.authority = connections.authority
        self.pagination = Pagination(cursor_key)

    def _denial(self, context, trace, error):
        reason = (
            error.code
            if error.code in {"INPUT_INVALID", "ROLE_DENIED", "STATE_CONFLICT", "LAST_OWNER"}
            else "DEPENDENCY_UNAVAILABLE"
        )
        if error.code == "OPERATION_IN_PROGRESS":
            reason = "STATE_CONFLICT"
        elif error.code in {"QUOTA_EXCEEDED", "TOO_LARGE"}:
            reason = "INPUT_INVALID"
        elif error.code == "NOT_FOUND":
            reason = "ROLE_DENIED"
        try:
            with self.control.begin() as c:
                audit(
                    c,
                    request_id=trace,
                    principal_id=context.principal_id,
                    tenant_id=context.tenant_id,
                    reason=reason,
                )
        except Exception:
            raise DocumentError() from None

    def _run(self, context, trace, action, operation):
        checked = self.authority.validate(context, trace)
        try:
            if len(checked.roles) != 1 or not tenant_allows(checked.roles[0], action):
                raise DocumentError("ROLE_DENIED")
            with self.connections.connection(checked, trace) as c, c.begin():
                return operation(c, checked)
        except DocumentError as error:
            self._denial(checked, trace, error)
            raise
        except AccessError:
            raise
        except sa.exc.IntegrityError as error:
            failure = DocumentError(
                "STATE_CONFLICT"
                if getattr(error.orig, "sqlstate", None) == "23505"
                else "DEPENDENCY_UNAVAILABLE"
            )
            self._denial(checked, trace, failure)
            raise failure from None
        except Exception:
            raise DocumentError() from None

    def _row(self, c, context, repo, action, *, lock=False):
        statement = (
            sa.select(repositories, repository_acl.c.role)
            .join(repository_acl, repository_acl.c.repository_id == repositories.c.id)
            .where(
                repositories.c.id == repo,
                repositories.c.state == "ACTIVE",
                repository_acl.c.principal_id == context.principal_id,
            )
        )
        if lock:
            statement = statement.with_for_update(of=repositories)
        row = c.execute(statement).first()
        if row is None or not repository_allows(row.role, action):
            raise DocumentError("ROLE_DENIED")
        return row

    def event(self, c, context, trace, repo, target, action):
        c.execute(
            audit_events.insert().values(
                id=uuid4(),
                principal_id=context.principal_id,
                repository_id=repo,
                target_id=target,
                request_id=trace,
                action=action,
                outcome="OK",
            )
        )

    def require(self, context, trace, repo, action):
        repo = logical_id(repo)
        if not isinstance(action, str) or action not in {"read", "upload"}:
            raise DocumentError("INPUT_INVALID")
        return self._run(
            context, trace, action, lambda c, checked: view(self._row(c, checked, repo, action))
        )

    def create(self, context, trace, name, config=None):
        name, config = name_and_config(name, config)

        def operation(c, checked):
            repo = uuid4()
            c.execute(
                repositories.insert().values(
                    id=repo,
                    name=name,
                    owner_id=checked.principal_id,
                    config=config,
                )
            )
            c.execute(
                repository_acl.insert().values(
                    repository_id=repo,
                    principal_id=checked.principal_id,
                    role="owner",
                )
            )
            self.event(c, checked, trace, repo, repo, "REPOSITORY_CREATED")
            return view(self._row(c, checked, repo, "read"))

        return self._run(context, trace, "create", operation)

    def list(self, context, trace, *, limit=50, cursor=None):
        last = self.pagination.decode(context, "repositories", cursor, limit)

        def operation(c, checked):
            query = (
                sa.select(repositories, repository_acl.c.role)
                .join(repository_acl, repository_acl.c.repository_id == repositories.c.id)
                .where(
                    repositories.c.state == "ACTIVE",
                    repository_acl.c.principal_id == checked.principal_id,
                )
                .order_by(repositories.c.id)
                .limit(limit + 1)
            )
            if last is not None:
                query = query.where(repositories.c.id > last)
            rows = c.execute(query).all()
            return self.pagination.page(
                checked, "repositories", rows, limit, key=lambda row: row.id, serialize=view
            )

        return self._run(context, trace, "read", operation)

    def show(self, context, trace, repo):
        repo = logical_id(repo)
        return self._run(
            context, trace, "read", lambda c, checked: view(self._row(c, checked, repo, "read"))
        )

    def update(self, context, trace, repo, name, config=None):
        repo = logical_id(repo)
        name, config = name_and_config(name, config)

        def operation(c, checked):
            self._row(c, checked, repo, "update", lock=True)
            c.execute(
                repositories.update()
                .where(repositories.c.id == repo)
                .values(
                    name=name,
                    config=config,
                    updated_at=sa.func.current_timestamp(),
                )
            )
            self.event(c, checked, trace, repo, repo, "REPOSITORY_UPDATED")
            return view(self._row(c, checked, repo, "read"))

        return self._run(context, trace, "update", operation)

    def delete(self, context, trace, repo):
        repo = logical_id(repo)

        def operation(c, checked):
            self._row(c, checked, repo, "delete", lock=True)
            c.execute(
                repositories.update()
                .where(repositories.c.id == repo)
                .values(
                    state="DELETED",
                    updated_at=sa.func.current_timestamp(),
                )
            )
            self.event(c, checked, trace, repo, repo, "REPOSITORY_DELETED")
            return {"repository_id": str(repo), "state": "DELETED"}

        return self._run(context, trace, "delete", operation)

    def _members(self, tenant, users):
        with self.control.connect() as c:
            return dict(
                c.execute(
                    sa.select(Membership.user_id, Membership.role)
                    .join(User, User.id == Membership.user_id)
                    .where(
                        Membership.tenant_id == tenant,
                        Membership.user_id.in_(users),
                        Membership.state == "ACTIVE",
                        User.state == "ACTIVE",
                    )
                ).all()
            )

    def set_acl(self, context, trace, repo, target, role):
        repo, target = logical_id(repo), logical_id(target)
        if role is not None and (
            not isinstance(role, str) or role not in {"owner", "admin", "editor", "reader"}
        ):
            raise DocumentError("INPUT_INVALID")

        def operation(c, checked):
            row = self._row(c, checked, repo, "acl", lock=True)
            prior = c.scalar(
                sa.select(repository_acl.c.role).where(
                    repository_acl.c.repository_id == repo, repository_acl.c.principal_id == target
                )
            )
            if not may_assign(row.role, prior, role):
                raise DocumentError("ROLE_DENIED")
            if role is not None and not target_allows(
                self._members(checked.tenant_id, [target]).get(target), role
            ):
                raise DocumentError("ROLE_DENIED")
            if prior == "owner" and role != "owner":
                owners = list(
                    c.scalars(
                        sa.select(repository_acl.c.principal_id)
                        .where(
                            repository_acl.c.repository_id == repo,
                            repository_acl.c.role == "owner",
                            repository_acl.c.principal_id != target,
                        )
                        .order_by(repository_acl.c.principal_id)
                    )
                )
                current = self._members(checked.tenant_id, owners) if owners else {}
                active_owners = [user for user in owners if current.get(user) in {"owner", "admin"}]
                if not active_owners:
                    raise DocumentError("LAST_OWNER")
                if row.owner_id == target:
                    c.execute(
                        repositories.update()
                        .where(repositories.c.id == repo)
                        .values(
                            owner_id=active_owners[0],
                            updated_at=sa.func.current_timestamp(),
                        )
                    )
            if role is None:
                c.execute(
                    repository_acl.delete().where(
                        repository_acl.c.repository_id == repo,
                        repository_acl.c.principal_id == target,
                    )
                )
            else:
                if (
                    prior is None
                    and c.scalar(
                        sa.select(sa.func.count())
                        .select_from(repository_acl)
                        .where(repository_acl.c.repository_id == repo)
                    )
                    >= 1000
                ):
                    raise DocumentError("QUOTA_EXCEEDED")
                c.execute(
                    insert(repository_acl)
                    .values(
                        repository_id=repo,
                        principal_id=target,
                        role=role,
                    )
                    .on_conflict_do_update(
                        index_elements=["repository_id", "principal_id"],
                        set_={"role": role, "updated_at": sa.func.current_timestamp()},
                    )
                )
            self.event(c, checked, trace, repo, target, "ACL_CHANGED")
            return {"repository_id": str(repo), "principal_id": str(target), "role": role}

        return self._run(context, trace, "acl", operation)

    def acl(self, context, trace, repo, *, limit=50, cursor=None):
        repo = logical_id(repo)
        purpose = "repository-acl:" + str(repo)
        last = self.pagination.decode(context, purpose, cursor, limit)

        def operation(c, checked):
            self._row(c, checked, repo, "acl")
            query = (
                sa.select(repository_acl.c.principal_id, repository_acl.c.role)
                .where(repository_acl.c.repository_id == repo)
                .order_by(repository_acl.c.principal_id)
                .limit(limit + 1)
            )
            if last is not None:
                query = query.where(repository_acl.c.principal_id > last)
            return self.pagination.page(
                checked,
                purpose,
                c.execute(query).all(),
                limit,
                key=lambda row: row.principal_id,
                serialize=lambda row: {"principal_id": str(row.principal_id), "role": row.role},
            )

        return self._run(context, trace, "acl", operation)
