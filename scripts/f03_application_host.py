"""Operator TTY only: configure the fixed F03 AppRole, preserving the daily session."""

import fcntl
import getpass
import hashlib
import json
import os
import resource
import subprocess
import sys
from pathlib import Path

import f01_daily_host as base
import f01_host

ROOT = f01_host.REPOSITORY
SOURCES = (
    "scripts/f03_application_setup.py",
    "scripts/f01_daily_setup.py",
    "ops/f01/provisioner.hcl",
    "ops/f03/application-scope.json",
)


class SetupError(RuntimeError):
    pass


def source_hash():
    return hashlib.sha256(b"".join((ROOT / name).read_bytes() for name in SOURCES)).hexdigest()


def rpc(action, **secrets):
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            str(ROOT / ".env.f02"),
            "-f",
            str(ROOT / "ops/f02/compose.yaml"),
            "run",
            "--rm",
            "-T",
            "--no-deps",
            "--entrypoint",
            "python",
            "isolation-check",
            "scripts/f03_application_setup.py",
        ],
        input=json.dumps({"action": action, **secrets}),
        text=True,
        capture_output=True,
        cwd=ROOT,
        timeout=180,
    )
    try:
        data = json.loads(result.stdout)
    except (ValueError, TypeError):
        raise SetupError("BRIDGE_PROTOCOL") from None
    if result.returncode or not isinstance(data, dict) or data.get("ok") is not True:
        allowed = {
            "INPUT",
            "HEALTH",
            "RECOVER",
            "RESTORE",
            "RECOVER_UNSEAL",
            "RECOVER_ACTIVE",
            "RECOVER_STATUS",
            "RECOVER_INIT",
            "RECOVER_UPDATE",
            "RECOVER_DECODE",
            "RECOVER_CONFIGURE",
            "ROOT_REVOKE",
            "CEREMONY_CLEANUP",
        }
        code = data.get("code", "") if isinstance(data, dict) else ""
        step = code.removeprefix("F03-APP-")
        raise SetupError(step if code.startswith("F03-APP-") and step in allowed else "BRIDGE")
    return data


def maintenance(key):
    original = base.EXPECTED.read_bytes()
    if base.CONFIG.is_symlink() or base.CONFIG.read_bytes() != original:
        raise SetupError("CONFIG_CONFLICT")
    changed = base.temporary_config(original)
    try:
        base.write_config(changed)
        base.restart()
        if rpc("recover", key=key).get("root_revoked") is not True:
            raise SetupError("ROOT_REVOCATION")
    finally:
        if base.CONFIG.read_bytes() not in (original, changed):
            raise SetupError("RESTORE_CONFLICT") from None
        base.write_config(original)
        base.restart()
        rpc("restore", key=key)


def main():
    try:
        if sys.argv[1:] != ["configure"] or not sys.stdin.isatty() or not sys.stdout.isatty():
            raise SetupError("TTY_REQUIRED")
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        f01_host.validate_host(starting=True)
        state = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        if state.stdout:
            raise SetupError("CHECKOUT_DIRTY")
        info = base.CONFIG.lstat()
        if info.st_uid != os.getuid() or info.st_mode & 0o077 or base.CONFIG.is_symlink():
            raise SetupError("CONFIG_OWNER")
        if base.CONFIG.read_bytes() != base.EXPECTED.read_bytes():
            raise SetupError("CONFIG_CONFLICT")
        directory = Path(f"/run/user/{os.getuid()}/rag-f01-access")
        info = directory.lstat()
        if (
            directory.is_symlink()
            or not directory.is_dir()
            or info.st_uid != os.getuid()
            or info.st_mode & 0o077
        ):
            raise SetupError("ACCESS_DIRECTORY")
        fd = os.open(directory / "maintenance.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            health = rpc("health")
            if health.get("source_hash") != source_hash():
                raise SetupError("IMAGE_SOURCE_MISMATCH")
            print("Esta operación reinicia SOLO OpenBao dos veces; conserva la sesión diaria.")
            print(
                "Instala solo el AppRole F03 y su emisión limitada; no cambia datos ni contraseñas."
            )
            print("El root recuperado se revoca y la configuración TLS original se restaura.")
            if input("Para autorizar escribe CONFIGURARF03: ") != "CONFIGURARF03":
                raise SetupError("CANCELLED")
            key = getpass.getpass("Clave de desbloqueo original (una línea): ").strip()
            if not key or any(c.isspace() for c in key):
                raise SetupError("KEY_FORMAT")
            maintenance(key)
            del key
            print("PASS F03 APP SETUP: root revocado; TLS/config original restaurada; nodo activo.")
            print(
                "PASS F03 APP SETUP: rol de lectura limitado instalado; sesión diaria conservada."
            )
        finally:
            os.close(fd)
    except (Exception, KeyboardInterrupt) as error:
        code = error.args[0] if isinstance(error, SetupError) else "STOPPED"
        raise SystemExit(
            "F03-APP-SETUP " + code + "; consulta el runbook; sin detalles sensibles."
        ) from None


if __name__ == "__main__":
    main()
