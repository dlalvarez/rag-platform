"""T002 SQL primitives. No destructive compensation and no secret-bearing errors."""

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import psycopg
from psycopg import sql

from rag_platform.providers.secrets import Credential

PROVISIONER = "f01_sql_provisioner"
TEMPLATE = "f01_vector_template"
TEMPLATE_MARKER = "rag-platform:f01:vector-template:v1"
VECTOR_VERSION = "0.8.7"


class SqlProvisioningError(RuntimeError):
    def __init__(self, code: str = "OWNERSHIP_CONFLICT"):
        super().__init__(code)


@dataclass(frozen=True)
class Names:
    tenant: UUID

    def __post_init__(self):
        if not isinstance(self.tenant, UUID):
            raise ValueError("An internal UUID is required")

    @property
    def database(self):
        return f"rag_t_{self.tenant.hex}"

    def role(self, kind: str):
        if kind not in ("owner", "migrator", "app", "readonly"):
            raise ValueError("Unknown SQL role")
        return f"{self.database}_{kind}"

    @property
    def marker(self):
        return f"rag-platform:f01:tenant:{self.tenant}"


@dataclass(frozen=True)
class Target:
    host: str
    port: int
    ca: Path

    def __post_init__(self):
        if (
            not self.host
            or any(c.isspace() for c in self.host)
            or "/" in self.host
            or type(self.port) is not int
            or not 1 <= self.port <= 65535
        ):
            raise ValueError("Invalid trusted SQL target")

    def connect(self, database: str, credential: Credential, *, autocommit=False):
        return psycopg.connect(
            host=self.host,
            port=self.port,
            dbname=database,
            user=credential.username,
            password=credential.password,
            sslmode="verify-full",
            sslrootcert=str(self.ca),
            connect_timeout=5,
            options=(
                "-c search_path=pg_catalog,public -c statement_timeout=10000 -c lock_timeout=3000"
            ),
            autocommit=autocommit,
        )


def execute(connection, statement: str, *identifiers: str):
    """Only module-owned SQL strings reach here; identifiers never use interpolation."""
    return connection.execute(sql.SQL(statement).format(*(sql.Identifier(i) for i in identifiers)))


def role_record(connection, name):
    return connection.execute(
        "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls, "
        "rolcanlogin, shobj_description(oid, 'pg_authid') FROM pg_roles WHERE rolname=%s",
        (name,),
    ).fetchone()


def database_record(connection, name):
    return connection.execute(
        "SELECT pg_get_userbyid(datdba), shobj_description(oid, 'pg_database'), "
        "datallowconn, datistemplate FROM pg_database WHERE datname=%s",
        (name,),
    ).fetchone()


def assert_role(connection, name, marker, *, login, administrative=False):
    record = role_record(connection, name)
    if record != (False, administrative, administrative, False, False, login, marker):
        raise SqlProvisioningError()


def create_role(connection, name, marker, password=None, *, administrative=False):
    # Transactional DDL: marker and password become visible with role creation.
    execute(
        connection,
        "CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
        "NOREPLICATION NOBYPASSRLS NOINHERIT",
        name,
    )
    connection.execute(
        sql.SQL("COMMENT ON ROLE {} IS {}").format(sql.Identifier(name), sql.Literal(marker))
    )
    if administrative:
        execute(connection, "ALTER ROLE {} CREATEDB CREATEROLE", name)
    if password is not None:
        # Send a SCRAM verifier, not a plaintext password in a SQL statement.
        verifier = connection.pgconn.encrypt_password(
            password.encode(), name.encode(), algorithm=b"scram-sha-256"
        ).decode()
        connection.execute(
            sql.SQL("ALTER ROLE {} LOGIN PASSWORD {}").format(
                sql.Identifier(name), sql.Literal(verifier)
            )
        )
    execute(connection, "ALTER ROLE {} SET search_path = pg_catalog, public", name)


def bootstrap(target: Target, bootstrap_credential: Credential, provisioner: Credential):
    """Explicit trusted per-instance bootstrap; only this function uses a superuser."""
    if provisioner.username != PROVISIONER:
        raise SqlProvisioningError()
    marker = "rag-platform:f01:sql-provisioner:v1"
    with target.connect("rag_control", bootstrap_credential, autocommit=True) as admin:
        # Session lock also serializes nontransactional CREATE DATABASE.
        admin.execute("SELECT pg_advisory_lock(71001, 2)")
        if role_record(admin, PROVISIONER) is None:
            with admin.transaction():
                create_role(admin, PROVISIONER, marker, provisioner.password, administrative=True)
        assert_role(admin, PROVISIONER, marker, login=True, administrative=True)
        execute(admin, "GRANT CONNECT ON DATABASE rag_control TO {}", PROVISIONER)
        record = database_record(admin, TEMPLATE)
        if record is None:
            execute(
                admin, "CREATE DATABASE {} TEMPLATE template0 ALLOW_CONNECTIONS false", TEMPLATE
            )
            admin.execute(
                sql.SQL("COMMENT ON DATABASE {} IS {}").format(
                    sql.Identifier(TEMPLATE), sql.Literal(TEMPLATE_MARKER)
                )
            )
        elif record[:2] != (bootstrap_credential.username, TEMPLATE_MARKER):
            raise SqlProvisioningError()
        execute(admin, "REVOKE ALL ON DATABASE {} FROM PUBLIC", TEMPLATE)
        # Only bootstrap can connect during inspection; no template0/template1 edits.
        execute(admin, "ALTER DATABASE {} ALLOW_CONNECTIONS true", TEMPLATE)
        try:
            with target.connect(TEMPLATE, bootstrap_credential) as template:
                template.execute("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public")
                vector = template.execute(
                    "SELECT extversion, pg_get_userbyid(extowner) FROM pg_extension "
                    "WHERE extname='vector' AND extnamespace='public'::regnamespace"
                ).fetchone()
                if vector != (VECTOR_VERSION, bootstrap_credential.username):
                    raise SqlProvisioningError("TEMPLATE_INCOMPATIBLE")
                template.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
                # The copied public schema must belong to the new database owner,
                # not to the bootstrap role.
                template.execute("ALTER SCHEMA public OWNER TO pg_database_owner")
                tables = template.execute(
                    "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','S')"
                ).fetchone()[0]
                if tables:
                    raise SqlProvisioningError("TEMPLATE_INCOMPATIBLE")
        finally:
            execute(admin, "ALTER DATABASE {} ALLOW_CONNECTIONS false", TEMPLATE)
        execute(admin, "ALTER DATABASE {} IS_TEMPLATE true", TEMPLATE)
        admin.execute("SELECT pg_advisory_unlock(71001, 2)")


def inspect_resources(connection, names: Names):
    """Refuse every unowned resource before applying grants or creating any roles."""
    for kind in ("owner", "migrator", "app", "readonly"):
        role = names.role(kind)
        if role_record(connection, role) is not None:
            assert_role(connection, role, names.marker, login=kind != "owner")
            memberships = connection.execute(
                "SELECT parent.rolname, m.admin_option, m.inherit_option, m.set_option "
                "FROM pg_auth_members m JOIN pg_roles parent ON parent.oid=m.roleid "
                "JOIN pg_roles child ON child.oid=m.member WHERE child.rolname=%s",
                (role,),
            ).fetchall()
            expected = [(names.role("owner"), False, False, True)] if kind == "migrator" else []
            if memberships != expected:
                raise SqlProvisioningError()
    db = database_record(connection, names.database)
    if db and (db[:2] != (names.role("owner"), names.marker) or db[3]):
        raise SqlProvisioningError()
    if db:
        grants = connection.execute(
            "SELECT acl.grantee, pg_get_userbyid(acl.grantee), acl.privilege_type "
            "FROM pg_database d CROSS JOIN LATERAL aclexplode("
            "COALESCE(d.datacl, acldefault('d', d.datdba))) acl WHERE d.datname=%s",
            (names.database,),
        ).fetchall()
        allowed = {names.role(kind) for kind in ("owner", "migrator", "app", "readonly")}
        for grantee, name, privilege in grants:
            if (grantee == 0 and db[2]) or (grantee != 0 and name not in allowed):
                raise SqlProvisioningError()
            if name in {names.role("app"), names.role("readonly"), names.role("migrator")}:
                if privilege != "CONNECT":
                    raise SqlProvisioningError()
    template = database_record(connection, TEMPLATE)
    if template != ("f01_bootstrap", TEMPLATE_MARKER, False, True):
        raise SqlProvisioningError("TEMPLATE_INCOMPATIBLE")


def provision_sql(
    target: Target, admin: Credential, names: Names, credentials: dict[str, Credential]
):
    """Bounded SQL step, not the T004 saga or a tenant READY transition."""
    if admin.username != PROVISIONER or set(credentials) != {"migrator", "app", "readonly"}:
        raise SqlProvisioningError()
    if any(value.username != names.role(kind) for kind, value in credentials.items()):
        raise SqlProvisioningError()
    with target.connect("rag_control", admin, autocommit=True) as connection:
        connection.execute("SELECT pg_advisory_lock(71002, hashtext(%s))", (str(names.tenant),))
        inspect_resources(connection, names)
        with connection.transaction():
            for kind in ("owner", "migrator", "app", "readonly"):
                if role_record(connection, names.role(kind)) is None:
                    create_role(
                        connection,
                        names.role(kind),
                        names.marker,
                        credentials[kind].password if kind != "owner" else None,
                    )
            # Explicit membership, no inheritance. CREATEROLE is administrative.
            execute(
                connection,
                "GRANT {} TO {} WITH ADMIN TRUE, INHERIT FALSE, SET TRUE",
                names.role("owner"),
                PROVISIONER,
            )
            execute(
                connection,
                "GRANT {} TO {} WITH ADMIN FALSE, INHERIT FALSE, SET TRUE",
                names.role("owner"),
                names.role("migrator"),
            )
        if database_record(connection, names.database) is None:
            execute(
                connection,
                "CREATE DATABASE {} OWNER {} TEMPLATE {} ALLOW_CONNECTIONS false",
                names.database,
                names.role("owner"),
                TEMPLATE,
            )
            execute(connection, "SET ROLE {}", names.role("owner"))
            try:
                connection.execute(
                    sql.SQL("COMMENT ON DATABASE {} IS {}").format(
                        sql.Identifier(names.database), sql.Literal(names.marker)
                    )
                )
            finally:
                connection.execute("RESET ROLE")
        # The DB was created with no connections; inherited template ACL is never assumed.
        execute(connection, "SET ROLE {}", names.role("owner"))
        try:
            execute(connection, "REVOKE ALL ON DATABASE {} FROM PUBLIC", names.database)
            for kind in ("migrator", "app", "readonly"):
                execute(
                    connection,
                    "GRANT CONNECT ON DATABASE {} TO {}",
                    names.database,
                    names.role(kind),
                )
            execute(connection, "ALTER DATABASE {} ALLOW_CONNECTIONS true", names.database)
        finally:
            connection.execute("RESET ROLE")
    # Configure via the limited migrator assuming only its own NOLOGIN owner.
    with target.connect(names.database, credentials["migrator"]) as connection:
        execute(connection, "SET ROLE {}", names.role("owner"))
        vector = connection.execute(
            "SELECT extversion, pg_get_userbyid(extowner) FROM pg_extension WHERE extname='vector'"
        ).fetchone()
        if vector != (VECTOR_VERSION, "f01_bootstrap"):
            raise SqlProvisioningError("TEMPLATE_INCOMPATIBLE")
        connection.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        for kind in ("app", "readonly"):
            execute(connection, "GRANT USAGE ON SCHEMA public TO {}", names.role(kind))
        execute(
            connection,
            "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public "
            "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}",
            names.role("owner"),
            names.role("app"),
        )
        execute(
            connection,
            "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public GRANT SELECT ON TABLES TO {}",
            names.role("owner"),
            names.role("readonly"),
        )
        execute(
            connection,
            "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public "
            "GRANT USAGE, SELECT ON SEQUENCES TO {}",
            names.role("owner"),
            names.role("app"),
        )
