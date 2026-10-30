"""Guard host data mount before every F00 Compose operation."""

import argparse
import subprocess
from pathlib import Path

from f00_prepare import validate_mount

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.command:
        parser.error("Supply a Compose command, for example config --quiet")
    try:
        env_file = args.env_file.resolve(strict=True)
        values = dict(
            line.split("=", 1)
            for line in env_file.read_text().splitlines()
            if line and not line.startswith("#")
        )
        root = Path(values["RAG_DATA_ROOT"])
        validate_mount(root, check_free=args.command[0] in {"up", "build", "create", "start"})
        if root.resolve() != root:
            raise ValueError("Symlinked data paths are refused")
        for name in ("postgres", "minio", "secrets"):
            if not (root / name).is_dir() or (root / name).is_symlink():
                raise ValueError("Prepare isolated directories first")
    except (ValueError, OSError, KeyError, subprocess.SubprocessError):
        raise SystemExit("F00 refused: check env file, isolated paths and ext4 mount.") from None
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--project-name",
            "rag-f00-dev",
            "--env-file",
            str(env_file),
            *args.command,
        ],
        cwd=ROOT,
    )
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
