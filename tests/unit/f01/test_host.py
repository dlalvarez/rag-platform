"""F01 guard checks must reject unsafe operations before touching Docker or data."""

import importlib.util
import json
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("f01_host", ROOT / "scripts/f01_host.py")
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)


def test_missing_data_mount_rejected(monkeypatch):
    monkeypatch.setattr(
        host.subprocess,
        "check_output",
        lambda *a, **k: json.dumps({"filesystems": [{"target": "/", "fstype": "ext4"}]}),
    )
    with pytest.raises(ValueError, match="mounted"):
        host.validate_host()


def test_existing_data_never_overwritten(monkeypatch, tmp_path):
    monkeypatch.setattr(host, "DATA", tmp_path)
    monkeypatch.setattr(host, "ENV", tmp_path / ".env.f01")
    monkeypatch.setattr(host, "validate_host", lambda **kw: None)
    marker = tmp_path / "preserve"
    marker.write_text("synthetic-existing-data")
    with pytest.raises(ValueError, match="overwritten"):
        host.prepare()
    assert marker.read_text() == "synthetic-existing-data"


@pytest.mark.parametrize(
    "arguments", [["down", "-v"], ["down", "--volumes"], ["up", "--remove-orphans"]]
)
def test_destructive_flags_rejected_before_docker(arguments):
    with pytest.raises(ValueError, match="not allowed"):
        host.compose(arguments)


def test_f01_has_no_host_ports_and_separate_internal_network():
    config = yaml.safe_load((ROOT / "ops/f01/compose.yaml").read_text())
    assert config["networks"]["f01"]["internal"] is True
    assert all(not service.get("ports") for service in config["services"].values())
    assert "/usr/bin/bao" in config["services"]["openbao"]["entrypoint"]
    assert config["services"]["openbao"]["command"][0] == "server"
    assert "-dev" not in config["services"]["openbao"]["command"]
    assert config["services"]["openbao"]["memswap_limit"] == "768m"
    assert config["services"]["tools"]["ulimits"]["core"]["hard"] == 0
    hba = (ROOT / "ops/f01/pg_hba.conf").read_text()
    assert "hostnossl all all all reject" in hba
