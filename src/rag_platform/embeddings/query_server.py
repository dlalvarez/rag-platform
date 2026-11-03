"""Private Unix listener with bounded handlers and ownership-safe endpoint cleanup."""

import errno
import logging
import os
import socket
import socketserver
import stat
from threading import BoundedSemaphore, Thread

from rag_platform.embeddings import query_wire as wire
from rag_platform.embeddings.contracts import EmbeddingError

LOGGER = logging.getLogger("rag_platform.embeddings")


class _Handler(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            wire.peer(self.request)
            message = wire.receive(self.request)
            response = self.server.backend.response(message)
            wire.send(self.request, response)
        except Exception:
            # No request, exception body, signed context or vector is logged.
            LOGGER.info("query_transport code=DEPENDENCY_UNAVAILABLE")


class _Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    request_queue_size = 1
    daemon_threads = False
    block_on_close = True

    def __init__(self, address, backend):
        self.backend, self.slots = backend, BoundedSemaphore(2)
        super().__init__(address, _Handler, bind_and_activate=False)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()

    def handle_error(self, request, client_address):
        LOGGER.info("query_transport code=DEPENDENCY_UNAVAILABLE")


def _identity(info):
    return info.st_dev, info.st_ino


def _stale(path):
    if not path.exists() and not path.is_symlink():
        return
    info = wire.private_socket(path)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.2)
        try:
            probe.connect(str(path))
        except OSError as error:
            if error.errno not in (errno.ECONNREFUSED, errno.ENOENT):
                raise EmbeddingError("DEPENDENCY_UNAVAILABLE") from None
        else:
            raise EmbeddingError("DEPENDENCY_UNAVAILABLE")
    # Only a private, unchanged, inactive socket. Never remove another file/listener.
    if _identity(wire.private_socket(path)) != _identity(info):
        raise EmbeddingError("DEPENDENCY_UNAVAILABLE")
    path.unlink()


class QueryServer:
    """Caller must own the exclusive worker handoff before constructing this listener."""

    def __init__(self, path, backend):
        self.path, self.thread, self.owned, self.server = (
            wire.private_parent(path),
            None,
            None,
            None,
        )
        try:
            _stale(self.path)
            self.server = _Server(str(self.path), backend)
            self.server.server_bind()
            self.owned = _identity(self.path.lstat())
            os.chmod(self.path, 0o600)
            self.owned = _identity(wire.private_socket(self.path))
            self.server.server_activate()
        except BaseException:
            self.close()
            raise

    def start(self):
        if self.server is None or self.thread is not None:
            raise ValueError("One private listener lifecycle required")
        self.thread = Thread(
            target=self.server.serve_forever,
            kwargs={"poll_interval": 0.1},
            name="private-query-listener",
            daemon=True,
        )
        self.thread.start()

    def close(self):
        try:
            if self.server is not None:
                if self.thread is not None and self.thread.is_alive():
                    self.server.shutdown()
                    self.thread.join(timeout=5)
                self.server.server_close()
        finally:
            self.server = None
            if self.owned is not None:
                try:
                    info = self.path.lstat()
                    if (
                        _identity(info) == self.owned
                        and stat.S_ISSOCK(info.st_mode)
                        and info.st_uid == os.getuid()
                        and info.st_nlink == 1
                    ):
                        self.path.unlink()
                except (OSError, EmbeddingError):
                    pass  # Refuse to remove any replaced/foreign path.
                self.owned = None

    def __repr__(self):
        return "QueryServer(<private endpoint>)"
