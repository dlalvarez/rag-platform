"""ragdev01-only tmpfs preparation and closed-protocol F03 application issuer."""

import argparse
import json
import os
import resource
import stat
import subprocess
from pathlib import Path

import f01_host

ROOT = Path(__file__).resolve().parents[1]
DELIVERY = Path(f"/run/user/{os.getuid()}/rag-f03-application")
ENV = ROOT / ".env.f03"


def prepare():
    f01_host.validate_host()
    mount = json.loads(
        subprocess.check_output(["findmnt", "--json", "--target", str(DELIVERY.parent)], text=True)
    )["filesystems"][0]
    if mount["fstype"] != "tmpfs" or DELIVERY.parent.resolve() != DELIVERY.parent:
        raise ValueError()
    DELIVERY.mkdir(mode=0o700, exist_ok=True)
    info = DELIVERY.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise ValueError()
    for name in ("consumer.lock", "issuer.lock"):
        path = DELIVERY / name
        if not path.exists() and not path.is_symlink():
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(b"1")
        info = path.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_nlink != 1
            or info.st_size != 1
        ):
            raise ValueError()
    content = f"RAG_F03_UID={os.getuid()}\nRAG_F03_GID={os.getgid()}\n"
    if ENV.exists() or ENV.is_symlink():
        if ENV.is_symlink() or ENV.read_text() != content:
            raise ValueError()
    else:
        fd = os.open(ENV, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(content)


def issue(action, f02_env):
    prepare()
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            str(f02_env),
            "--env-file",
            str(ENV),
            "-f",
            str(ROOT / "ops/f02/compose.yaml"),
            "-f",
            str(ROOT / "ops/f03/handoff.compose.yaml"),
            "run",
            "--rm",
            "-T",
            "--no-deps",
            "application-issue",
            action,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=180,
    )
    try:
        data = json.loads(result.stdout)
        if (
            result.returncode
            or set(data) != {"state", "expires_at", "created"}
            or data["state"] != "ACTIVE"
            or type(data["created"]) is not bool
            or type(data["expires_at"]) not in (int, float)
        ):
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError() from None
    return data


def main():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "ensure", "replace"])
    parser.add_argument("--f02-env", type=Path, default=ROOT / ".env.f02")
    args = parser.parse_args()
    action = args.action
    if action == "prepare":
        prepare()
        print("PASS F03 HANDOFF: directorio tmpfs privado preparado; sin credenciales creadas.")
    else:
        print(json.dumps(issue(action, args.f02_env), sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (Exception, KeyboardInterrupt):
        raise SystemExit("F03 HANDOFF HOST: REFUSED; sin detalles sensibles.") from None
