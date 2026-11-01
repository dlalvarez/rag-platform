"""Real additive identity migration/privilege/concurrency probe. No secret output."""

import hashlib
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import sqlalchemy as sa
from f02_common import NAMES, connect, credential, engine
from psycopg import sql
from sqlalchemy.exc import DBAPIError

from rag_platform.control.identity import AccessError, register
from rag_platform.control.identity_models import IdentityBase, Membership, TenantProfile, User
from rag_platform.control.migrations import upgrade_control, upgrade_identity
from rag_platform.control.models import Base, Tenant
from rag_platform.providers.identity import Identity

ROOT = Path(__file__).resolve().parents[1]
MARKER = "rag-platform/F02/identity-role/v1"
PHASE = "START"


def snapshot(connection):
    result = {}
    for name in Base.metadata.tables:
        rows = connection.execute(sa.text('SELECT to_jsonb(t) FROM "' + name + '" t')).scalars()
        canonical = sorted(json.dumps(row, sort_keys=True) for row in rows)
        result[name] = hashlib.sha256("".join(canonical).encode()).digest()
    return result


def bootstrap_roles():
    with connect("bootstrap") as connection:
        # Suppress SQL statement/error echo for this private bootstrap session only.
        connection.execute("SET LOCAL log_statement='none'")
        connection.execute("SET LOCAL log_min_error_statement='PANIC'")
        for role in ("app", "admin"):
            user, password = credential(role)
            record = connection.execute(
                "SELECT r.rolsuper,r.rolcreatedb,r.rolcreaterole,r.rolreplication,"
                "r.rolbypassrls,r.rolcanlogin,r.rolinherit,"
                "shobj_description(r.oid,'pg_authid') FROM pg_roles r WHERE rolname=%s",
                (user,),
            ).fetchone()
            if record is None:
                connection.execute(
                    sql.SQL(
                        "CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE "
                        "NOREPLICATION NOBYPASSRLS PASSWORD {}"
                    ).format(sql.Identifier(user), sql.Literal(password))
                )
                connection.execute(
                    sql.SQL("COMMENT ON ROLE {} IS {}").format(
                        sql.Identifier(user), sql.Literal(MARKER)
                    )
                )
            elif record != (False, False, False, False, False, True, False, MARKER):
                raise RuntimeError("ROLE_OWNERSHIP")
            if connection.execute(
                "SELECT count(*) FROM pg_auth_members WHERE member=(SELECT oid "
                "FROM pg_roles WHERE rolname=%s)",
                (user,),
            ).fetchone()[0]:
                raise RuntimeError("ROLE_MEMBERSHIP")
            connection.execute(
                sql.SQL("GRANT CONNECT ON DATABASE rag_control TO {}").format(sql.Identifier(user))
            )
            connection.execute(
                sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(user))
            )


def grants():
    with connect("bootstrap") as connection:
        for name in IdentityBase.metadata.tables:
            connection.execute(
                sql.SQL("REVOKE ALL ON TABLE {} FROM PUBLIC").format(sql.Identifier(name))
            )
        for role in ("app", "admin"):
            user = sql.Identifier(NAMES[role][0])
            tables = [
                "users",
                "memberships",
                "platform_roles",
                "tenant_profiles",
                "tenants",
                "instances",
                "db_locations",
                "storage_locations",
            ]
            connection.execute(
                sql.SQL("GRANT SELECT ON {} TO {}").format(
                    sql.SQL(",").join(map(sql.Identifier, tables)), user
                )
            )
            connection.execute(
                sql.SQL("GRANT INSERT(id,issuer,oidc_subject) ON users TO {}").format(user)
            )
            connection.execute(
                sql.SQL(
                    "GRANT INSERT(id,request_id,principal_id,target_user_id,tenant_id,"
                    "event_code,outcome,reason) ON identity_audit TO {}"
                ).format(user)
            )
        user = sql.Identifier(NAMES["admin"][0])
        connection.execute(sql.SQL("GRANT SELECT ON identity_audit TO {}").format(user))
        connection.execute(sql.SQL("GRANT UPDATE(state) ON users TO {}").format(user))
        connection.execute(
            sql.SQL("GRANT INSERT ON memberships,platform_roles,tenant_profiles TO {}").format(user)
        )
        connection.execute(sql.SQL("GRANT UPDATE(role,state) ON memberships TO {}").format(user))
        connection.execute(sql.SQL("GRANT UPDATE(state) ON platform_roles TO {}").format(user))
        connection.execute(sql.SQL("GRANT UPDATE(kind) ON tenant_profiles TO {}").format(user))


def rejected(connection, statement, values=None, state="42501"):
    try:
        with connection.begin_nested():
            connection.execute(sa.text(statement), values or {})
    except DBAPIError as error:
        if getattr(error.orig, "sqlstate", None) != state:
            raise RuntimeError("WRONG_DENIAL") from None
    else:
        raise RuntimeError("WRONG_ACCEPT")


def run():
    global PHASE
    engines = {}
    try:
        PHASE = "MIGRATION"
        engines["migrator"] = engine("migrator")
        migration = engines["migrator"]
        with migration.connect() as connection:
            before = snapshot(connection)
        with migration.begin() as connection:
            upgrade_identity(connection, ROOT)
        with migration.begin() as connection:
            upgrade_identity(connection, ROOT)
            upgrade_control(connection, ROOT)
            assert (
                connection.scalar(sa.text("SELECT version_num FROM alembic_version_control"))
                == "f02_control_0005"
            )
            assert snapshot(connection) == before
        PHASE = "GRANTS"
        bootstrap_roles()
        grants()
        engines["app"], engines["admin"] = engine("app"), engine("admin")
        app, admin = engines["app"], engines["admin"]
        PHASE = "IDENTITY"
        identity = Identity(
            "https://synthetic-f02.invalid/one", "catalog-probe", int(time.time()) + 600
        )
        user = register(app, identity, uuid4())
        assert register(app, identity, uuid4()) == user
        other = register(
            app,
            Identity("https://synthetic-f02.invalid/two", "catalog-probe", int(time.time()) + 600),
            uuid4(),
        )
        assert user != other
        concurrent = Identity(
            "https://synthetic-f02.invalid/one", "concurrent-probe", int(time.time()) + 600
        )
        with ThreadPoolExecutor(max_workers=8) as pool:
            values = list(pool.map(lambda _: register(app, concurrent, uuid4()), range(12)))
        assert len(set(values)) == 1
        PHASE = "CONSTRAINTS"
        with migration.begin() as connection:
            with connection.begin_nested() as fixture:
                tenants = [uuid4(), uuid4()]
                for tenant in tenants:
                    connection.execute(
                        sa.insert(Tenant).values(id=tenant, desired_version="f01_tenant_0001")
                    )
                connection.execute(
                    sa.insert(TenantProfile),
                    [
                        {"tenant_id": tenants[0], "kind": "PERSONAL"},
                        {"tenant_id": tenants[1], "kind": "ORG"},
                    ],
                )
                connection.execute(
                    sa.insert(Membership),
                    [
                        {"user_id": user, "tenant_id": tenants[0], "role": "owner"},
                        {"user_id": user, "tenant_id": tenants[1], "role": "reader"},
                    ],
                )
                roles = (
                    connection.execute(
                        sa.select(Membership.role).where(
                            Membership.user_id == user, Membership.tenant_id.in_(tenants)
                        )
                    )
                    .scalars()
                    .all()
                )
                assert set(roles) == {"owner", "reader"}
                params = {"u": user, "t": tenants[0]}
                for query, state in (
                    (
                        "INSERT INTO memberships(user_id,tenant_id,role) VALUES(:u,:t,'reader')",
                        "23505",
                    ),
                    ("UPDATE memberships SET role='root' WHERE user_id=:u", "23514"),
                    ("UPDATE memberships SET state='JWT_ADMIN' WHERE user_id=:u", "23514"),
                    ("UPDATE tenant_profiles SET kind='INFERRED' WHERE tenant_id=:t", "23514"),
                ):
                    rejected(connection, query, params, state)
                rejected(
                    connection,
                    "INSERT INTO memberships(user_id,tenant_id,role) VALUES(:u,:t,'reader')",
                    {"u": uuid4(), "t": tenants[0]},
                    "23503",
                )
                fixture.rollback()
        PHASE = "PRIVILEGES"
        with app.begin() as connection:
            assert connection.scalar(
                sa.text("SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()")
            )
            assert (
                connection.scalar(
                    sa.text(
                        "SELECT count(*) FROM pg_database WHERE datname LIKE 'rag_t_%' "
                        "AND has_database_privilege(current_user,oid,'CONNECT')"
                    )
                )
                == 0
            )
            for query in (
                "UPDATE users SET state='SUSPENDED' WHERE id=:u",
                "UPDATE users SET issuer='https://forged' WHERE id=:u",
                "INSERT INTO memberships(user_id,tenant_id,role) VALUES(:u,:t,'owner')",
                "INSERT INTO platform_roles(user_id,role) VALUES(:u,'platform_operator')",
                "UPDATE identity_audit SET outcome='OK'",
                "DELETE FROM identity_audit",
                "SELECT * FROM provisioning_operations",
                "CREATE TABLE f02_unapproved_table(id integer)",
            ):
                rejected(connection, query, {"u": user, "t": uuid4()})
        PHASE = "SUSPENSION"
        try:
            with admin.begin() as connection:
                connection.execute(sa.update(User).where(User.id == user).values(state="SUSPENDED"))
            try:
                register(app, identity, uuid4())
            except AccessError as error:
                assert error.code == "IDENTITY_SUSPENDED"
            else:
                raise RuntimeError("SUSPENSION")
        finally:
            with admin.begin() as connection:
                connection.execute(sa.update(User).where(User.id == user).values(state="ACTIVE"))
        with admin.begin() as connection:
            rejected(
                connection, "UPDATE users SET oidc_subject='replacement' WHERE id=:u", {"u": user}
            )
            rejected(connection, "UPDATE identity_audit SET reason='NONE'")
            assert (
                connection.scalar(
                    sa.text(
                        "SELECT count(*) FROM identity_audit WHERE principal_id=:u "
                        "AND reason='IDENTITY_SUSPENDED'"
                    ),
                    {"u": user},
                )
                >= 1
            )
            assert (
                connection.scalar(
                    sa.select(sa.func.count())
                    .select_from(Membership)
                    .where(Membership.user_id.in_([user, other, values[0]]))
                )
                == 0
            )
        PHASE = "PRESERVATION"
        with migration.connect() as connection:
            assert snapshot(connection) == before
        print("PASS T003: additive/repeated control migration; F01 catalog rows preserved exactly.")
        print("PASS T003: issuer+sub stable; 12 attempts/8 workers, one identity; no auto roles.")
        print("PASS T003: roles/types/FK/uniqueness enforced in PostgreSQL; fixtures rolled back.")
        print("PASS T003: TLS/least privilege; append-only audit; suspension denied and restored.")
        print("T003: three catalog fixtures retained; no product users/API or F02 closure.")
    finally:
        for value in engines.values():
            value.dispose()


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    try:
        run()
    except Exception as error:
        state = getattr(getattr(error, "orig", None), "sqlstate", None)
        suffix = (
            " SQLSTATE " + state
            if isinstance(state, str) and len(state) == 5 and state.isalnum()
            else ""
        )
        closed = {
            "WRONG_DENIAL",
            "WRONG_ACCEPT",
            "ROLE_OWNERSHIP",
            "ROLE_MEMBERSHIP",
            "SUSPENSION",
            "PRIVATE_FILE",
        }
        detail = " " + str(error) if str(error) in closed else ""
        print("F02-T003 " + PHASE + suffix + detail + ": stopped; no sensitive details.")
        raise SystemExit(1) from None
