"""ragdev01-only private worker delivery; never deploys or migrates services."""

import argparse
import json
import os
import resource
import stat
import subprocess
from pathlib import Path

import f01_host

ROOT = Path(__file__).resolve().parents[1]
DELIVERY = Path(f"/run/user/{os.getuid()}/rag-f04-worker")


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
        p = DELIVERY / name
        if not p.exists() and not p.is_symlink():
            fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(b"1")
        info = p.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_nlink != 1
            or info.st_size != 1
        ):
            raise ValueError()


def issue(action, environment):
    prepare()
    r = subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            str(environment),
            "-f",
            str(ROOT / "ops/f02/compose.yaml"),
            "-f",
            str(ROOT / "ops/f04/worker.compose.yaml"),
            "run",
            "--rm",
            "-T",
            "--no-deps",
            "worker-issue",
            action,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    try:
        data = json.loads(r.stdout)
        if (
            r.returncode
            or set(data) != {"state", "expires_at", "created"}
            or data["state"] != "ACTIVE"
            or type(data["created"]) is not bool
            or type(data["expires_at"]) not in (int, float)
        ):
            raise ValueError()
        return data
    except Exception:
        raise ValueError() from None


def main():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "ensure", "replace"])
    parser.add_argument("--f02-env", type=Path, default=ROOT / ".env.f02")
    args = parser.parse_args()
    if args.action == "prepare":
        prepare()
        print("PASS F04 HANDOFF: tmpfs privado preparado; sin credenciales creadas.")
    else:
        print(json.dumps(issue(args.action, args.f02_env), sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (Exception, KeyboardInterrupt):
        raise SystemExit("F04 HANDOFF HOST: REFUSED; sin detalles sensibles.") from None
