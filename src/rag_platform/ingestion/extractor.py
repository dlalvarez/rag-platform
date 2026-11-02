"""Bounded private parser subprocess; never used on the API request thread."""

import hashlib
import json
import os
import re
import selectors
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path
from threading import BoundedSemaphore

from rag_platform.documents.validation import MAX_BYTES
from rag_platform.ingestion.extraction import MAX_OUTPUT, PARSERS, ExtractionError, from_wire

_SLOT = BoundedSemaphore(1)


def _readonly(stream, expected_size, expected_hash):
    if (
        type(expected_size) is not int
        or not 1 <= expected_size <= MAX_BYTES
        or not isinstance(expected_hash, str)
        or not re.fullmatch(r"[0-9a-f]{64}", expected_hash)
    ):
        raise ExtractionError("INPUT_INVALID")
    fd = None
    try:
        source = stream.fileno()
        info = os.fstat(source)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_nlink > 1
            or info.st_size != expected_size
        ):
            raise ExtractionError("INPUT_INVALID")
        fd = os.open("/proc/self/fd/" + str(source), os.O_RDONLY | os.O_CLOEXEC)
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
            os.close(fd)
            raise ExtractionError("INPUT_INVALID")
    except (OSError, ValueError, AttributeError):
        if fd is not None:
            os.close(fd)
        raise ExtractionError("INPUT_INVALID") from None
    try:
        digest = hashlib.sha256()
        total = 0
        while data := os.read(fd, 65536):
            total += len(data)
            if total > expected_size:
                raise ExtractionError("INPUT_INVALID")
            digest.update(data)
        if total != expected_size or digest.hexdigest() != expected_hash:
            raise ExtractionError("INPUT_INVALID")
        os.lseek(fd, 0, os.SEEK_SET)
        return fd
    except BaseException:
        os.close(fd)
        raise


def _collect(process, timeout):
    output, deadline = bytearray(), time.monotonic() + timeout
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ExtractionError("PARSER_LIMIT")
            ready = selector.select(min(remaining, 0.25))
            for key, _ in ready:
                piece = os.read(key.fd, 65536)
                if not piece:
                    selector.unregister(key.fileobj)
                elif len(output) + len(piece) > MAX_OUTPUT:
                    raise ExtractionError("PARSER_LIMIT")
                else:
                    output.extend(piece)
        try:
            process.wait(timeout=max(0.001, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            raise ExtractionError("PARSER_LIMIT") from None
    return bytes(output)


def extract(stream, mime, *, expected_size, expected_hash, cpu_seconds=30, wall_seconds=45):
    if (
        not isinstance(mime, str)
        or mime not in PARSERS
        or type(cpu_seconds) is not int
        or not 1 <= cpu_seconds <= 30
        or type(wall_seconds) not in (int, float)
        or not 0 < wall_seconds <= 45
    ):
        raise ExtractionError("INPUT_INVALID")
    if not _SLOT.acquire(blocking=False):
        raise ExtractionError("PARSER_LIMIT")
    fd, process = None, None
    try:
        fd = _readonly(stream, expected_size, expected_hash)
        env = {
            "PYTHONPATH": str(Path(__file__).resolve().parents[2]),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUTF8": "1",
        }
        process = subprocess.Popen(
            [sys.executable, "-m", "rag_platform.ingestion.parser_child", mime, str(cpu_seconds)],
            stdin=fd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=env,
            cwd="/",
            close_fds=True,
            start_new_session=True,
        )
        data = _collect(process, wall_seconds)
        try:
            value = json.loads(data)
        except (ValueError, UnicodeError):
            code = (
                "PARSER_LIMIT"
                if process.returncode in (-signal.SIGKILL, -signal.SIGXCPU)
                else "PARSER_INVALID"
            )
            raise ExtractionError(code) from None
        if isinstance(value, dict) and set(value) == {"error"}:
            raise ExtractionError(value["error"])
        if process.returncode != 0:
            raise ExtractionError()
        return from_wire(value, mime)
    except ExtractionError:
        raise
    except Exception:
        raise ExtractionError("SANDBOX_UNAVAILABLE") from None
    finally:
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.wait()
            if process.stdout is not None:
                process.stdout.close()
        if fd is not None:
            os.close(fd)
        _SLOT.release()
