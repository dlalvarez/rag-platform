"""The opt-in proof selects only authenticated retained atomic fixtures."""

import importlib
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest


@pytest.fixture
def fixture_data(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    module = importlib.import_module("f05_real_embedding_check")
    actors = {"alice": uuid4(), "bob": uuid4()}
    scope = [
        {"name": name, "tenant": str(uuid4())} for name in ("same-a", "same-b", "two-a", "two-b")
    ]
    manifest = {
        "actors": {k: str(v) for k, v in actors.items()},
        "fixtures": [
            dict(
                row,
                repository=str(uuid4()),
                documents=[
                    dict(
                        case="atomic",
                        actor="alice",
                        document=str(uuid4()),
                        original=str(uuid4()),
                        mime="text/plain",
                        sha256="a" * 64,
                        byte_size=64,
                    )
                ],
            )
            for row in scope
        ],
    }
    return module, manifest, actors, scope


def test_selection_is_repeatable_and_contains_no_document_content(fixture_data):
    module, manifest, actors, scope = fixture_data
    before = deepcopy(manifest)
    first = module.selection(manifest, actors, scope)
    assert first == module.selection(manifest, actors, scope)
    assert manifest == before and len(first) == 4
    assert len({r["intent"] for r in first}) == 4
    assert not any("text" in r or "body" in r for r in first)


@pytest.mark.parametrize(
    "drift",
    [
        "actor_identity",
        "tenant",
        "missing_fixture",
        "missing_atomic",
        "duplicate_atomic",
        "wrong_actor",
        "zero_document",
        "duplicate_document",
    ],
)
def test_selection_refuses_fixture_drift_before_request(fixture_data, drift):
    module, manifest, actors, scope = fixture_data
    fixtures = manifest["fixtures"]
    if drift == "actor_identity":
        manifest["actors"]["alice"] = str(uuid4())
    elif drift == "tenant":
        fixtures[0]["tenant"] = str(uuid4())
    elif drift == "missing_fixture":
        fixtures.pop()
    elif drift == "missing_atomic":
        fixtures[0]["documents"][0]["case"] = "positive"
    elif drift == "duplicate_atomic":
        fixtures[0]["documents"].append(deepcopy(fixtures[0]["documents"][0]))
    elif drift == "wrong_actor":
        fixtures[0]["documents"][0]["actor"] = "bob"
    elif drift == "zero_document":
        fixtures[0]["documents"][0]["document"] = "00000000-0000-0000-0000-000000000000"
    elif drift == "duplicate_document":
        fixtures[1]["documents"][0]["document"] = fixtures[0]["documents"][0]["document"]
    with pytest.raises(ValueError):
        module.selection(manifest, actors, scope)
