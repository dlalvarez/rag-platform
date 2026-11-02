"""Selection guards execute before loading Qwen or opening credentials."""

import importlib
import json
from copy import deepcopy

import pytest
from test_f05_real_embedding_selection import fixture_data  # noqa: F401


@pytest.fixture
def selected(fixture_data, monkeypatch):  # noqa: F811
    source, manifest, actors, scope = fixture_data
    proof = {
        "profile": source.qwen_profile().fingerprint(),
        "records": source.selection(manifest, actors, scope),
    }
    module = importlib.import_module("f05_search_check")

    def private(path, _maximum):
        return json.dumps(manifest if str(path).endswith("manifest.json") else proof).encode()

    monkeypatch.setattr(module, "private_file", private)
    monkeypatch.setattr(module.Path, "read_text", lambda self: json.dumps({"fixtures": scope}))
    return module, manifest, proof, actors


def test_search_proof_selects_only_previously_published_fixture(selected):
    module, _manifest, proof, actors = selected
    assert module.selection() == (actors["alice"], proof["records"])


@pytest.mark.parametrize("drift", ["profile", "missing", "tenant", "document", "duplicate", "zero"])
def test_search_proof_rejects_drift_before_runtime(selected, drift):
    module, manifest, proof, _actors = selected
    if drift == "profile":
        proof["profile"] = "0" * 64
    elif drift == "missing":
        proof["records"].pop()
    elif drift == "tenant":
        proof["records"][0]["tenant"] = proof["records"][1]["tenant"]
    elif drift == "document":
        manifest["fixtures"][0]["documents"][0]["document"] = proof["records"][1]["document"]
    elif drift == "duplicate":
        proof["records"][1] = deepcopy(proof["records"][0])
    else:
        proof["records"][0]["space"] = "00000000-0000-0000-0000-000000000000"
    with pytest.raises((AssertionError, ValueError)):
        module.selection()
