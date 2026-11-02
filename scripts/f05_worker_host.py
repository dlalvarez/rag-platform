"""Host-only private delivery directory preparation and metadata status; no bearer output."""

import argparse
import json
import os
import stat
import time
from pathlib import Path

from rag_platform.identity_api import private_file
from rag_platform.providers.application_handoff import NAME, directory, lock_file, read_record


def delivery():
    if os.uname().sysname != "Linux" or os.getuid() != 1000:
        raise ValueError("Development host required")
    return Path("/run/user/1000/rag-f05-worker")


def prepare(path):
    path.mkdir(mode=0o700, exist_ok=True)
    parent = directory(path)
    try:
        for name in ("issuer.lock", "consumer.lock"):
            try:
                fd = os.open(
                    name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent
                )
            except FileExistsError:
                info = (path / name).lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != 1:
                    raise ValueError("Invalid private lock") from None
                private_file(path / name, 1)
                continue
            with os.fdopen(fd, "wb") as stream:
                stream.write(b"0")
                stream.flush()
                os.fsync(stream.fileno())
    finally:
        os.close(parent)


def status(path):
    fd = directory(path)
    os.close(fd)
    busy = False
    try:
        consumer = lock_file(path / "consumer.lock")
    except BlockingIOError:
        busy = True
    else:
        os.close(consumer)
    record_path = path / NAME
    if not record_path.exists() and not record_path.is_symlink():
        return {"consumer_busy": busy, "file_state": "MISSING"}
    record = read_record(record_path)
    return {
        "consumer_busy": busy,
        "file_state": "UNEXPIRED" if record["expires_at"] > time.time() else "EXPIRED",
        "expires_at": record["expires_at"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "status"))
    args = parser.parse_args()
    path = delivery()
    if args.action == "prepare":
        prepare(path)
    return status(path)


if __name__ == "__main__":
    try:
        print(json.dumps(main(), sort_keys=True))
    except (Exception, KeyboardInterrupt):
        raise SystemExit("F05 DELIVERY: REFUSED; no sensitive details.") from None
