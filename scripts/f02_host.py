"""Isolated F02 preparation/launcher on ragdev01; no F00/F01 mutations."""

import argparse
import json
import os
import secrets
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOUNT = Path("/srv/rag-data")
DATA = MOUNT / "rag-platform/f02"
ENV = ROOT / ".env.f02"


def validate(starting=False):
    mount = json.loads(
        subprocess.check_output(["findmnt", "--json", "--target", str(MOUNT)], text=True)
    )["filesystems"][0]
    if mount["target"] != str(MOUNT) or mount["fstype"] != "ext4":
        raise ValueError("MOUNT")
    if DATA.resolve() != DATA:
        raise ValueError("PATH")
    if starting:
        memory = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
        if int(memory["MemAvailable"].split()[0]) < 4 * 1024**2:
            raise ValueError("MEMORY")
        if shutil.disk_usage(MOUNT).free < 20 * 1024**3:
            raise ValueError("DISK")


def prepare():
    validate(True)
    if ENV.exists() or DATA.exists() or ENV.is_symlink() or DATA.is_symlink():
        raise ValueError("EXISTS")
    previous = os.umask(0o077)
    try:
        DATA.mkdir(mode=0o700)
        for folder in ("postgres", "tls", "secrets", "config"):
            (DATA / folder).mkdir(mode=0o700)
        tls = DATA / "tls"

        def openssl(*args):
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
            "/CN=ragdev01-f02-development-ca",
            "-keyout",
            "ca.key",
            "-out",
            "ca.crt",
            "-addext",
            "basicConstraints=critical,CA:TRUE",
            "-addext",
            "keyUsage=critical,keyCertSign,cRLSign",
        )
        for name in ("idp", "idp-postgres"):
            (tls / (name + ".ext")).write_text(
                f"subjectAltName=DNS:{name}\nbasicConstraints=critical,CA:FALSE\n"
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
                f"/CN={name}",
                "-keyout",
                name + ".key",
                "-out",
                name + ".csr",
            )
            openssl(
                "x509",
                "-req",
                "-in",
                name + ".csr",
                "-CA",
                "ca.crt",
                "-CAkey",
                "ca.key",
                "-CAcreateserial",
                "-days",
                "90",
                "-extfile",
                name + ".ext",
                "-out",
                name + ".crt",
            )
        for path in tls.glob("*.crt"):
            path.chmod(0o444)
        (tls / "pg_hba.conf").write_text(
            "local all all trust\nhostssl all all all scram-sha-256\nhostnossl all all all reject\n"
        )
        (tls / "pg_hba.conf").chmod(0o444)
        database_password = secrets.token_urlsafe(36)
        (DATA / "secrets/postgres_password").write_text(secrets.token_urlsafe(36))
        # Private bootstrap files, never committed or printed; URL-safe generated values.
        (DATA / "config/init.sql").write_text(
            "CREATE ROLE f02_idp LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
            f"NOREPLICATION NOBYPASSRLS PASSWORD '{database_password}';\n"
            "CREATE DATABASE keycloak OWNER f02_idp;\n"
            "REVOKE CONNECT ON DATABASE keycloak FROM PUBLIC;\n"
            "GRANT CONNECT ON DATABASE keycloak TO f02_idp;\n"
        )
        (DATA / "config/keycloak.conf").write_text(
            "db=postgres\ndb-username=f02_idp\n"
            f"db-password={database_password}\n"
            "db-url=jdbc:postgresql://idp-postgres:5432/keycloak?"
            "sslmode=verify-full&sslrootcert=/tls/ca.crt\n"
            "db-pool-initial-size=1\ndb-pool-min-size=1\ndb-pool-max-size=5\n"
            "hostname=https://idp:8443\nhttp-enabled=false\n"
            "https-certificate-file=/tls/idp.crt\nhttps-certificate-key-file=/tls/idp.key\n"
            "https-protocols=TLSv1.3\nhealth-enabled=true\n"
            "cache=local\n"
        )
        # No initial admin user or password; realm config contains no users/secrets.
        ENV.write_text(
            f"RAG_F02_ROOT={DATA}\nRAG_F02_UID={os.getuid()}\nRAG_F02_GID={os.getgid()}\n"
        )
    finally:
        os.umask(previous)
    print("PASS F02 PREP: private paths/TLS/SQL prepared; no users or product memberships.")


def compose(*args):
    validate(args[0] in {"up", "build"})
    if not ENV.is_file() or ENV.is_symlink():
        raise ValueError("ENV")
    expected = f"RAG_F02_ROOT={DATA}\nRAG_F02_UID={os.getuid()}\nRAG_F02_GID={os.getgid()}\n"
    if ENV.read_text() != expected:
        raise ValueError("ENV")
    return subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            str(ENV),
            "-f",
            str(ROOT / "ops/f02/compose.yaml"),
            *args,
        ],
        cwd=ROOT,
        check=True,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "build", "up", "status", "check", "config"])
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            prepare()
        elif args.action == "build":
            compose("build", "idp")
        elif args.action == "up":
            compose("up", "-d", "idp-postgres", "idp")
        elif args.action == "status":
            compose("ps")
        elif args.action == "check":
            compose("run", "--rm", "-T", "--no-deps", "idp-check")
        else:
            compose("config", "--quiet")
    except Exception:
        print("F02-T001 HOST: stopped; preserve data and inspect the runbook.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
