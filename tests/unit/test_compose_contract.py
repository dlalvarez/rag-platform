from pathlib import Path

import yaml

ROOT = Path(__file__).parents[2]


def test_v03_data_services_are_private_and_bind_paths_are_not_created():
    spec = yaml.safe_load((ROOT / "compose.yaml").read_text())
    for name in ("postgres", "minio"):
        service = spec["services"][name]
        assert "ports" not in service
        assert service["volumes"][0]["bind"]["create_host_path"] is False
    assert spec["services"]["api"]["ports"] == ["127.0.0.1:${RAG_API_PORT:-8000}:8000"]


def test_v03_versions_and_resource_limits():
    spec = yaml.safe_load((ROOT / "compose.yaml").read_text())
    for service in spec["services"].values():
        assert ":latest" not in service["image"]
        assert service["cpus"] <= 0.75
        assert "mem_limit" in service
    assert "@sha256:" in spec["services"]["postgres"]["image"]
