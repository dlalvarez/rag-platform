"""Prove that documentation, lint and test gates reject controlled failures."""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def rejected(command: list[str], cwd: Path, label: str) -> None:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=60)
    if result.returncode != 1:
        raise RuntimeError(f"{label}: expected exit 1, got {result.returncode}")
    print(f"{label}: expected failure, exit 1")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="rag-f00-gates-") as directory:
        root = Path(directory) / "repo"
        shutil.copytree(
            ROOT,
            root,
            ignore=shutil.ignore_patterns(
                ".git", ".venv", ".local", ".env", ".env.*", "__pycache__", "*.log"
            ),
        )
        constitution = root / "docs/01-constitution.md"
        original = constitution.read_text()
        constitution.unlink()
        rejected([sys.executable, "scripts/check_docs.py"], root, "V04 missing constitution")
        constitution.write_text(original)
        fixture = root / "tests/unit/test_expected_failure.py"
        fixture.write_text("def test_expected_failure():\n    assert False\n")
        rejected(
            [sys.executable, "-m", "pytest", "-q", str(fixture)],
            root,
            "V04 failing assertion",
        )
        fixture.unlink()
        fixture = root / "src/rag_platform/expected_lint_failure.py"
        fixture.write_text("import os\n")
        rejected([sys.executable, "-m", "ruff", "check", str(fixture)], root, "V04 lint")
    print("V04 PASS: controlled changes were confined to temporary copies")


if __name__ == "__main__":
    main()
