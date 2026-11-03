"""Offline unit suite: deny IP networking; Unix IPC stays inside pytest's temp root."""

import os
import socket
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def deny_network(monkeypatch, tmp_path_factory):
    temporary = tmp_path_factory.getbasetemp().resolve()
    original_connect, original_connect_ex = socket.socket.connect, socket.socket.connect_ex

    def denied(*args, **kwargs):
        raise AssertionError("External networking is forbidden in the unit suite")

    def local(operation, sock, address, *args, **kwargs):
        try:
            path = Path(os.fsdecode(address))
            allowed = sock.family == socket.AF_UNIX and path.is_absolute()
            allowed = allowed and temporary in path.resolve().parents
        except (TypeError, ValueError, OSError):
            allowed = False
        if not allowed:
            return denied()
        return operation(sock, address, *args, **kwargs)

    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(
        socket.socket,
        "connect",
        lambda sock, address, *args, **kwargs: local(
            original_connect, sock, address, *args, **kwargs
        ),
    )
    monkeypatch.setattr(
        socket.socket,
        "connect_ex",
        lambda sock, address, *args, **kwargs: local(
            original_connect_ex, sock, address, *args, **kwargs
        ),
    )
