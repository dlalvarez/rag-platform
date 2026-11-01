"""Private expiring application bearer delivery; no infrastructure identity or renewal."""

import fcntl
import json
import math
import os
import stat
import threading
import time
from pathlib import Path
from uuid import uuid4

from rag_platform.identity_api import private_file
from rag_platform.providers.application_secrets import ApplicationSecretStore
from rag_platform.providers.secrets import SecretErrorCode, SecretStoreError

NAME = "application.json"


def invalid():
    return SecretStoreError(SecretErrorCode.INVALID)


def directory(path):
    path = Path(path)
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise invalid()
        return fd
    except BaseException:
        os.close(fd)
        raise


def lock_file(path):
    private_file(path, 1)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_nlink != 1
            or info.st_size != 1
        ):
            raise invalid()
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except BaseException:
        os.close(fd)
        raise


def read_record(path):
    try:
        record = json.loads(private_file(path, 8192))
        if (
            not isinstance(record, dict)
            or set(record) != {"version", "token", "issued_at", "expires_at"}
            or type(record["version"]) is not int
            or record["version"] != 1
            or not isinstance(record["token"], str)
            or not 1 <= len(record["token"]) <= 4096
            or any(not 33 <= ord(c) <= 126 for c in record["token"])
            or any(
                type(record[k]) not in (int, float) or not math.isfinite(record[k])
                for k in ("issued_at", "expires_at")
            )
            or not 0 < record["expires_at"] - record["issued_at"] <= 3600
            or record["issued_at"] > time.time() + 1
        ):
            raise invalid()
        return record
    except (ValueError, TypeError, KeyError):
        raise invalid() from None


def publish(path, record):
    """Atomic private replacement on a prevalidated directory, never follows a target."""
    path = Path(path)
    fd = directory(path)
    temp = "." + uuid4().hex
    out = None
    try:
        # Refuse symlinks/non-private files even though rename itself does not follow them.
        destination = path / NAME
        if destination.exists() or destination.is_symlink():
            read_record(destination)
        data = json.dumps(record, separators=(",", ":")).encode()
        out = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
        with os.fdopen(out, "wb") as stream:
            out = None
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, NAME, src_dir_fd=fd, dst_dir_fd=fd)
        os.fsync(fd)
    finally:
        if out is not None:
            os.close(out)
        try:
            os.unlink(temp, dir_fd=fd)
        except FileNotFoundError:
            pass
        os.close(fd)


class FileApplicationStore:
    """Single consumer, read-only mount; hot pools still verify every secret read.

    Missing, changed-invalid, expired or revoked delivery fails closed. Only the
    trusted operator tool can issue a replacement. No renewal, day token or KV write.
    """

    def __init__(self, path, endpoint, ca, *, factory=ApplicationSecretStore):
        self.path, self.endpoint, self.ca = Path(path), endpoint, ca
        self.factory = factory
        self._lock = threading.RLock()
        self._store, self._token, self._closed = None, None, False
        self._consumer = None
        try:
            fd = directory(self.path)
            os.close(fd)
            self._consumer = lock_file(self.path / "consumer.lock")
        except Exception:
            raise invalid() from None

    def __repr__(self):
        return "FileApplicationStore(<redacted>)"

    def _current(self):
        if self._closed:
            raise invalid()
        record = read_record(self.path / NAME)
        if record["expires_at"] <= time.time():
            raise SecretStoreError(SecretErrorCode.DENIED)
        token = record["token"]
        if token == self._token and self._store is not None:
            return self._store
        candidate = self.factory(self.endpoint, self.ca)
        try:
            candidate.attach_application(token)
        except BaseException:
            candidate.close()  # A rejected supplied token is never revoked.
            raise
        previous, self._store = self._store, None
        self._token = None
        try:
            if previous is not None:
                previous.revoke()
        except BaseException:
            try:
                candidate.revoke()
            finally:
                candidate.close()
            raise
        finally:
            if previous is not None:
                previous.close()
        self._store, self._token = candidate, token
        return candidate

    def read(self, ref):
        with self._lock:
            try:
                return self._current().read(ref)
            except SecretStoreError:
                raise
            except Exception:
                raise invalid() from None

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            try:
                if self._store is not None:
                    try:
                        self._store.revoke()
                    finally:
                        self._store.close()
            finally:
                self._store, self._token = None, None
                if self._consumer is not None:
                    os.close(self._consumer)
                    self._consumer = None
