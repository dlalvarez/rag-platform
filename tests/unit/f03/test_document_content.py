"""The private download must verify actual bytes against the SQL version before success."""

import hashlib
import io
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest

from rag_platform.documents.content import DocumentService
from rag_platform.documents.errors import DocumentError
from rag_platform.documents.storage import Original, inspect_original
from rag_platform.documents.validation import UploadSpool

BODY = b"synthetic original\n"


def fixture(monkeypatch, body=BODY, *, denied=False):
    import rag_platform.documents.content as module

    repo, version = uuid4(), uuid4()
    row = SimpleNamespace(
        version_id=version,
        content_hash=hashlib.sha256(BODY).hexdigest(),
        byte_size=len(BODY),
        mime="text/plain",
        filename="synthetic.txt",
        blob_key=f"f03/{repo.hex}/{version.hex}",
    )
    spools = []

    class Tracked(UploadSpool):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            spools.append(self)

    @contextmanager
    def download(*args):
        with io.BytesIO(body) as response:
            yield response

    def require(*args):
        if denied:
            raise DocumentError("ROLE_DENIED")

    service = DocumentService(SimpleNamespace(require=require), SimpleNamespace(download=download))
    monkeypatch.setattr(module, "UploadSpool", Tracked)
    monkeypatch.setattr(service, "_row", lambda *a: row)
    return service, repo, spools


@pytest.mark.parametrize(
    "body", [b"wrong same size!!!\n", b"short", BODY + b"long", b"\xff" * len(BODY)]
)
def test_corrupt_or_truncated_original_never_returns_download(monkeypatch, body):
    service, repo, spools = fixture(monkeypatch, body)
    with pytest.raises(DocumentError, match="DEPENDENCY_UNAVAILABLE"):
        service.original(None, uuid4(), repo, uuid4())
    assert len(spools) == 1 and spools[0].file.closed


def test_membership_or_acl_loss_after_remote_read_closes_spool(monkeypatch):
    service, repo, spools = fixture(monkeypatch, denied=True)
    with pytest.raises(DocumentError, match="ROLE_DENIED"):
        service.original(None, uuid4(), repo, uuid4())
    assert spools[0].file.closed


def test_valid_original_remains_private_until_response_closes(monkeypatch):
    service, repo, spools = fixture(monkeypatch)
    prepared = service.original(None, uuid4(), repo, uuid4())
    try:
        assert b"".join(prepared.chunks()) == BODY
        assert not spools[0].file.closed
        assert repr(prepared) == "Download(<private>)"
    finally:
        prepared.close()
    assert spools[0].file.closed


def test_proxy_refuses_s3_owner_version_or_size_mismatch():
    original = Original(uuid4(), uuid4(), "a" * 64, 10, "text/plain")
    metadata = {
        "x-amz-meta-rag-repository": str(original.repository_id),
        "x-amz-meta-rag-version": str(original.version_id),
        "x-amz-meta-rag-sha256": original.content_hash,
        "x-amz-meta-rag-receipt": str(uuid4()),
        "x-amz-meta-rag-fingerprint": "b" * 64,
        "x-amz-meta-rag-md5": "c" * 32,
    }
    info = SimpleNamespace(size=10, content_type="text/plain", etag="c" * 32, metadata=metadata)
    client = SimpleNamespace(stat_object=lambda *a: info)
    assert inspect_original(client, "synthetic", original) == "c" * 32
    for field in ("x-amz-meta-rag-repository", "x-amz-meta-rag-version", "x-amz-meta-rag-sha256"):
        saved = metadata[field]
        metadata[field] = "wrong"
        with pytest.raises(DocumentError):
            inspect_original(client, "synthetic", original)
        metadata[field] = saved


def test_download_has_total_io_deadline_and_cleans_spool(monkeypatch):
    import rag_platform.documents.content as module

    service, repo, spools = fixture(monkeypatch)
    readings = iter([0, 0, 21])
    monkeypatch.setattr(module.time, "monotonic", lambda: next(readings))
    with pytest.raises(DocumentError):
        service.original(None, uuid4(), repo, uuid4())
    assert spools[0].file.closed
