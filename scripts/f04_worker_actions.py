"""Scoped operator actions for worker pause tests; no content or credentials in output."""

import argparse
import json
import logging
from pathlib import Path
from uuid import UUID, uuid4

import sqlalchemy as sa
from f01_daily import session
from f02_common import engine
from f02_testing import Humans
from f03_http_check import API
from f03_testing import Services, application, real_actors

from rag_platform.control.identity_admin import IdentityAdministration
from rag_platform.control.identity_models import Membership
from rag_platform.identity_api import private_file
from rag_platform.ingestion.document_state import DocumentStateService
from rag_platform.ingestion.schema import audit, documents

PHASE = "START"


def run():
    global PHASE
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=[
            "acl-revoke",
            "acl-restore",
            "membership-revoke",
            "membership-restore",
            "tombstone",
        ],
    )
    parser.add_argument("--fixture", choices=["same-a", "two-b"], required=True)
    args = parser.parse_args()
    manifest = json.loads(private_file("/checks/manifest.json", 512 * 1024))
    fixture = next(f for f in manifest["fixtures"] if f["name"] == args.fixture)
    PHASE = args.action + "/" + args.fixture
    humans, api, control, admin = None, None, None, None
    try:
        humans = Humans()
        humans.ready()
        control = engine()
        actors = real_actors(control, humans)
        assert {key: str(value) for key, value in actors.items()} == manifest["actors"]
        tenant, repo = UUID(fixture["tenant"]), UUID(fixture["repository"])
        api = API(humans)
        scope = json.loads(
            (Path(__file__).resolve().parents[1] / "ops/f03/application-scope.json").read_text()
        )["fixtures"]
        expected = next(f for f in scope if f["name"] == args.fixture)
        assert fixture["tenant"] == expected["tenant"]
        base = f"/api/v1/tenants/{tenant}/repositories/{repo}"
        owned = api.json("alice", "GET", base)["repository"]
        expected_name = "f04-worker-" + args.fixture + "-" + UUID(manifest["run_id"]).hex[:12]
        assert owned["owner_id"] == str(actors["alice"]) and owned["name"] == expected_name
        if args.action.startswith("acl-"):
            path = f"/api/v1/tenants/{tenant}/repositories/{repo}/acl/{actors['bob']}"
            if args.action == "acl-revoke":
                api.json("alice", "DELETE", path)
            else:
                api.json("alice", "PUT", path, value={"role": "editor"})
        elif args.action.startswith("membership-"):
            admin = engine("admin")
            with admin.connect() as c:
                before = c.execute(
                    sa.select(Membership.role, Membership.state).where(
                        Membership.user_id == actors["bob"], Membership.tenant_id == tenant
                    )
                ).one()
            wanted = "REVOKED" if args.action == "membership-revoke" else "ACTIVE"
            prior = "ACTIVE" if wanted == "REVOKED" else "REVOKED"
            assert tuple(before) == ("editor", prior)
            result = IdentityAdministration(admin, actors["alice"], uuid4()).membership(
                tenant, actors["bob"], "editor", wanted
            )
            assert result["state"] == wanted and result["role"] == "editor"
        else:
            item = next(i for i in fixture["documents"] if i["case"] == "tombstone")
            doc = UUID(item["document"])
            with session() as (day, _, _), application(day) as store:
                with Services(store=store, profile="ingestion") as services:
                    trace = uuid4()
                    context = services.authority.authorize(actors["alice"], tenant, trace)
                    with services.connections.connection(context, trace) as c:
                        assert (
                            c.scalar(
                                sa.select(documents.c.repository_id).where(documents.c.id == doc)
                            )
                            == repo
                        )
                    delete = DocumentStateService(services.repositories)
                    first = delete.delete(context, trace, doc)
                    second = delete.delete(context, trace, doc)
                    assert first == second == {"document_id": str(doc), "state": "TOMBSTONED"}
                    with services.connections.connection(context, trace) as c:
                        assert (
                            c.scalar(
                                sa.select(sa.func.count())
                                .select_from(audit)
                                .where(
                                    audit.c.target_id == doc,
                                    audit.c.action == "DOCUMENT_TOMBSTONED",
                                )
                            )
                            == 1
                        )
            original = f"/api/v1/tenants/{tenant}/repositories/{repo}/documents/{doc}/original"
            api.json("alice", "GET", original, expected=404)
        print(
            "PASS T005 ACTION: "
            + args.action.upper()
            + " scoped to synthetic fixture; resources retained."
        )
    finally:
        if admin is not None:
            admin.dispose()
        if control is not None:
            control.dispose()
        if api is not None:
            api.close()
        if humans is not None:
            humans.close()


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    try:
        run()
    except Exception as error:
        print("F04-T005 ACTION/" + PHASE + " " + type(error).__name__ + " REFUSED")
        raise SystemExit(1) from None
