"""Request authorization, signed contexts and identity-only API boundaries."""

import json
import logging
import secrets
import ssl
import time
from contextlib import contextmanager
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from uuid import uuid4

import httpx
import jwt
import pytest
import sqlalchemy as sa
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, Request
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool

from rag_platform.control.identity import AccessError, register
from rag_platform.control.identity_models import Membership, TenantProfile, User
from rag_platform.control.migrations import upgrade_identity
from rag_platform.control.models import DbLocation, Instance, StorageLocation, Tenant
from rag_platform.identity_api import create_app
from rag_platform.providers.identity import Identity, OIDCSettings, OIDCVerifier
from rag_platform.tenancy.authorization import AuthorizedConnections

ROOT = Path(__file__).resolve().parents[3]
ISSUER = "https://idp.invalid/realms/api-fixture"
JWKS = ISSUER + "/protocol/openid-connect/certs"


@pytest.fixture(scope="module")
def key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def setup(key):
    e = sa.create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        hide_parameters=True,
    )
    with e.begin() as c:
        c.exec_driver_sql("PRAGMA foreign_keys=ON")
        upgrade_identity(c, ROOT)
    users = [
        register(e, Identity(ISSUER, n, int(time.time()) + 300), uuid4())
        for n in ("alice-private", "bob-private", "dave-private")
    ]
    tenants = [uuid4(), uuid4()]
    instance = uuid4()
    with e.begin() as c:
        c.execute(
            sa.insert(Instance).values(
                id=instance,
                host="synthetic.invalid",
                admin_secret_ref=uuid4(),
                admin_secret_version=1,
            )
        )
        for tenant, role in zip(tenants, ("owner", "reader"), strict=True):
            c.execute(
                sa.insert(Tenant).values(
                    id=tenant,
                    state="READY",
                    migration_state="READY",
                    desired_version="f01_tenant_0001",
                    observed_version="f01_tenant_0001",
                )
            )
            c.execute(sa.insert(TenantProfile).values(tenant_id=tenant, kind="PERSONAL"))
            c.execute(
                sa.insert(DbLocation).values(
                    tenant_id=tenant,
                    instance_id=instance,
                    db_name="rag_t_" + tenant.hex,
                    app_secret_ref=uuid4(),
                    app_secret_version=1,
                    migrator_secret_ref=uuid4(),
                    migrator_secret_version=1,
                    readonly_secret_ref=uuid4(),
                    readonly_secret_version=1,
                )
            )
            c.execute(
                sa.insert(StorageLocation).values(
                    tenant_id=tenant,
                    endpoint="synthetic.invalid",
                    bucket="fixture-" + tenant.hex,
                    credential_ref=uuid4(),
                    credential_version=1,
                )
            )
            c.execute(
                sa.insert(Membership).values(
                    user_id=users[0],
                    tenant_id=tenant,
                    role=role,
                )
            )
        c.execute(
            sa.insert(Membership).values(
                user_id=users[1],
                tenant_id=tenants[0],
                role="reader",
            )
        )
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))

    def transport(request):
        if str(request.url).endswith("openid-configuration"):
            return httpx.Response(200, json={"issuer": ISSUER, "jwks_uri": JWKS})
        return httpx.Response(200, json={"keys": [{**jwk, "kid": "fixture", "alg": "RS256"}]})

    verifier = OIDCVerifier(
        OIDCSettings(
            ISSUER, "rag-api", JWKS, Path(ssl.get_default_verify_paths().cafile), leeway=0
        ),
        transport=httpx.MockTransport(transport),
    )
    secret = secrets.token_bytes(32)
    app = create_app(e, verifier, secret)

    def token(subject="alice-private", **changes):
        claims = dict(
            iss=ISSUER,
            sub=subject,
            aud="rag-api",
            exp=int(time.time()) + 300,
            iat=int(time.time()),
            typ="Bearer",
        )
        claims.update(changes)
        return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "fixture"})

    with TestClient(app) as client:
        yield e, users, tenants, app, client, token, secret
    verifier.close()
    e.dispose()


def test_views_roles_pagination_and_no_private_catalog(setup):
    e, users, tenants, app, client, token, secret = setup
    headers = {
        "Authorization": "Bearer " + token(roles=["platform_operator"], tenant_id=str(uuid4()))
    }
    me = client.get("/api/v1/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["principal_id"] == str(users[0])
    assert me.json()["platform_roles"] == []
    assert {x["role"] for x in me.json()["memberships"]} == {"owner", "reader"}
    page = client.get("/api/v1/tenants?limit=1", headers=headers).json()
    assert len(page["items"]) == 1 and page["next_cursor"]
    second = client.get(
        "/api/v1/tenants", params={"cursor": page["next_cursor"], "limit": 1}, headers=headers
    ).json()
    assert len(second["items"]) == 1 and not second["next_cursor"]
    assert page["items"][0]["tenant_id"] != second["items"][0]["tenant_id"]
    body = me.text + json.dumps(page) + json.dumps(second)
    assert all(
        value not in body
        for value in (
            "alice-private",
            ISSUER,
            "rag_t_",
            "secret_ref",
            "synthetic.invalid",
            "Bearer",
        )
    )
    assert me.headers["cache-control"] == "no-store"
    dave = client.get("/api/v1/me", headers={"Authorization": "Bearer " + token("dave-private")})
    assert dave.json()["memberships"] == []


def test_cursor_bound_to_identity_and_query_errors_never_echo(setup):
    e, users, tenants, app, client, token, secret = setup
    bearer = token()
    headers = {"Authorization": "Bearer " + bearer}
    cursor = client.get("/api/v1/tenants?limit=1", headers=headers).json()["next_cursor"]
    other = client.get(
        "/api/v1/tenants",
        params={"cursor": cursor},
        headers={"Authorization": "Bearer " + token("bob-private")},
    )
    assert other.status_code == 422
    for params in (
        {"cursor": bearer},
        {"limit": "101"},
        {"limit": "0"},
        {"limit": bearer},
        {"tenant_id": str(tenants[1])},
    ):
        response = client.get("/api/v1/tenants", headers=headers, params=params)
        assert response.status_code == 422
        assert bearer not in response.text
    assert client.get("/api/v1/tenants?limit=1&limit=2", headers=headers).status_code == 422


@pytest.mark.parametrize(
    "changes",
    [{"exp": 1}, {"aud": "wrong"}, {"iss": "https://wrong"}, {"typ": "ID"}, {"nbf": 2**40}],
)
def test_invalid_real_signed_access_token_api_denied(setup, changes, caplog):
    e, users, tenants, app, client, token, secret = setup
    bearer = token(**changes)
    caplog.set_level(logging.INFO, logger="rag_platform.identity")
    response = client.get("/api/v1/me", headers={"Authorization": "Bearer " + bearer})
    assert response.status_code == 401
    assert bearer not in response.text
    assert all(
        bearer not in record.getMessage() and "alice-private" not in record.getMessage()
        for record in caplog.records
        if record.name.startswith("rag_platform")
    )
    with e.connect() as c:
        assert c.scalar(sa.text("SELECT count(*) FROM identity_audit WHERE reason='TOKEN_INVALID'"))


def test_api_does_not_expose_administration_or_fixture_routes(setup):
    e, users, tenants, app, client, token, secret = setup
    assert client.get("/api/v1/me").status_code == 401
    assert client.get("/api/v1/tenants/" + str(tenants[0])).status_code == 404
    assert client.post("/api/v1/admin/tenants").status_code == 404
    assert client.get("/__test/context/" + str(tenants[0])).status_code == 404


def test_context_frozen_request_bound_and_before_connections(setup):
    e, users, tenants, app, client, token, secret = setup
    authority = app.state.authority
    trace = uuid4()
    context = authority.authorize(users[0], tenants[0], trace)
    with pytest.raises(FrozenInstanceError):
        context.tenant_id = tenants[1]
    calls = []

    class Registry:
        @contextmanager
        def connection(self, administrative, role):
            calls.append((administrative.tenant_id, role))
            yield "connection"

    boundary = AuthorizedConnections(authority, Registry())
    with boundary.connection(context, trace) as c:
        assert c == "connection"
    for altered in (
        replace(context, tenant_id=tenants[1]),
        replace(context, principal_id=users[1]),
        replace(context, roles=("admin",)),
        replace(context, db_ref=replace(context.db_ref, id=uuid4())),
        replace(context, storage_ref=replace(context.storage_ref, version=2)),
        replace(context, expires_at=int(time.time()) + 60),
    ):
        with pytest.raises(AccessError, match="INPUT_INVALID"):
            with boundary.connection(altered, trace):
                pytest.fail("Invalid proof reached data plane")
    with pytest.raises(AccessError, match="INPUT_INVALID"):
        with boundary.connection(context, uuid4()):
            pytest.fail("Context reused across requests")
    assert calls == [(tenants[0], "app")]
    reader = authority.authorize(users[0], tenants[1], trace)
    with boundary.connection(reader, trace):
        pass
    assert calls[-1] == (tenants[1], "readonly")


@pytest.mark.parametrize(
    "table,changes,code",
    [
        (User, {"state": "SUSPENDED"}, "IDENTITY_SUSPENDED"),
        (Membership, {"state": "REVOKED"}, "MEMBERSHIP_REQUIRED"),
        (Membership, {"state": "SUSPENDED"}, "MEMBERSHIP_REQUIRED"),
        (Tenant, {"state": "SUSPENDED"}, "TENANT_UNAVAILABLE"),
        (Tenant, {"observed_version": "incompatible"}, "TENANT_UNAVAILABLE"),
        (Tenant, {"migration_state": "MIGRATING"}, "TENANT_UNAVAILABLE"),
    ],
)
def test_revalidation_after_state_change_precedes_hot_pool(setup, table, changes, code):
    e, users, tenants, app, client, token, secret = setup
    authority, trace = app.state.authority, uuid4()
    context = authority.authorize(users[0], tenants[0], trace)
    with e.begin() as c:
        condition = (
            table.id == (users[0] if table is User else tenants[0])
            if table is not Membership
            else ((Membership.user_id == users[0]) & (Membership.tenant_id == tenants[0]))
        )
        c.execute(sa.update(table).where(condition).values(**changes))

    class NoRegistry:
        def connection(self, *args):
            pytest.fail("Denied request reached registry")

    with pytest.raises(AccessError, match=code):
        with AuthorizedConnections(authority, NoRegistry()).connection(context, trace):
            pytest.fail("State change ignored")


def test_dependency_fixture_path_rejects_cross_before_factory(setup):
    e, users, tenants, app, client, token, secret = setup
    authority = app.state.authority
    dependency = app.state.principal_dependency
    called = []

    @app.get("/__test/context/{tenant}")
    def route(tenant: str, request: Request, principal=Depends(dependency)):  # noqa: B008
        from uuid import UUID

        try:
            identifier = UUID(tenant)
        except ValueError:
            raise AccessError("INPUT_INVALID") from None
        context = authority.authorize(principal, identifier, request.state.trace_id)
        called.append(context.tenant_id)
        return {"tenant_id": str(context.tenant_id), "role": context.roles[0]}

    headers = {
        "Authorization": "Bearer "
        + token("bob-private", tenant_id=str(tenants[1]), roles=["owner"])
    }
    own = client.get("/__test/context/" + str(tenants[0]), headers=headers)
    assert own.json()["role"] == "reader"
    cross = client.get(
        "/__test/context/" + str(tenants[1]), headers={**headers, "X-Tenant-ID": str(tenants[0])}
    )
    assert cross.status_code == 403
    assert called == [tenants[0]]
    assert client.get("/__test/context/private-invalid", headers=headers).status_code == 422


def test_context_expiry_and_private_config_fail_closed(setup, monkeypatch, tmp_path):
    from rag_platform.identity_api import private_file

    e, users, tenants, app, client, token, secret = setup
    trace = uuid4()
    context = app.state.authority.authorize(users[0], tenants[0], trace)
    with monkeypatch.context() as patch:
        patch.setattr(
            "rag_platform.tenancy.authorization.time.time", lambda: context.expires_at + 1
        )
        with pytest.raises(AccessError, match="INPUT_INVALID"):
            app.state.authority.validate(context, trace)
    file = tmp_path / "private"
    file.write_bytes(b"x" * 32)
    file.chmod(0o600)
    assert private_file(file, 32) == b"x" * 32
    file.chmod(0o644)
    with pytest.raises(ValueError, match="Invalid private API configuration"):
        private_file(file, 32)
    file.chmod(0o600)
    link = tmp_path / "link"
    link.symlink_to(file)
    with pytest.raises(ValueError):
        private_file(link, 32)
    with pytest.raises(ValueError):
        private_file(file, 16)


def test_identity_dependency_unavailable_returns_503_without_registration(setup, caplog):
    from rag_platform.providers.identity import IdentityError

    e, users, tenants, app, client, token, secret = setup

    class UnavailableVerifier:
        def verify(self, bearer):
            raise IdentityError(unavailable=True)

    faulted = create_app(e, UnavailableVerifier(), secret)
    with e.connect() as c:
        before = c.scalar(sa.select(sa.func.count()).select_from(User))
    bearer = "synthetic-sensitive-bearer"
    caplog.set_level(logging.INFO, logger="rag_platform.identity")
    with TestClient(faulted) as http:
        response = http.get("/api/v1/me", headers={"Authorization": "Bearer " + bearer})
    assert response.status_code == 503
    assert response.json()["error"] == {"version": "v1", "code": "IDENTITY_UNAVAILABLE"}
    assert bearer not in response.text
    assert all(
        bearer not in r.getMessage() for r in caplog.records if r.name.startswith("rag_platform")
    )
    with e.connect() as c:
        assert c.scalar(sa.select(sa.func.count()).select_from(User)) == before
        assert (
            c.scalar(
                sa.text("SELECT count(*) FROM identity_audit WHERE reason='DEPENDENCY_UNAVAILABLE'")
            )
            >= 1
        )
