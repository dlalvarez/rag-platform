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


def prepare_storage() -> None:
    """Add only isolated T003 storage bootstrap; never overwrite existing inputs."""
    validate_host(starting=True)
    for parent in (DATA, DATA / "tls", DATA / "secrets"):
        if not parent.is_dir() or parent.is_symlink():
            raise ValueError("Existing F01 preparation is required")
    targets = [
        DATA / "minio",
        DATA / "tls/minio",
        DATA / "secrets/storage_admin_user",
        DATA / "secrets/storage_admin_password",
    ]
    if any(path.exists() or path.is_symlink() for path in targets):
        raise ValueError("Existing or partial storage bootstrap will not be overwritten")
    for name in ("ca.crt", "ca.key"):
        path = DATA / "tls" / name
        if not path.is_file() or path.is_symlink():
            raise ValueError("Existing trusted CA is required")
    old_umask = os.umask(0o077)
    try:
        (DATA / "minio").mkdir(mode=0o700)
        tls = DATA / "tls/minio"
        tls.mkdir(mode=0o700)
        with (DATA / "secrets/storage_admin_user").open("x") as output:
            output.write("f01-admin-" + secrets.token_hex(16))
        with (DATA / "secrets/storage_admin_password").open("x") as output:
            output.write(secrets.token_urlsafe(36))
        (tls / "server.ext").write_text(
            "subjectAltName=DNS:minio\nbasicConstraints=critical,CA:FALSE\n"
            "keyUsage=critical,digitalSignature,keyEncipherment\n"
            "extendedKeyUsage=serverAuth\n"
        )

        def openssl(*args):
            subprocess.run(["openssl", *args], cwd=tls, check=True, capture_output=True)

        openssl(
            "req",
            "-new",
            "-newkey",
            "rsa:3072",
            "-nodes",
            "-subj",
            "/CN=minio",
            "-keyout",
            "private.key",
            "-out",
            "server.csr",
        )
        openssl(
            "x509",
            "-req",
            "-in",
            "server.csr",
            "-CA",
            "../ca.crt",
            "-CAkey",
            "../ca.key",
            "-CAcreateserial",
            "-days",
            "90",
            "-extfile",
            "server.ext",
            "-out",
            "public.crt",
        )
        (tls / "public.crt").chmod(0o444)
    finally:
        os.umask(old_umask)
    print("F01 storage prepared: isolated data/TLS/bootstrap; existing services preserved.")


def prepare_second() -> None:
    """Prepare only T006's new instance. Never overwrite data, passwords or certificates."""
    validate_host(starting=True)
    for folder in (DATA, DATA / "tls", DATA / "secrets"):
        if not folder.is_dir() or folder.is_symlink():
            raise ValueError("Existing F01 preparation required")
    tls = DATA / "tls"
    targets = [
        DATA / "postgres2",
        DATA / "secrets/postgres2_password",
        tls / "postgres2.key",
        tls / "postgres2.crt",
        tls / "postgres2.csr",
        tls / "postgres2.ext",
    ]
    if any(p.exists() or p.is_symlink() for p in targets):
        raise ValueError("Existing or partial second instance will not be overwritten")
    for name in ("ca.crt", "ca.key"):
        if not (tls / name).is_file() or (tls / name).is_symlink():
            raise ValueError("Existing trusted CA required")
    old_umask = os.umask(0o077)
    try:
        (DATA / "postgres2").mkdir(mode=0o700)
        (DATA / "secrets/postgres2_password").write_text(secrets.token_urlsafe(36))
        (tls / "postgres2.ext").write_text(
            "subjectAltName=DNS:postgres2\nbasicConstraints=critical,CA:FALSE\n"
            "keyUsage=critical,digitalSignature,keyEncipherment\n"
            "extendedKeyUsage=serverAuth\n"
        )
        for arguments in (
            (
                "req",
                "-new",
                "-newkey",
                "rsa:3072",
                "-nodes",
                "-subj",
                "/CN=postgres2",
                "-keyout",
                "postgres2.key",
                "-out",
                "postgres2.csr",
            ),
            (
                "x509",
                "-req",
                "-in",
                "postgres2.csr",
                "-CA",
                "ca.crt",
                "-CAkey",
                "ca.key",
                "-CAcreateserial",
                "-days",
                "90",
                "-extfile",
                "postgres2.ext",
                "-out",
                "postgres2.crt",
            ),
        ):
            subprocess.run(["openssl", *arguments], cwd=tls, check=True, capture_output=True)
        (tls / "postgres2.crt").chmod(0o444)
    finally:
        os.umask(old_umask)
    print("T006 second instance paths/TLS/bootstrap prepared; existing services unchanged.")


def attach_existing() -> None:
    """Attach this clean checkout to already prepared dev paths; writes no secrets/data."""
    validate_host()
    for name in ("raft", "postgres", "tls", "config", "secrets"):
        path = DATA / name
        if not path.is_dir() or path.is_symlink():
            raise ValueError("Existing prepared F01 paths required")
    if ENV.exists() or ENV.is_symlink():
        raise ValueError("Existing checkout configuration will not be overwritten")
    old_umask = os.umask(0o077)
    try:
        with ENV.open("x") as output:
            output.write(
                f"RAG_F01_ROOT={DATA}\nRAG_F01_UID={os.getuid()}\nRAG_F01_GID={os.getgid()}\n"
            )
    finally:
        os.umask(old_umask)
    print(
        "Checkout attached to existing F01 paths; no services started or data/credentials changed."
    )


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
    if any(
        arg
        in {"minio", "s3-check", "s3-compat", "saga-check", "isolation-check", "admin", "cli-check"}
        for arg in arguments
    ):
        for name in ("minio", "tls/minio"):
            path = DATA / name
            if path.is_symlink() or not path.is_dir():
                raise ValueError("Explicit storage preparation required")
        for name in (
            "tls/minio/public.crt",
            "tls/minio/private.key",
            "secrets/storage_admin_user",
            "secrets/storage_admin_password",
        ):
            path = DATA / name
            if path.is_symlink() or not path.is_file():
                raise ValueError("Missing or symlinked storage input")
            if name != "tls/minio/public.crt":
                stat = path.stat()
                if stat.st_uid != os.getuid() or stat.st_mode & 0o077:
                    raise ValueError("Storage bootstrap requires private owner-only files")
    if any(arg in {"postgres2", "isolation-check", "migration-calibrate"} for arg in arguments):
        for name in ("postgres2",):
            path = DATA / name
            if not path.is_dir() or path.is_symlink():
                raise ValueError("Explicit second instance preparation required")
        for name in ("tls/postgres2.crt", "tls/postgres2.key", "secrets/postgres2_password"):
            path = DATA / name
            if not path.is_file() or path.is_symlink():
                raise ValueError("Missing second instance input")
            if not name.endswith(".crt") and (
                path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077
            ):
                raise ValueError("Second instance inputs must be private")
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
        elif args.command == ["prepare-storage"]:
            prepare_storage()
        elif args.command == ["prepare-second"]:
            prepare_second()
        elif args.command == ["attach-existing"]:
            attach_existing()
        else:
            compose(args.command)
    except (ValueError, OSError, subprocess.SubprocessError, KeyError):
        raise SystemExit(
            "F01 refused: check isolated paths, mount, resources and configuration."
        ) from None


if __name__ == "__main__":
    main()
