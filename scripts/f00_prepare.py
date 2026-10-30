"""Prepare an isolated development directory. Never starts services."""

import argparse
import json
import os
import secrets
import subprocess
from pathlib import Path


def validate_mount(root: Path, check_free: bool = False) -> None:
    mount = Path("/srv/rag-data")
    if root == mount or mount not in root.parents:
        raise ValueError("Host data must be a subdirectory of /srv/rag-data")
    result = subprocess.run(
        ["findmnt", "--json", "--target", str(mount)],
        capture_output=True,
        text=True,
        check=True,
    )
    filesystem = json.loads(result.stdout)["filesystems"][0]
    if filesystem["target"] != str(mount) or filesystem["fstype"] != "ext4":
        raise ValueError("/srv/rag-data must be an ext4 mount")
    if check_free and os.statvfs(mount).f_bavail * os.statvfs(mount).f_frsize < 5 * 1024**3:
        raise ValueError("At least 5 GiB free is required for this development check")


def validate_root(root: Path, host: bool) -> None:
    if (
        not root.is_absolute()
        or root == Path("/")
        or root.resolve() != root
        or any(c.isspace() for c in str(root))
        or "=" in str(root)
    ):
        raise ValueError("Use an absolute, isolated data directory")
    if host:
        validate_mount(root, check_free=True)
    elif Path("/srv") == root or Path("/srv") in root.parents:
        raise ValueError("Use --host for /srv paths; host execution needs separate authorization")
    if root.exists() and any(root.iterdir()):
        raise ValueError("Data directory is not empty; existing data will not be modified")


def prepare(root: Path, env_file: Path, host: bool = False) -> None:
    validate_root(root, host)
    if env_file.exists():
        raise ValueError("Environment file already exists; refusing to replace it")
    # Secrets are generated only at runtime, never committed or printed.
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name in ("postgres", "minio", "secrets"):
        (root / name).mkdir(mode=0o700)
    for name in ("postgres_password", "minio_user", "minio_password"):
        path = root / "secrets" / name
        path.write_text(secrets.token_hex(24), encoding="utf-8")
        path.chmod(0o444)  # Individual read-only bind mounts; parent stays 0700.
    env_file.parent.mkdir(parents=True, exist_ok=True)
    with env_file.open("x", encoding="utf-8") as output:
        output.write(
            f"RAG_DATA_ROOT={root}\nRAG_UID={os.getuid()}\nRAG_GID={os.getgid()}\n"
            "RAG_LOG_LEVEL=info\nRAG_API_PORT=8000\n"
        )
    env_file.chmod(0o600)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--host", action="store_true")
    args = parser.parse_args()
    try:
        prepare(args.data_root, args.env_file, args.host)
    except (ValueError, OSError, subprocess.SubprocessError, KeyError) as error:
        raise SystemExit(
            f"Preparation refused ({type(error).__name__}); check inputs/mount."
        ) from None
    print("Prepared isolated F00 data and ephemeral credentials; no services started.")


if __name__ == "__main__":
    main()
