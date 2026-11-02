"""Adoption journals must never overwrite a prior or symlinked checkpoint."""

import importlib
from pathlib import Path

import pytest


@pytest.fixture(params=["f05_adopt", "f05_publication_adopt"])
def adopter(monkeypatch, tmp_path, request):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    module = importlib.import_module(request.param)
    monkeypatch.setattr(module, "OUT", tmp_path)
    return module


def test_checkpoint_repeat_and_conflict_preserve_original(adopter):
    adopter.save("same-a-before.json", {"fingerprint": "a" * 64})
    path = adopter.OUT / "same-a-before.json"
    before = path.read_bytes()
    adopter.save(path.name, {"fingerprint": "a" * 64})
    with pytest.raises(RuntimeError, match="CHECKPOINT_CONFLICT"):
        adopter.save(path.name, {"fingerprint": "b" * 64})
    assert path.read_bytes() == before
    assert path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("existing", [True, False])
def test_checkpoint_refuses_symlink_without_changing_target(adopter, existing):
    target = adopter.OUT / "retained"
    if existing:
        target.write_text("retained")
    path = adopter.OUT / "same-a-before.json"
    path.symlink_to(target)
    with pytest.raises((ValueError, OSError)):
        adopter.save(path.name, {"fingerprint": "a" * 64})
    assert path.is_symlink()
    assert target.read_text() == "retained" if existing else not target.exists()


def test_publication_adoption_requires_preflight_before_connecting(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    module = importlib.import_module("f05_publication_adopt")
    monkeypatch.setattr(module, "OUT", tmp_path)
    monkeypatch.setattr(module, "engine", lambda *_: pytest.fail("Unexpected database access"))
    with pytest.raises(ValueError, match="Invalid private API configuration"):
        module.run("adopt")
    with pytest.raises(ValueError, match="Unknown adoption mode"):
        module.run("unknown")
