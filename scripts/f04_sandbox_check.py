"""Offline QA child only. Exercise actual restrictions, CPU, memory and output limits."""

import errno
import json
import os
import socket
import sys

from rag_platform.ingestion.parser_sandbox import seal
from rag_platform.ingestion.parsers import preload


def denied(operation, expected=errno.EPERM):
    try:
        operation()
    except OSError as error:
        return error.errno == expected
    return False


def no_fork():
    try:
        child = os.fork()
    except OSError as error:
        return error.errno == errno.EPERM
    if child == 0:
        os._exit(3)
    return False


def main():
    preload()
    seal(cpu_seconds=1 if sys.argv[1] == "cpu" else 30)
    if sys.argv[1] == "cpu":
        while True:
            pass
    if sys.argv[1] == "output":
        piece = b"x" * 65536
        while True:
            os.write(1, piece)
    values = {
        "filesystem": denied(lambda: os.open("/etc/passwd", os.O_RDONLY)),
        "ipv4": denied(lambda: socket.socket(socket.AF_INET, socket.SOCK_STREAM)),
        "unix": denied(lambda: socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)),
        "fork": no_fork(),
        "exec": denied(lambda: os.execve("/bin/true", ["/bin/true"], {})),
        "input_readonly": denied(lambda: os.write(0, b"x"), errno.EBADF),
    }
    try:
        _value = bytearray(768 * 1024 * 1024)
        values["memory"] = False
    except MemoryError:
        values["memory"] = True
    values["input_readable"] = bool(os.read(0, 1))
    os.write(1, json.dumps(values).encode())
    os._exit(0)


if __name__ == "__main__":
    main()
