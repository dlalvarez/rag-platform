"""Bounded private IPC framing and signed-context representation. Never HTTP/log payloads."""

import json
import os
import re
import socket
import stat
import struct
import time
from pathlib import Path
from uuid import UUID

from rag_platform.embeddings.contracts import EmbeddingError
from rag_platform.tenancy.authorization import AuthorizedTenantContext
from rag_platform.tenancy.contracts import SecretRef

MAX_FRAME = 65536


def shape(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise EmbeddingError("INPUT_INVALID")


def identifier(value):
    if not isinstance(value, str):
        raise EmbeddingError("INPUT_INVALID")
    try:
        result = UUID(value)
        if result.int == 0:
            raise ValueError()
        return result
    except ValueError:
        raise EmbeddingError("INPUT_INVALID") from None


def context_payload(context):
    if not isinstance(context, AuthorizedTenantContext):
        raise EmbeddingError("INPUT_INVALID")
    return {
        "principal": str(context.principal_id),
        "tenant": str(context.tenant_id),
        "roles": list(context.roles),
        "trace": str(context.trace_id),
        "db": {"id": str(context.db_ref.id), "version": context.db_ref.version},
        "storage": {"id": str(context.storage_ref.id), "version": context.storage_ref.version},
        "expires": context.expires_at,
        "proof": context._proof,
    }


def context_from_payload(value):
    try:
        shape(value, ("principal", "tenant", "roles", "trace", "db", "storage", "expires", "proof"))
        for name in ("db", "storage"):
            shape(value[name], ("id", "version"))
        if (
            not isinstance(value["roles"], list)
            or len(value["roles"]) != 1
            or value["roles"][0] not in ("owner", "admin", "editor", "reader")
            or type(value["expires"]) is not int
            or value["expires"] <= 0
            or not isinstance(value["proof"], str)
            or re.fullmatch("[a-f0-9]{64}", value["proof"]) is None
        ):
            raise ValueError()
        return AuthorizedTenantContext(
            identifier(value["principal"]),
            identifier(value["tenant"]),
            tuple(value["roles"]),
            SecretRef(identifier(value["db"]["id"]), value["db"]["version"]),
            SecretRef(identifier(value["storage"]["id"]), value["storage"]["version"]),
            identifier(value["trace"]),
            value["expires"],
            value["proof"],
        )
    except Exception:
        raise EmbeddingError("INPUT_INVALID") from None


def _pairs(values):
    result = {}
    for key, value in values:
        if key in result:
            raise ValueError()
        result[key] = value
    return result


def _invalid_constant(_value):
    raise ValueError()


def _receive(sock, size, deadline):
    result = bytearray()
    while len(result) < size:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError()
        sock.settimeout(remaining)
        chunk = sock.recv(size - len(result))
        if not chunk:
            raise ValueError()
        result.extend(chunk)
    return bytes(result)


def receive(sock, *, seconds=2):
    try:
        deadline = time.monotonic() + seconds
        size = struct.unpack("!I", _receive(sock, 4, deadline))[0]
        if not 1 <= size <= MAX_FRAME:
            raise ValueError()
        data = _receive(sock, size, deadline)
        value = json.loads(
            data.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_invalid_constant
        )
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except Exception:
        raise EmbeddingError("DEPENDENCY_UNAVAILABLE") from None


def send(sock, value, *, seconds=2):
    try:
        data = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode(
            "utf-8"
        )
        if not isinstance(value, dict) or not 1 <= len(data) <= MAX_FRAME:
            raise ValueError()
        sock.settimeout(seconds)
        sock.sendall(struct.pack("!I", len(data)) + data)
    except Exception:
        raise EmbeddingError("DEPENDENCY_UNAVAILABLE") from None


def private_parent(path):
    try:
        path = Path(path)
        info = path.parent.lstat()
        if (
            not path.is_absolute()
            or len(os.fsencode(path)) > 103
            or not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o700
            or path.parent.resolve() != path.parent
        ):
            raise ValueError()
        return path
    except Exception:
        raise EmbeddingError("DEPENDENCY_UNAVAILABLE") from None


def private_socket(path):
    try:
        path = private_parent(path)
        info = path.lstat()
        if (
            not stat.S_ISSOCK(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) != 0o600
        ):
            raise ValueError()
        return info
    except Exception:
        raise EmbeddingError("DEPENDENCY_UNAVAILABLE") from None


def peer(sock):
    try:
        _pid, uid, _gid = struct.unpack(
            "3i", sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
        )
        if uid != os.getuid():
            raise ValueError()
    except Exception:
        raise EmbeddingError("DEPENDENCY_UNAVAILABLE") from None
