"""Trusted T004 component proof with real OIDC, limited AppRole and tenant SQL."""

import hashlib
import json
import logging
from contextlib import closing
from pathlib import Path
from uuid import UUID, uuid4

import sqlalchemy as sa
from f01_daily import session
from f01_operator import CA, ENDPOINT
from f02_common import engine
from f02_identity_admin import settings
from f02_testing import Humans
from f03_fixtures import ROOT, snapshot

from rag_platform.control.identity import AccessError, register
from rag_platform.control.identity_admin import IdentityAdministration
from rag_platform.control.identity_models import Membership, PlatformRole, TenantProfile, User
from rag_platform.documents.errors import DocumentError
from rag_platform.documents.repositories import RepositoryService
from rag_platform.documents.schema import audit_events, documents, repositories, repository_acl
from rag_platform.providers.application_secrets import ApplicationSecretStore
from rag_platform.providers.identity import OIDCVerifier
from rag_platform.tenancy.authorization import AuthorizedConnections, TenantAuthorizer
from rag_platform.tenancy.registry import ConnectionRegistry
from rag_platform.tenancy.resolver import CatalogResolver


class ProbeFailure(RuntimeError):
    pass


class Reads:
    def __init__(self, store):
        self.store, self.count = store, 0

    def read(self, ref):
        self.count += 1
        return self.store.read(ref)


def identity_snapshot(engine, owned):
    with engine.connect() as c:
        result = {}
        for model in (User, Membership, PlatformRole, TenantProfile):
            table = model.__table__
            query = sa.select(table)
            if "tenant_id" in table.c:
                query = query.where(table.c.tenant_id.not_in(owned))
            values = sorted(
                json.dumps(dict(r), sort_keys=True, default=str)
                for r in c.execute(query).mappings()
            )
            result[table.name] = hashlib.sha256("".join(values).encode()).digest()
        return result


def prove():
    humans = Humans()
    app_control, admin_control, catalog = engine(), engine("admin"), engine("migrator")
    registry = store = None
    phase = "IDENTITY"
    try:
        humans.ready()
        actors = {}
        with closing(OIDCVerifier(settings())) as verifier:
            for name in ("alice", "bob", "carol", "dave"):
                identity = verifier.verify(humans.tokens(name)["access_token"])
                actors[name] = register(app_control, identity, uuid4())
        owner = IdentityAdministration(admin_control, actors["alice"], uuid4())
        if "platform_operator" not in owner.me()["platform_roles"]:
            raise ProbeFailure("OPERATOR_FIXTURE_MISSING")
        scope = json.loads((ROOT / "ops/f03/application-scope.json").read_text())
        tenant_ids = [UUID(item["tenant"]) for item in scope["fixtures"]]
        with session() as (day, _, _):
            before = snapshot(catalog)
            identities_before = identity_snapshot(admin_control, tenant_ids)
            for tenant in tenant_ids:
                IdentityAdministration(admin_control, actors["alice"], uuid4()).bootstrap_owner(
                    tenant, actors["alice"], "ORG"
                )
                for name, role in (("bob", "editor"), ("carol", "reader"), ("dave", "admin")):
                    IdentityAdministration(admin_control, actors["alice"], uuid4()).membership(
                        tenant, actors[name], role
                    )
            role = day._request("GET", "/v1/auth/approle/role/f03-application/role-id")["data"][
                "role_id"
            ]
            issued = day._request(
                "POST", "/v1/auth/approle/role/f03-application/secret-id", json={}
            )["data"]["secret_id"]
            store = ApplicationSecretStore(ENDPOINT, CA)
            store.login(role, issued)
            del issued, role
            reads = Reads(store)
            key = Path("/run/secrets/api_authority_key").read_bytes()
            authority = TenantAuthorizer(app_control, key, profile="documents")
            registry = ConnectionRegistry(
                CatalogResolver(app_control, profile="documents"), reads, CA
            )
            connections = AuthorizedConnections(authority, registry)
            service = RepositoryService(connections, app_control, key)

            def request(name, tenant, method, *args, expected=None, cold=False, **kwargs):
                trace = uuid4()
                count = reads.count
                try:
                    context = authority.authorize(actors[name], tenant, trace)
                    result = getattr(service, method)(context, trace, *args, **kwargs)
                except (DocumentError, AccessError) as error:
                    if error.code != expected:
                        raise ProbeFailure("WRONG_DENIAL") from None
                    if cold and reads.count != count:
                        raise ProbeFailure("DENIAL_READ_SECRET") from None
                    return None
                if expected is not None:
                    raise ProbeFailure("DENIAL_NOT_ENFORCED")
                return result

            def seeded(name, tenant, label):
                page = request(name, tenant, "list", limit=100)
                existing = next((r for r in page["items"] if r["name"] == label), None)
                if existing:
                    return UUID(existing["repository_id"])
                # After an interrupted ownership probe the other authorized owner
                # may hold the seed; recover through audited ACL operations, never SQL bypass.
                other = "dave" if name == "alice" else "alice"
                alternate = request(other, tenant, "list", limit=100)
                existing = next((r for r in alternate["items"] if r["name"] == label), None)
                if existing:
                    repo = UUID(existing["repository_id"])
                    if existing["role"] != "owner":
                        raise ProbeFailure("SEED_OWNER_MISSING")
                    request(other, tenant, "set_acl", repo, actors[name], "owner")
                    return repo
                return UUID(request(name, tenant, "create", label)["repository_id"])

            result = []
            for fixture in scope["fixtures"]:
                tag = fixture["name"].upper().replace("-", "_")
                tenant = UUID(fixture["tenant"])
                phase = tag + "/SEED"
                repo = seeded("alice", tenant, "f03-" + fixture["name"] + "-a")
                second = seeded("alice", tenant, "f03-" + fixture["name"] + "-c")
                private = seeded("dave", tenant, "f03-" + fixture["name"] + "-b")
                # Normalize only these F03 fixtures using explicit repository ownership.
                request("alice", tenant, "set_acl", repo, actors["bob"], "editor")
                request("alice", tenant, "set_acl", repo, actors["carol"], "reader")
                request("alice", tenant, "set_acl", repo, actors["dave"], None)

                trace = uuid4()
                context = authority.authorize(actors["alice"], tenant, trace)
                with connections.connection(context, trace) as c:
                    original_documents = c.scalar(sa.select(sa.func.count()).select_from(documents))

                phase = tag + "/DENIALS"
                request("dave", tenant, "show", repo, expected="ROLE_DENIED")
                request("alice", tenant, "show", private, expected="ROLE_DENIED")
                request("carol", tenant, "show", repo)
                request("bob", tenant, "show", repo)
                request("carol", tenant, "create", "forbidden", expected="ROLE_DENIED", cold=True)
                request(
                    "bob", tenant, "update", repo, "forbidden", expected="ROLE_DENIED", cold=True
                )
                request(
                    "carol",
                    tenant,
                    "set_acl",
                    repo,
                    actors["carol"],
                    "owner",
                    expected="ROLE_DENIED",
                    cold=True,
                )
                request(
                    "alice", tenant, "set_acl", repo, actors["bob"], "owner", expected="ROLE_DENIED"
                )
                request(
                    "alice", tenant, "set_acl", repo, actors["alice"], None, expected="LAST_OWNER"
                )
                page = request("alice", tenant, "list", limit=1)
                if page["next_cursor"] is None:
                    raise ProbeFailure("CURSOR_MISSING")
                request(
                    "dave",
                    tenant,
                    "list",
                    cursor=page["next_cursor"],
                    expected="INPUT_INVALID",
                    cold=True,
                )
                other_tenant = next(item for item in tenant_ids if item != tenant)
                request(
                    "alice",
                    other_tenant,
                    "list",
                    cursor=page["next_cursor"],
                    expected="INPUT_INVALID",
                    cold=True,
                )
                request("alice", other_tenant, "show", repo, expected="ROLE_DENIED")
                next_page = request("alice", tenant, "list", limit=1, cursor=page["next_cursor"])
                if not next_page["items"] or (
                    next_page["items"][0]["repository_id"] == page["items"][0]["repository_id"]
                ):
                    raise ProbeFailure("CURSOR_DUPLICATE")

                phase = tag + "/ACL"
                request("alice", tenant, "set_acl", repo, actors["dave"], "admin")
                request(
                    "dave",
                    tenant,
                    "update",
                    repo,
                    "f03-" + fixture["name"] + "-a",
                    {"language": "es"},
                )
                request(
                    "dave", tenant, "set_acl", repo, actors["dave"], "owner", expected="ROLE_DENIED"
                )
                request(
                    "dave",
                    tenant,
                    "set_acl",
                    repo,
                    actors["alice"],
                    "reader",
                    expected="ROLE_DENIED",
                )
                request("dave", tenant, "set_acl", repo, actors["bob"], "reader")
                request("alice", tenant, "set_acl", repo, actors["bob"], "editor")
                request("alice", tenant, "set_acl", repo, actors["dave"], "owner")
                request("alice", tenant, "set_acl", repo, actors["alice"], None)
                request("alice", tenant, "show", repo, expected="ROLE_DENIED")
                request("dave", tenant, "set_acl", repo, actors["alice"], "owner")
                request("dave", tenant, "set_acl", repo, actors["dave"], "admin")
                request("alice", tenant, "set_acl", repo, actors["dave"], None)
                row = request("alice", tenant, "show", repo)
                if row["owner_id"] != str(actors["alice"]):
                    raise ProbeFailure("OWNER_NOT_RECONCILED")

                phase = tag + "/REVALIDATE"
                trace = uuid4()
                stale = authority.authorize(actors["bob"], tenant, trace)
                try:
                    IdentityAdministration(admin_control, actors["alice"], uuid4()).membership(
                        tenant, actors["bob"], "editor", "SUSPENDED"
                    )
                    count = reads.count
                    try:
                        service.show(stale, trace, repo)
                    except AccessError as error:
                        if error.code != "MEMBERSHIP_REQUIRED":
                            raise ProbeFailure("WRONG_DENIAL") from None
                    else:
                        raise ProbeFailure("STALE_MEMBERSHIP_ACCEPTED")
                    if reads.count != count:
                        raise ProbeFailure("DENIAL_READ_SECRET")
                finally:
                    IdentityAdministration(admin_control, actors["alice"], uuid4()).membership(
                        tenant, actors["bob"], "editor", "ACTIVE"
                    )

                phase = tag + "/CRUD"
                temporary = UUID(
                    request("alice", tenant, "create", "f03-temporary-" + uuid4().hex)[
                        "repository_id"
                    ]
                )
                request(
                    "alice",
                    tenant,
                    "update",
                    temporary,
                    "f03-retained-" + temporary.hex,
                    {"language": "en"},
                )
                request("alice", tenant, "delete", temporary)
                request("alice", tenant, "show", temporary, expected="ROLE_DENIED")
                trace = uuid4()
                context = authority.authorize(actors["alice"], tenant, trace)
                with connections.connection(context, trace) as c:
                    if (
                        c.scalar(
                            sa.select(repositories.c.state).where(repositories.c.id == temporary)
                        )
                        != "DELETED"
                    ):
                        raise ProbeFailure("SOFT_DELETE_FAILED")
                    if (
                        c.scalar(
                            sa.select(sa.func.count())
                            .select_from(repository_acl)
                            .where(repository_acl.c.repository_id == temporary)
                        )
                        != 1
                    ):
                        raise ProbeFailure("ACL_HISTORY_LOST")
                    if (
                        c.scalar(
                            sa.select(sa.func.count())
                            .select_from(audit_events)
                            .where(
                                audit_events.c.target_id == temporary,
                                audit_events.c.action == "REPOSITORY_DELETED",
                            )
                        )
                        != 1
                    ):
                        raise ProbeFailure("AUDIT_MISSING")
                    if (
                        c.scalar(sa.select(sa.func.count()).select_from(documents))
                        != original_documents
                    ):
                        raise ProbeFailure("DOCUMENT_CREATED_BY_CRUD")
                result.append(
                    {
                        "name": fixture["name"],
                        "tenant": str(tenant),
                        "repository": str(repo),
                        "second": str(second),
                        "private": str(private),
                    }
                )
                print(f"PASS T004 {tag}: CRUD/ACL explícita; sin acceso por rol global/tenant.")
                print(f"PASS T004 {tag}: escalado/cursor/cruce denegados; membresía revalidada.")
                print(f"PASS T004 {tag}: owner reconciliado, baja lógica e historial/auditoría.")
            if (
                snapshot(catalog) != before
                or identity_snapshot(admin_control, tenant_ids) != identities_before
            ):
                raise ProbeFailure("LEGACY_CHANGED")
            print("PASS T004: AppRole limitado; fixtures y membresías previas conservadas.")
            print(
                "F03 REPO FIXTURES "
                + json.dumps({"version": 1, "fixtures": result}, sort_keys=True)
            )
    except (Exception, KeyboardInterrupt) as error:
        safe = {
            "OPERATOR_FIXTURE_MISSING",
            "WRONG_DENIAL",
            "DENIAL_READ_SECRET",
            "DENIAL_NOT_ENFORCED",
            "SEED_OWNER_MISSING",
            "CURSOR_MISSING",
            "CURSOR_DUPLICATE",
            "OWNER_NOT_RECONCILED",
            "STALE_MEMBERSHIP_ACCEPTED",
            "SOFT_DELETE_FAILED",
            "ACL_HISTORY_LOST",
            "AUDIT_MISSING",
            "DOCUMENT_CREATED_BY_CRUD",
            "LEGACY_CHANGED",
        }
        code = (
            str(error)
            if isinstance(error, ProbeFailure) and str(error) in safe
            else (error.code if isinstance(error, (DocumentError, AccessError)) else "REFUSED")
        )
        raise SystemExit(f"F03 T004 {phase}: {code}; sin detalles sensibles.") from None
    finally:
        try:
            if registry is not None:
                registry.close()
            if store is not None:
                store.revoke()
                store.close()
        finally:
            humans.close()
            for pool in (app_control, admin_control, catalog):
                pool.dispose()


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    prove()
