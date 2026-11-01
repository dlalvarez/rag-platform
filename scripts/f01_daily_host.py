"""Operator's own SSH terminal only: guarded, reversible initial daily-role setup."""

import fcntl
import getpass
import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import f01_host

ROOT = f01_host.DATA
CONFIG = ROOT / "config/openbao.hcl"
EXPECTED = f01_host.REPOSITORY / "ops/f01/openbao.hcl"
BRIDGE = "scripts/f01_daily_setup.py"


class RecoveryError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__("F01-DAY-SETUP " + code + "; conserva datos y consulta el runbook.")


def prefix():
    return [
        "docker",
        "compose",
        "--project-name",
        "rag-f01-dev",
        "--env-file",
        str(f01_host.ENV),
        "-f",
        str(f01_host.REPOSITORY / "ops/f01/compose.yaml"),
    ]


def rpc(action, **secrets):
    result = subprocess.run(
        [*prefix(), "run", "--rm", "-T", "--entrypoint", "python", "daily", BRIDGE],
        input=json.dumps({"action": action, **secrets}),
        text=True,
        capture_output=True,
        cwd=f01_host.REPOSITORY,
    )
    # Never echo a subprocess body/stderr/exception, including on JSON failures.
    try:
        data = json.loads(result.stdout)
    except (ValueError, TypeError):
        raise RecoveryError("BRIDGE_PROTOCOL") from None
    if result.returncode or not isinstance(data, dict) or data.get("ok") is not True:
        allowed = {
            "INPUT",
            "RECOVER",
            "RESTORE",
            "ACTIVATE",
            "RECOVER_UNSEAL",
            "RECOVER_ACTIVE",
            "RECOVER_STATUS",
            "RECOVER_INIT",
            "RECOVER_UPDATE",
            "RECOVER_DECODE",
            "RECOVER_CONFIGURE",
            "ROOT_REVOKE",
            "CEREMONY_CLEANUP",
            "RESTORE_ACTIVE",
            "ACTIVATE_ACTIVE",
        }
        code = data.get("code", "") if isinstance(data, dict) else ""
        if code in {"F01-DAY-" + step for step in allowed}:
            raise RecoveryError(code.removeprefix("F01-DAY-"))
        raise RecoveryError("BRIDGE_" + action.upper())
    return data


def restart():
    subprocess.run(
        [*prefix(), "restart", "openbao"],
        check=True,
        capture_output=True,
        cwd=f01_host.REPOSITORY,
    )
    for _ in range(12):
        try:
            rpc("health")
            return
        except (RecoveryError, subprocess.SubprocessError):
            time.sleep(1)
    raise RecoveryError("HEALTH")


def temporary_config(original):
    marker = b'listener "tcp" {\n'
    if original.count(marker) != 1 or b"disable_unauthed_generate_root_endpoints" in original:
        raise RecoveryError("CONFIG_CONFLICT")
    return original.replace(
        marker, marker + b"  disable_unauthed_generate_root_endpoints = false\n", 1
    )


def write_config(body):
    if CONFIG.is_symlink() or not CONFIG.is_file():
        raise RecoveryError("CONFIG_PATH")
    path = CONFIG.parent / (".daily-config-" + uuid4().hex)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(body)
            output.flush()
            os.fsync(output.fileno())
        os.replace(path, CONFIG)
    finally:
        path.unlink(missing_ok=True)


def maintenance(key):
    original = EXPECTED.read_bytes()
    if CONFIG.is_symlink() or CONFIG.read_bytes() != original:
        raise RecoveryError("CONFIG_CONFLICT")
    changed = temporary_config(original)
    try:
        write_config(changed)
        restart()
        if rpc("recover", key=key).get("root_revoked") is not True:
            raise RecoveryError("ROOT_REVOCATION")
    finally:
        # Atomic writes guarantee either original or exact temporary bytes.
        # Refuse concurrent foreign configuration instead of overwriting it.
        current = CONFIG.read_bytes()
        if current not in (original, changed):
            raise RecoveryError("RESTORE_CONFLICT") from None
        write_config(original)
        restart()
        rpc("restore", key=key)


def main():
    try:
        if len(sys.argv) != 2 or sys.argv[1] != "configure":
            raise RecoveryError("INPUT")
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            raise RecoveryError("TTY_REQUIRED")
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        f01_host.validate_host(starting=True)
        if (
            f01_host.ENV.is_symlink()
            or f01_host.ENV.read_text()
            != f"RAG_F01_ROOT={ROOT}\nRAG_F01_UID={os.getuid()}\nRAG_F01_GID={os.getgid()}\n"
        ):
            raise RecoveryError("HOST_CONFIG")
        if CONFIG.is_symlink() or CONFIG.read_bytes() != EXPECTED.read_bytes():
            raise RecoveryError("CONFIG_CONFLICT")
        info = CONFIG.stat()
        if info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise RecoveryError("CONFIG_OWNER")
        f01_host.prepare_access()
        directory = Path(f"/run/user/{os.getuid()}/rag-f01-access")
        # Stable operator lock; separate from the handoff directory lock used inside tools.
        fd = os.open(directory / "maintenance.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if any(
                (directory / name).exists() or (directory / name).is_symlink()
                for name in ("grant.json", "day.json")
            ):
                raise RecoveryError("EXISTING_AUTHORIZATION")
            print("Esta configuración reinicia SOLO OpenBao dos veces.")
            print(
                "Activa recuperación solo durante la operación, revoca root y restaura TLS/config."
            )
            print("No ejecuta init, rekey, borrado, ni reinicia PostgreSQL/MinIO.")
            if input("Para autorizar esta ventana escribe CONFIGURAR24H: ") != "CONFIGURAR24H":
                raise RecoveryError("CANCELLED")
            key = getpass.getpass("Clave de desbloqueo original (una línea): ").strip()
            password = getpass.getpass("Contraseña del operador diego: ")
            if not key or any(c.isspace() for c in key) or not password:
                raise RecoveryError("INPUT")
            maintenance(key)
            print("PASS DAY SETUP: root revocado; configuración original restaurada.")
            result = rpc("activate", key=key, password=password)
            del key, password
            print("PASS DAY SETUP: sesión de ensayo revocada; sesión operativa de 24 horas activa.")
            print(json.dumps(result["day"], sort_keys=True))
        finally:
            os.close(fd)
    except RecoveryError as error:
        raise SystemExit(str(error)) from None
    except (Exception, KeyboardInterrupt):
        raise SystemExit(
            "F01-DAY-SETUP STOPPED; consulta el runbook; no se muestran secretos."
        ) from None


if __name__ == "__main__":
    main()
