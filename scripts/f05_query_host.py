"""Prepare only the private tmpfs directory for the approved Unix query provider."""

import argparse
import json
import os
from pathlib import Path

from rag_platform.embeddings.query_wire import private_parent, private_socket


def location():
    if os.uname().sysname != "Linux" or os.getuid() != 1000:
        raise ValueError("Development host required")
    return Path("/run/user/1000/rag-f05-query")


def prepare(path):
    path.mkdir(mode=0o700, exist_ok=True)
    private_parent(path / "qwen.sock")


def status(path):
    endpoint = path / "qwen.sock"
    private_parent(endpoint)
    present = endpoint.exists() or endpoint.is_symlink()
    if present:
        private_socket(endpoint)
    return {"prepared": True, "socket_present": present}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "status"))
    args = parser.parse_args()
    path = location()
    if args.action == "prepare":
        prepare(path)
    return status(path)


if __name__ == "__main__":
    try:
        print(json.dumps(main(), sort_keys=True))
    except (Exception, KeyboardInterrupt):
        raise SystemExit("F05 QUERY DIRECTORY: REFUSED; no sensitive details.") from None
