"""Invalid/oversized files never become validated uploads; memory and ZIP metadata bounded."""

import hashlib
import io
import os
import stat
import struct
import zipfile
from uuid import uuid4

import pytest

from rag_platform.documents.errors import DocumentError
from rag_platform.documents.validation import CHUNK, MAX_BYTES, UploadSpool

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TYPE = b"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"


def word_package(*, extras=None, text=None, content_type=TYPE, compression=zipfile.ZIP_DEFLATED):
    output = io.BytesIO()
    parts = {
        "[Content_Types].xml": b'<Types><Override ContentType="' + content_type + b'"/></Types>',
        "_rels/.rels": b"<Relationships/>",
        "word/document.xml": text or b"<document>validation-marker-A</document>",
    }
    parts.update(extras or {})
    with zipfile.ZipFile(output, "w", compression=compression) as archive:
        for name, value in parts.items():
            archive.writestr(name, value)
    return output.getvalue()


@pytest.mark.parametrize(
    "name,mime,body",
    [
        ("original.pdf", "application/pdf", b"%PDF-1.7\nsynthetic\n%%EOF\n"),
        ("original.docx", DOCX, word_package()),
        ("original.txt", "text/plain", "Texto español: café.\n".encode()),
        ("original.md", "text/markdown", "# Título\nTexto privado sintético.\n".encode()),
    ],
)
def test_streaming_hashes_formats_and_private_lifetime(name, mime, body):
    with UploadSpool(name, mime) as spool:
        assert stat.S_IMODE(os.fstat(spool.file.fileno()).st_mode) == 0o600
        for byte in body:
            spool.accept(bytes([byte]))
        file = spool.finish()
        assert file.byte_size == len(body)
        assert file.content_hash == hashlib.sha256(body).hexdigest()
        assert file.md5 == hashlib.md5(body, usedforsecurity=False).hexdigest()
        assert file.file.read() == body
        assert len(spool.prefix) <= 16 and len(spool.tail) <= 1024
        assert name not in repr(file) + repr(spool)
    assert file.file.closed


def test_large_input_chunk_is_processed_in_bounded_pieces(monkeypatch):
    body = ("é" * CHUNK * 2).encode()
    with UploadSpool("large.txt", "text/plain") as spool:
        original = spool._text
        observed = []

        def text(data, **kwargs):
            observed.append(len(data))
            return original(data, **kwargs)

        monkeypatch.setattr(spool, "_text", text)
        spool.accept(body)
        assert spool.finish().byte_size == len(body)
        assert max(observed) <= CHUNK


@pytest.mark.parametrize(
    "name",
    [
        "../secret.txt",
        "/secret.txt",
        "C:secret.txt",
        "folder\\secret.txt",
        " secret.txt",
        "secret.txt ",
        "bad\nname.txt",
        "bad\x00name.txt",
        "bad\u202ename.txt",
        "Cafe\u0301.txt",
        "a" * 256 + ".txt",
        True,
    ],
)
def test_invalid_filename_fails_before_spool_creation(name, monkeypatch):
    monkeypatch.setattr(
        "rag_platform.documents.validation.tempfile.TemporaryFile",
        lambda **_: pytest.fail("file allocated for invalid name"),
    )
    with pytest.raises(DocumentError, match="INPUT_INVALID"):
        UploadSpool(name, "text/plain")


@pytest.mark.parametrize(
    "name,mime,body",
    [
        ("empty.txt", "text/plain", b""),
        ("binary.txt", "text/plain", b"\x00\x01\xff"),
        ("truncated.txt", "text/plain", b"\xe2\x82"),
        ("wrong.txt", "text/plain", b"%PDF-1.4\n%%EOF"),
        ("wrong.pdf", "application/pdf", b"not PDF"),
        ("truncated.pdf", "application/pdf", b"%PDF-1.4\nmissing EOF"),
        ("wrong.docx", DOCX, b"not a ZIP"),
        ("wrong.docx", DOCX, word_package(content_type=b"application/zip")),
        ("macro.docx", DOCX, word_package(extras={"word/vbaProject.bin": b"synthetic"})),
        ("macro.docx", DOCX, word_package(content_type=TYPE + b" macroEnabled")),
        ("traversal.docx", DOCX, word_package(extras={"../escape": b"synthetic"})),
        ("absolute.docx", DOCX, word_package(extras={"/escape": b"synthetic"})),
        ("windows.docx", DOCX, word_package(extras={"C:escape": b"synthetic"})),
        ("bomb.docx", DOCX, word_package(text=b"x" * 1024 * 1024)),
    ],
)
def test_invalid_format_or_container_never_returns_validated_file(name, mime, body, caplog):
    with UploadSpool(name, mime) as spool:
        with pytest.raises(DocumentError):
            spool.accept(body)
            spool.finish()
        with pytest.raises(DocumentError):
            spool.finish()
    assert "validation-marker" not in caplog.text


def test_symlink_member_rejected_without_extracting():
    member = zipfile.ZipInfo("word/link")
    member.create_system = 3
    member.external_attr = (stat.S_IFLNK | 0o777) << 16
    body = word_package(extras={member: b"../../elsewhere"})
    with UploadSpool("link.docx", DOCX) as spool, pytest.raises(DocumentError):
        spool.accept(body)
        spool.finish()


def test_crc_is_checked_in_bounded_reads():
    body = word_package(compression=zipfile.ZIP_STORED)
    assert body.count(b"validation-marker-A") == 1
    body = body.replace(b"validation-marker-A", b"validation-marker-B")
    with UploadSpool("corrupt.docx", DOCX) as spool, pytest.raises(DocumentError):
        spool.accept(body)
        spool.finish()


@pytest.mark.parametrize("lie", [False, True])
def test_zip_entry_limit_checked_before_zipinfo_allocation(lie, monkeypatch):
    body = bytearray(word_package(extras={f"extra/{n}": b"" for n in range(2050)}))
    if lie:
        offset = body.rfind(b"PK\x05\x06")
        struct.pack_into("<HH", body, offset + 8, 1, 1)
    with UploadSpool("many.docx", DOCX) as spool:
        spool.accept(body)
        monkeypatch.setattr(
            "rag_platform.documents.validation.zipfile.ZipFile",
            lambda *_: pytest.fail("unbounded ZipInfo allocation"),
        )
        with pytest.raises(DocumentError):
            spool.finish()


def test_partial_chunk_error_poisons_whole_upload():
    with UploadSpool("partial.txt", "text/plain") as spool:
        spool.accept(b"valid prefix")
        with pytest.raises(DocumentError):
            spool.accept(b"x" * CHUNK + b"\xff")
        with pytest.raises(DocumentError):
            spool.accept(b"cannot continue")
        with pytest.raises(DocumentError):
            spool.finish()


def test_size_limit_rejected_before_write_and_cannot_resume():
    with UploadSpool("small.txt", "text/plain", max_bytes=4) as spool:
        with pytest.raises(DocumentError, match="TOO_LARGE"):
            spool.accept(b"12345")
        assert spool.file.tell() == 0
        with pytest.raises(DocumentError):
            spool.finish()


@pytest.mark.parametrize("limit", [True, 0, -1, MAX_BYTES + 1])
def test_invalid_resource_configuration_creates_no_file(limit, monkeypatch):
    monkeypatch.setattr(
        "rag_platform.documents.validation.tempfile.TemporaryFile",
        lambda **_: pytest.fail("file allocated"),
    )
    with pytest.raises(ValueError):
        UploadSpool("name.txt", "text/plain", max_bytes=limit)


def test_fingerprint_binds_actor_repo_and_metadata():
    actor, repo = uuid4(), uuid4()
    with UploadSpool("synthetic-private-title.txt", "text/plain") as spool:
        spool.accept(b"synthetic private body")
        value = spool.finish()
        digest = value.fingerprint(actor, repo)
        assert digest == value.fingerprint(actor, repo)
        assert digest != value.fingerprint(uuid4(), repo)
        assert digest != value.fingerprint(actor, uuid4())
        assert "synthetic" not in repr(value)
        assert value.content_hash not in repr(value)
