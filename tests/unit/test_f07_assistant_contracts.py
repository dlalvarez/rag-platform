"""Private assistant bounds and default-deny ownership, without SQL or models."""

from dataclasses import FrozenInstanceError, replace
from uuid import UUID

import pytest

from rag_platform.assistants.contracts import (
    AssistantConfiguration,
    AssistantError,
    expected_revision,
    owner_allows,
)

OWNER = UUID(int=1)
OTHER = UUID(int=2)


def config(**changes):
    base = AssistantConfiguration(
        "Private assistant",
        "PRIVATE_PURPOSE",
        (UUID(int=3), UUID(int=2)),
        UUID(int=4),
        "a" * 64,
    )
    return replace(base, **changes)


def test_configuration_is_immutable_canonical_and_private():
    value = config()
    assert value.repository_ids == (UUID(int=2), UUID(int=3))
    assert value == config(repository_ids=(UUID(int=2), UUID(int=3)))
    assert "PRIVATE_PURPOSE" not in repr(value)
    assert "Private assistant" not in repr(value)
    with pytest.raises(FrozenInstanceError):
        value.purpose = "changed"


@pytest.mark.parametrize(
    "changes",
    [
        {"name": ""},
        {"name": " x"},
        {"name": "x "},
        {"name": "x" * 121},
        {"name": "cafe\u0301"},
        {"name": "x\n"},
        {"name": "x\u200b"},
        {"name": "\ud800"},
        {"purpose": "x" * 2001},
        {"purpose": "x\0"},
        {"purpose": "\udfff"},
        {"repository_ids": []},
        {"repository_ids": ()},
        {"repository_ids": (OWNER, OWNER)},
        {"repository_ids": (str(OWNER),)},
        {"repository_ids": (UUID(int=0),)},
        {"repository_ids": (True,)},
        {"repository_ids": tuple(UUID(int=i) for i in range(1, 18))},
        {"space_id": str(OWNER)},
        {"space_id": UUID(int=0)},
        {"generation_fingerprint": "A" * 64},
        {"generation_fingerprint": "a" * 63},
        {"generation_fingerprint": "http://model"},
        {"generation_fingerprint": None},
        {"top_k": 0},
        {"top_k": 9},
        {"top_k": True},
        {"top_k": 1.0},
    ],
)
def test_invalid_configuration_is_closed_without_private_error_text(changes):
    with pytest.raises(AssistantError, match="^INPUT_INVALID$"):
        config(**changes)


@pytest.mark.parametrize("role", ["owner", "admin", "editor", "reader"])
@pytest.mark.parametrize("action", ["read", "use", "create", "update", "delete"])
def test_explicit_owner_policy(role, action):
    expected = action in {"read", "use"} or role != "reader"
    assert owner_allows(role, OWNER, OWNER, action) is expected
    assert not owner_allows(role, OTHER, OWNER, action)


@pytest.mark.parametrize("role", ["platform_operator", "platform_support", "root", None, [], True])
def test_platform_or_unknown_roles_never_grant_content(role):
    assert not owner_allows(role, OWNER, OWNER, "use")


@pytest.mark.parametrize(
    "actor,owner,action",
    [
        (None, OWNER, "use"),
        (str(OWNER), str(OWNER), "use"),
        (UUID(int=0), UUID(int=0), "use"),
        (OWNER, OWNER, None),
        (OWNER, OWNER, []),
        (OWNER, OWNER, "acl"),
        (OWNER, OWNER, "execute"),
    ],
)
def test_invalid_ownership_or_action_denies(actor, owner, action):
    assert not owner_allows("owner", actor, owner, action)


@pytest.mark.parametrize("value", [0, -1, True, False, 1.0, "1", None, 2**63])
def test_revision_requires_positive_bounded_integer(value):
    with pytest.raises(AssistantError, match="^INPUT_INVALID$"):
        expected_revision(value)


def test_revision_boundary_and_empty_purpose_are_valid():
    assert expected_revision(1) == 1
    assert expected_revision(2**63 - 1) == 2**63 - 1
    assert config(purpose="", top_k=1).purpose == ""
