"""F03 ACL negative paths and cursor IDOR, independent of infrastructure credentials."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from rag_platform.documents.errors import DocumentError
from rag_platform.documents.pagination import Pagination
from rag_platform.documents.policy import (
    may_assign,
    name_and_config,
    repository_allows,
    target_allows,
    tenant_allows,
)


@pytest.mark.parametrize("role", ["reader", None, "", "platform_operator", "platform_support", {}])
@pytest.mark.parametrize("action", ["create", "update", "delete", "acl", "upload"])
def test_readonly_or_platform_role_never_grants_tenant_write(role, action):
    assert not tenant_allows(role, action)


@pytest.mark.parametrize("role", ["reader", "editor"])
@pytest.mark.parametrize("action", ["update", "delete", "acl"])
def test_content_roles_cannot_manage_repository(role, action):
    assert not repository_allows(role, action)


@pytest.mark.parametrize(
    "prior,target",
    [
        ("admin", "owner"),
        (None, "owner"),
        ("owner", "reader"),
        ("owner", None),
        ("admin", None),
        (None, "admin"),
    ],
)
def test_repository_admin_cannot_promote_or_modify_administrators(prior, target):
    assert not may_assign("admin", prior, target)


def test_explicit_repo_owner_and_limited_admin_changes():
    assert may_assign("owner", "admin", "owner")
    assert may_assign("admin", "editor", "reader")
    assert may_assign("admin", "reader", None)
    assert not may_assign("platform_operator", "reader", "owner")
    assert not may_assign("owner", "reader", {})
    assert not target_allows("editor", "owner")
    assert not target_allows("reader", "editor")
    assert target_allows("admin", "owner")  # repo ownership never changes tenant role


@pytest.mark.parametrize(
    "name,config",
    [
        ("", None),
        (" outside", None),
        ("outside ", None),
        ("line\nbreak", None),
        ("Cafe\u0301", None),
        ("a" * 121, None),
        (True, None),
        ("valid", {"language": "auto", "credentials": "synthetic-marker"}),
        ("valid", {"language": "../other"}),
        ("valid", {"language": None}),
        ("valid", {"language": True}),
        ("valid", []),
    ],
)
def test_invalid_metadata_rejected_without_echo(name, config):
    with pytest.raises(DocumentError, match="INPUT_INVALID") as error:
        name_and_config(name, config)
    assert "synthetic-marker" not in str(error.value)


def test_metadata_defaults_and_language_canonicalization():
    assert name_and_config("Privado", None) == ("Privado", {"language": "auto"})
    assert name_and_config("Café", {"language": "es-CO"}) == ("Café", {"language": "es-co"})


def context():
    return SimpleNamespace(principal_id=uuid4(), tenant_id=uuid4())


def test_cursor_cannot_cross_actor_tenant_or_collection():
    pagination, owner, last = Pagination(b"x" * 32), context(), uuid4()
    cursor = pagination.encode(owner, "repositories", last)
    assert pagination.decode(owner, "repositories", cursor, 1) == last
    candidates = [
        (SimpleNamespace(principal_id=uuid4(), tenant_id=owner.tenant_id), "repositories", cursor),
        (
            SimpleNamespace(principal_id=owner.principal_id, tenant_id=uuid4()),
            "repositories",
            cursor,
        ),
        (owner, "repository-acl:" + str(uuid4()), cursor),
        (owner, "repositories", ("A" if cursor[0] != "A" else "B") + cursor[1:]),
        (owner, "repositories", cursor + "="),
    ]
    for actor, purpose, value in candidates:
        with pytest.raises(DocumentError, match="INPUT_INVALID"):
            pagination.decode(actor, purpose, value, 1)


@pytest.mark.parametrize("limit", [0, -1, 101, True, "10", None])
def test_pagination_boundaries_rejected_before_query(limit):
    with pytest.raises(DocumentError, match="INPUT_INVALID"):
        Pagination(b"x" * 32).decode(context(), "repositories", None, limit)


def test_empty_page_has_no_cursor_and_unknown_error_is_closed():
    pagination, actor = Pagination(b"x" * 32), context()
    assert pagination.page(actor, "repositories", [], 50, key=lambda x: x, serialize=str) == {
        "items": [],
        "next_cursor": None,
    }
    error = DocumentError({"sensitive-provider-body": "synthetic-marker"})
    assert error.code == "DEPENDENCY_UNAVAILABLE" and error.status == 503
    assert "synthetic-marker" not in str(error)
