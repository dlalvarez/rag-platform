import importlib.util
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

SPEC = importlib.util.spec_from_file_location(
    "prepare", Path(__file__).parents[2] / "scripts/f00_prepare.py"
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_v03_prepare_refuses_existing_data(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    fixture = root / "keep"
    fixture.write_text("synthetic")
    with pytest.raises(ValueError):
        module.prepare(root, tmp_path / ".env")
    assert fixture.read_text() == "synthetic"


def test_v03_secrets_only_in_excluded_runtime_files(tmp_path):
    root = tmp_path / "data"
    env = tmp_path / ".env"
    module.prepare(root, env)
    assert str(root) in env.read_text()
    for secret in (root / "secrets").iterdir():
        assert len(secret.read_text()) == 48
        assert secret.read_text() not in env.read_text()
    with pytest.raises(ValueError):
        module.prepare(root, env)


def test_v03_missing_ext4_mount_fails_before_any_write():
    fake = subprocess.CompletedProcess([], 0, '{"filesystems":[{"target":"/","fstype":"ext4"}]}')
    with patch.object(module.subprocess, "run", return_value=fake):
        with pytest.raises(ValueError, match="ext4 mount"):
            module.validate_root(Path("/srv/rag-data/f00-test"), host=True)


@pytest.mark.parametrize("root", [Path("/"), Path("relative"), Path("/srv/rag-data/test")])
def test_v03_unsafe_local_root_is_refused(root):
    with pytest.raises(ValueError):
        module.validate_root(root, host=False)
