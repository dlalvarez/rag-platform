"""Guarded ragdev01 preparation and Compose launcher; never generates unseal material."""

import argparse
import json
import os
import secrets
import shutil
import subprocess
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
DATA = Path("/srv/rag-data/rag-platform/f01")
ENV = REPOSITORY / ".env.f01"
MOUNT = Path("/srv/rag-data")


def validate_host(*, starting: bool = False) -> None:
    mount = json.loads(
        subprocess.check_output(["findmnt", "--json", "--target", str(MOUNT)], text=True)
    )["filesystems"][0]
    if mount["target"] != str(MOUNT) or mount["fstype"] != "ext4":
        raise ValueError("F01 requires the mounted ext4 data disk")
    if DATA.resolve() != DATA:
        raise ValueError("F01 refuses symlinked data paths")
    if starting:
        if shutil.disk_usage(MOUNT).free < 20 * 1024**3:
            raise ValueError("F01 requires 20 GiB free disk")
        memory = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
        if int(memory["MemAvailable"].strip().split()[0]) < 7 * 1024**2:
            raise ValueError("F01 requires 7 GiB available RAM")


def prepare() -> None:
    validate_host(starting=True)
    if ENV.exists() or DATA.exists():
        raise ValueError("Existing F01 env/data will not be overwritten")
    old_umask = os.umask(0o077)
    try:
        DATA.mkdir(mode=0o700)
        for folder in ("raft", "postgres", "tls", "config", "secrets"):
            (DATA / folder).mkdir(mode=0o700)
        shutil.copyfile(REPOSITORY / "ops/f01/openbao.hcl", DATA / "config/openbao.hcl")
        shutil.copyfile(REPOSITORY / "ops/f01/pg_hba.conf", DATA / "config/pg_hba.conf")
        (DATA / "config/pg_hba.conf").chmod(0o444)
        for name in ("postgres_password", "control_migrator_password"):
            (DATA / "secrets" / name).write_text(secrets.token_urlsafe(36))
        tls = DATA / "tls"

        def openssl(*args: str) -> None:
            subprocess.run(["openssl", *args], cwd=tls, check=True, capture_output=True)

        openssl(
            "req",
            "-x509",
            "-newkey",
            "rsa:3072",
            "-nodes",
            "-days",
            "90",
            "-subj",
            "/CN=ragdev01-f01-development-ca",
            "-keyout",
            "ca.key",
            "-out",
            "ca.crt",
            "-addext",
            "basicConstraints=critical,CA:TRUE",
            "-addext",
            "keyUsage=critical,keyCertSign,cRLSign",
        )
        for service in ("openbao", "postgres"):
            (tls / f"{service}.ext").write_text(
                f"subjectAltName=DNS:{service}\nbasicConstraints=critical,CA:FALSE\n"
                "keyUsage=critical,digitalSignature,keyEncipherment\n"
                "extendedKeyUsage=serverAuth\n"
            )
            openssl(
                "req",
                "-new",
                "-newkey",
                "rsa:3072",
                "-nodes",
                "-subj",
                f"/CN={service}",
                "-keyout",
                f"{service}.key",
                "-out",
                f"{service}.csr",
            )
            openssl(
                "x509",
                "-req",
                "-in",
                f"{service}.csr",
                "-CA",
                "ca.crt",
                "-CAkey",
                "ca.key",
                "-CAcreateserial",
                "-days",
                "90",
                "-extfile",
                f"{service}.ext",
                "-out",
                f"{service}.crt",
            )
        for path in tls.glob("*.crt"):
            path.chmod(0o444)
        ENV.write_text(
            f"RAG_F01_ROOT={DATA}\nRAG_F01_UID={os.getuid()}\nRAG_F01_GID={os.getgid()}\n"
        )
    finally:
        os.umask(old_umask)
    print("F01 paths/TLS/SQL bootstrap prepared; no OpenBao initialization or unseal keys.")


def compose(arguments: list[str]) -> None:
    if not arguments or arguments[0] not in {
        "config",
        "build",
        "pull",
        "up",
        "ps",
        "run",
        "stop",
        "start",
        "restart",
        "down",
    }:
        raise ValueError("Supply an allowed F01 Compose command")
    if "--volumes" in arguments or "-v" in arguments or "--remove-orphans" in arguments:
        raise ValueError("Data deletion/orphan removal is not allowed")
    validate_host(starting=arguments[0] in {"build", "pull", "up", "start", "run", "restart"})
    expected = f"RAG_F01_ROOT={DATA}\nRAG_F01_UID={os.getuid()}\nRAG_F01_GID={os.getgid()}\n"
    if ENV.is_symlink() or ENV.read_text() != expected:
        raise ValueError("F01 env must match the fixed isolated host profile")
    for name in ("raft", "postgres", "tls", "config", "secrets"):
        path = DATA / name
        if not path.is_dir() or path.is_symlink():
            raise ValueError("F01 paths must be explicitly prepared")
    for name in (
        "config/openbao.hcl",
        "config/pg_hba.conf",
        "tls/ca.crt",
        "tls/openbao.key",
        "tls/openbao.crt",
        "tls/postgres.key",
        "tls/postgres.crt",
        "secrets/postgres_password",
        "secrets/control_migrator_password",
    ):
        path = DATA / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("Missing or symlinked F01 input")
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--project-name",
            "rag-f01-dev",
            "--env-file",
            str(ENV),
            "-f",
            str(REPOSITORY / "ops/f01/compose.yaml"),
            *arguments,
        ],
        cwd=REPOSITORY,
    )
    raise SystemExit(result.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        if args.command == ["prepare"]:
            prepare()
        else:
            compose(args.command)
    except (ValueError, OSError, subprocess.SubprocessError, KeyError):
        raise SystemExit(
            "F01 refused: check isolated paths, mount, resources and configuration."
        ) from None


if __name__ == "__main__":
    main()
