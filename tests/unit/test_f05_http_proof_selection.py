"""Retained worker/API fixtures share tenant/space, not necessarily repository."""

import sys
from pathlib import Path
from uuid import UUID, uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from f05_search_http_check import validate_retained  # noqa: E402


def records():
    first = [
        dict(
            name=name,
            tenant=str(uuid4()),
            repository=str(uuid4()),
            space=str(uuid4()),
            document=str(uuid4()),
            version=str(uuid4()),
            original=str(uuid4()),
        )
        for name in ("same-a", "same-b", "two-a", "two-b")
    ]
    retained = [
        {
            **r,
            "repository": str(uuid4()),
            "document": str(uuid4()),
            "version": str(uuid4()),
            "original": str(uuid4()),
        }
        for r in first
    ]
    return first, retained


def test_independent_repositories_in_same_scope_are_accepted():
    original, retained = records()
    validate_retained(original, retained)
    assert all(a["repository"] != b["repository"] for a, b in zip(original, retained, strict=True))


@pytest.mark.parametrize("field", ["tenant", "space", "name", "repository"])
def test_changed_scope_or_invalid_identity_is_refused(field):
    original, retained = records()
    retained[0][field] = "wrong" if field == "name" else str(uuid4())
    if field == "repository":
        retained[0][field] = str(UUID(int=0))
    with pytest.raises(ValueError):
        validate_retained(original, retained)


def test_missing_fixture_is_refused():
    original, retained = records()
    with pytest.raises(ValueError):
        validate_retained(original, retained[:-1])
