"""Bounded private spool, format checks and hashes before any SQL receipt or S3 write."""

import codecs
import hashlib
import json
import re
import stat
import struct
import tempfile
import unicodedata
import zipfile
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from uuid import UUID

from rag_platform.documents.errors import DocumentError

CHUNK = 65536
MAX_BYTES = 10 * 1024 * 1024
MIMES = {
    "application/pdf": {".pdf"},
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {".docx"},
    "text/plain": {".txt"},
    "text/markdown": {".md", ".markdown"},
}
BAD_TEXT = re.compile(r"[\x00-\x08\x0b\x0e-\x1f\x7f-\x9f]")
WORD_TYPE = b"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"


def filename(value):
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 255
        or value != value.strip()
        or unicodedata.normalize("NFC", value) != value
        or any(char in value for char in ("/", "\\", ":"))
        or any(unicodedata.category(char).startswith("C") for char in value)
    ):
        raise DocumentError("INPUT_INVALID")
    return value


@dataclass(frozen=True, slots=True, repr=False)
class ValidatedFile:
    filename: str = field(repr=False)
    mime: str = field(repr=False)
    byte_size: int
    content_hash: str = field(repr=False)
    md5: str = field(repr=False)
    file: object = field(repr=False)

    def __repr__(self):
        return "ValidatedFile(<private>)"

    def fingerprint(self, principal, repository):
        if not isinstance(principal, UUID) or not isinstance(repository, UUID):
            raise DocumentError("INPUT_INVALID")
        values = [
            str(principal),
            str(repository),
            self.filename,
            self.mime,
            self.byte_size,
            self.content_hash,
        ]
        return hashlib.sha256(
            json.dumps(values, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest()


def check_zip_directory(file, byte_size):
    # Bound metadata allocation before ZipFile builds its ZipInfo list. Do not
    # trust only EOCD's declared entry count: count central records as well.
    file.seek(max(0, byte_size - 65557))
    tail = file.read(65557)
    offset = tail.rfind(b"PK\x05\x06")
    if offset < 0 or len(tail) - offset < 22:
        raise DocumentError("INPUT_INVALID")
    fields = struct.unpack("<4s4H2LH", tail[offset : offset + 22])
    _, disk, central_disk, disk_count, count, central_size, central_start, comment = fields
    end_position = byte_size - len(tail) + offset
    if (
        offset + 22 + comment != len(tail)
        or disk
        or central_disk
        or disk_count != count
        or not 1 <= count <= 2048
        or central_size > 2 * 1024 * 1024
        or central_start + central_size != end_position
    ):
        raise DocumentError("INPUT_INVALID")
    position, actual = central_start, 0
    while position < end_position:
        file.seek(position)
        header = file.read(46)
        if len(header) != 46 or header[:4] != b"PK\x01\x02":
            raise DocumentError("INPUT_INVALID")
        name_size, extra_size, comment_size = struct.unpack_from("<HHH", header, 28)
        actual += 1
        if not 1 <= name_size <= 1024 or actual > 2048:
            raise DocumentError("INPUT_INVALID")
        position += 46 + name_size + extra_size + comment_size
    if position != end_position or actual != count:
        raise DocumentError("INPUT_INVALID")


def check_docx(file, byte_size):
    try:
        check_zip_directory(file, byte_size)
        with zipfile.ZipFile(file) as archive:
            entries = archive.infolist()
            if not 1 <= len(entries) <= 2048:
                raise DocumentError("INPUT_INVALID")
            names, declared = set(), 0
            for entry in entries:
                name = entry.filename
                parts = name.rstrip("/").split("/")
                if (
                    not name
                    or name in names
                    or name.startswith("/")
                    or "\\" in name
                    or ":" in name
                    or any(part in ("", ".", "..") for part in parts)
                    or any(unicodedata.category(char).startswith("C") for char in name)
                    or stat.S_ISLNK(entry.external_attr >> 16)
                    or entry.flag_bits & 1
                    or entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                    or entry.file_size > 16 * 1024 * 1024
                    or entry.file_size > 100 * max(1, entry.compress_size)
                    or name.lower() == "word/vbaproject.bin"
                ):
                    raise DocumentError("INPUT_INVALID")
                names.add(name)
                declared += entry.file_size
            if declared > 100 * 1024 * 1024 or not {
                "[Content_Types].xml",
                "_rels/.rels",
                "word/document.xml",
            }.issubset(names):
                raise DocumentError("INPUT_INVALID")
            if archive.getinfo("[Content_Types].xml").file_size > 1024 * 1024:
                raise DocumentError("INPUT_INVALID")
            total, found_type = 0, False
            for entry in entries:
                if entry.is_dir():
                    continue
                actual, window = 0, b""
                with archive.open(entry) as content:
                    while piece := content.read(CHUNK):
                        actual += len(piece)
                        total += len(piece)
                        if actual > 16 * 1024 * 1024 or total > 100 * 1024 * 1024:
                            raise DocumentError("TOO_LARGE")
                        if entry.filename == "[Content_Types].xml":
                            window = (window[-len(WORD_TYPE) :] + piece).lower()
                            found_type = found_type or WORD_TYPE in window
                            if b"macroenabled" in window:
                                raise DocumentError("INPUT_INVALID")
                    if actual != entry.file_size:
                        raise DocumentError("INPUT_INVALID")
            if not found_type:
                raise DocumentError("INPUT_INVALID")
    except DocumentError:
        raise
    except (
        zipfile.BadZipFile,
        EOFError,
        RuntimeError,
        NotImplementedError,
        ValueError,
        struct.error,
    ):
        raise DocumentError("INPUT_INVALID") from None


class UploadSpool:
    """Unlinked private file. No caller filename is used as a path; caller must close."""

    def __init__(self, name, mime, *, max_bytes=MAX_BYTES):
        self.name = filename(name)
        if (
            not isinstance(mime, str)
            or mime not in MIMES
            or (PurePosixPath(self.name).suffix.lower() not in MIMES[mime])
        ):
            raise DocumentError("INPUT_INVALID")
        if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_BYTES:
            raise ValueError("Invalid upload limit")
        self.mime, self.limit = mime, max_bytes
        self.file = tempfile.TemporaryFile(mode="w+b")
        self.size = 0
        self.prefix = self.tail = b""
        self.sha = hashlib.sha256()
        self.md5 = hashlib.md5(usedforsecurity=False)  # S3 transport checksum, not authentication.
        self.decoder = (
            codecs.getincrementaldecoder("utf-8")("strict") if mime.startswith("text/") else None
        )
        self._result = None
        self._failed = False

    def __repr__(self):
        return "UploadSpool(<private>)"

    def _text(self, data, *, final=False):
        try:
            value = self.decoder.decode(data, final=final)
        except UnicodeError:
            raise DocumentError("INPUT_INVALID") from None
        if BAD_TEXT.search(value):
            raise DocumentError("INPUT_INVALID")

    def accept(self, chunk):
        if self._failed:
            raise DocumentError("INPUT_INVALID")
        try:
            self._accept(chunk)
        except Exception:
            self._failed = True
            raise

    def _accept(self, chunk):
        if self._result is not None or self.file.closed:
            raise DocumentError("INPUT_INVALID")
        if not isinstance(chunk, (bytes, bytearray, memoryview)):
            raise DocumentError("INPUT_INVALID")
        data = memoryview(chunk)
        if not data.c_contiguous:
            raise DocumentError("INPUT_INVALID")
        data = data.cast("B")
        if self.size + len(data) > self.limit:
            raise DocumentError("TOO_LARGE")
        for start in range(0, len(data), CHUNK):
            piece = data[start : start + CHUNK]
            if self.decoder is not None:
                self._text(piece)
            self.sha.update(piece)
            self.md5.update(piece)
            self.file.write(piece)
            if len(self.prefix) < 16:
                self.prefix += bytes(piece[: 16 - len(self.prefix)])
            self.tail = (self.tail + bytes(piece[-1024:]))[-1024:]
        self.size += len(data)

    def _zip_directory(self):
        return check_zip_directory(self.file, self.size)

    def _docx(self):
        return check_docx(self.file, self.size)

    def finish(self):
        if self._failed or self.file.closed:
            raise DocumentError("INPUT_INVALID")
        try:
            return self._finish()
        except Exception:
            self._failed = True
            raise

    def _finish(self):
        if self._result is not None:
            return self._result
        if self.file.closed or not self.size:
            raise DocumentError("INPUT_INVALID")
        if self.decoder is not None:
            self._text(b"", final=True)
            if self.prefix.startswith((b"%PDF-", b"PK\x03\x04")):
                raise DocumentError("INPUT_INVALID")
        elif self.mime == "application/pdf":
            if not re.match(
                rb"%PDF-(1\.[0-7]|2\.0)", self.prefix
            ) or not self.tail.rstrip().endswith(b"%%EOF"):
                raise DocumentError("INPUT_INVALID")
        else:
            self._docx()
        self.file.flush()
        self.file.seek(0)
        self._result = ValidatedFile(
            self.name, self.mime, self.size, self.sha.hexdigest(), self.md5.hexdigest(), self.file
        )
        return self._result

    def close(self):
        self.file.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
