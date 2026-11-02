"""Optional inference lock parity and private delivery consumer exclusion."""

import importlib.util
import json
import os
import time
import tomllib
from contextlib import contextmanager
from pathlib import Path

import pytest

from rag_platform.providers.application_handoff import lock_file, publish

ROOT = Path(__file__).resolve().parents[2]


def load_script(monkeypatch, name):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(
        "_test_" + name, ROOT / "scripts" / (name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_optional_worker_keeps_baseline_pins_and_cpu_profile_outside_api():
    main = tomllib.loads((ROOT / "pyproject.toml").read_text())
    inference = tomllib.loads((ROOT / "ops/f05/inference/pyproject.toml").read_text())
    worker = tomllib.loads((ROOT / "ops/f05/worker-inference/pyproject.toml").read_text())
    assert set(main["project"]["dependencies"]) <= set(worker["project"]["dependencies"])
    assert set(inference["project"]["dependencies"]) <= set(worker["project"]["dependencies"])
    baseline = tomllib.loads((ROOT / "uv.lock").read_text())["package"]
    optional = tomllib.loads((ROOT / "ops/f05/worker-inference/uv.lock").read_text())["package"]
    versions = {}
    for package in optional:
        versions.setdefault(package["name"], set()).add(package["version"])
    for package in baseline:
        if package["name"] in versions:
            assert versions[package["name"]] == {package["version"]}
    assert "torch" not in {p["name"] for p in baseline}
    assert versions["torch"] == {"2.7.1+cpu"}
    assert versions["transformers"] == {"4.51.3"}
    assert versions["tokenizers"] == {"0.21.4"}
    assert versions["safetensors"] == {"0.5.3"}
    assert not any(p["name"].startswith("nvidia-") for p in optional)


@pytest.fixture
def delivery(tmp_path, monkeypatch):
    host = load_script(monkeypatch, "f05_worker_host")
    path = tmp_path / "delivery"
    host.prepare(path)
    return host, path


def test_prepare_preserves_existing_private_lock_inodes(delivery):
    host, path = delivery
    before = {p.name: p.stat().st_ino for p in path.iterdir()}
    host.prepare(path)
    assert {p.name: p.stat().st_ino for p in path.iterdir()} == before
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in path.iterdir())


def test_status_exposes_expiry_and_busy_only_never_bearer(delivery):
    host, path = delivery
    now = time.time()
    publish(
        path, dict(version=1, token="PRIVATE_TEST_BEARER", issued_at=now, expires_at=now + 3000)
    )
    fd = lock_file(path / "consumer.lock")
    try:
        result = host.status(path)
        assert result["consumer_busy"] is True and result["file_state"] == "UNEXPIRED"
        assert "PRIVATE_TEST_BEARER" not in json.dumps(result)
        assert "token" not in result
    finally:
        os.close(fd)


def test_issuer_refuses_live_consumer_before_daily_access(delivery, monkeypatch):
    _host, path = delivery
    issuer = load_script(monkeypatch, "f05_application_issue")
    monkeypatch.setattr(issuer, "DELIVERY", path)
    monkeypatch.setattr(issuer, "session", lambda: pytest.fail("daily access"))
    fd = lock_file(path / "consumer.lock")
    try:
        with pytest.raises(BlockingIOError):
            issuer.issue(replace=True)
    finally:
        os.close(fd)


@pytest.mark.parametrize("fail", [False, True])
def test_issuer_holds_consumer_lock_and_releases_on_all_outcomes(delivery, monkeypatch, fail):
    _host, path = delivery
    issuer = load_script(monkeypatch, "f05_application_issue")
    monkeypatch.setattr(issuer, "DELIVERY", path)

    @contextmanager
    def session():
        yield object(), None, None

    def ensure(_day, actual_path, *, replace):
        assert actual_path == path and replace is True
        with pytest.raises(BlockingIOError):
            lock_file(path / "consumer.lock")
        if fail:
            raise RuntimeError("synthetic issuer failure")
        return {"state": "ACTIVE", "created": True}

    monkeypatch.setattr(issuer, "session", session)
    monkeypatch.setattr(issuer, "ensure", ensure)
    if fail:
        with pytest.raises(RuntimeError, match="synthetic issuer"):
            issuer.issue(replace=True)
    else:
        assert issuer.issue(replace=True) == {"state": "ACTIVE", "created": True}
    fd = lock_file(path / "consumer.lock")
    os.close(fd)
