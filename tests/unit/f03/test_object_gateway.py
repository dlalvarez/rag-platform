"""Pinned SDK streaming/conditional signing and ownership/authorization negative paths."""

import hashlib
import io
import ssl
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
import urllib3
from minio import Minio

from rag_platform.documents.errors import DocumentError
from rag_platform.documents.storage import (
    Blob,
    BoundedBody,
    ObjectGateway,
    conditional_put,
    inspect_object,
)
from rag_platform.documents.validation import CHUNK, UploadSpool
from rag_platform.tenancy.contracts import SecretRef


def blob(file):
    return Blob(
        uuid4(), uuid4(), uuid4(), "b" * 64, file.content_hash, file.byte_size, file.mime, file.md5
    )


def test_native_sdk_signs_conditional_stream_without_reading_full_body(monkeypatch, caplog):
    data = ("synthetic streaming fixture\n" * 10000).encode()
    with UploadSpool("synthetic.txt", "text/plain") as spool:
        spool.accept(data)
        file = spool.finish()
        manifest = blob(file)
        pool = urllib3.PoolManager()
        client = Minio(
            "minio:9000",
            access_key="synthetic-access-key",
            secret_key="synthetic-sensitive-marker",
            secure=True,
            region="us-east-1",
            http_client=pool,
        )
        requests = []

        def urlopen(method, url, *, body, headers, **kwargs):
            assert method == "PUT" and "?" not in url
            assert headers["If-None-Match"] == "*"
            assert headers["Content-Length"] == str(len(data))
            assert headers["x-amz-content-sha256"] == "UNSIGNED-PAYLOAD"
            assert "if-none-match" in headers["Authorization"].lower()
            assert "synthetic-sensitive-marker" not in url
            digest, largest = hashlib.sha256(), 0
            while piece := body.read(CHUNK * 10):
                largest = max(largest, len(piece))
                digest.update(piece)
            assert largest <= CHUNK and digest.hexdigest() == file.content_hash
            requests.append(method)
            return urllib3.HTTPResponse(
                status=200, body=b"", headers={"etag": '"' + file.md5 + '"'}
            )

        monkeypatch.setattr(pool, "urlopen", urlopen)
        assert conditional_put(client, "synthetic-bucket", manifest, file) == file.md5
        assert requests == ["PUT"]
        assert "synthetic-sensitive-marker" not in caplog.text


def test_trace_or_mismatched_file_rejected_before_http(monkeypatch):
    with UploadSpool("file.txt", "text/plain") as spool:
        spool.accept(b"synthetic")
        file = spool.finish()
        client = SimpleNamespace(
            _trace_stream=io.StringIO(), _url_open=lambda *_: pytest.fail("HTTP request")
        )
        with pytest.raises(DocumentError):
            conditional_put(client, "synthetic", blob(file), file)
        assert client._trace_stream.getvalue() == ""


def test_body_length_and_bounded_reads():
    body = BoundedBody(io.BytesIO(b"a" * (CHUNK + 3)), CHUNK + 3)
    assert len(body) == CHUNK + 3 and len(body.read(-1)) == CHUNK
    assert body.read(0) == b"" and body.read(CHUNK * 2) == b"aaa"
    with pytest.raises(DocumentError):
        BoundedBody(io.BytesIO(b"short"), 99)


@pytest.mark.parametrize(
    "field,value",
    [
        ("receipt_id", "../other"),
        ("repository_id", "not-uuid"),
        ("version_id", None),
        ("content_hash", "not-a-hash"),
        ("byte_size", True),
        ("byte_size", 0),
        ("mime", "application/x-executable"),
        ("md5", "not-a-checksum"),
    ],
)
def test_manifest_rejects_untyped_ids_or_unbounded_metadata(field, value):
    values = dict(
        receipt_id=uuid4(),
        repository_id=uuid4(),
        version_id=uuid4(),
        fingerprint="b" * 64,
        content_hash="a" * 64,
        byte_size=10,
        mime="text/plain",
        md5="c" * 32,
    )
    values[field] = value
    with pytest.raises(DocumentError):
        Blob(**values)


def test_existing_key_requires_every_ownership_marker_and_actual_etag():
    manifest = Blob(uuid4(), uuid4(), uuid4(), "b" * 64, "a" * 64, 10, "text/plain", "c" * 32)
    info = SimpleNamespace(
        size=10,
        content_type="text/plain",
        etag="c" * 32,
        metadata={"X-Amz-Meta-" + key: value for key, value in manifest.metadata.items()},
    )
    client = SimpleNamespace(stat_object=lambda *_: info)
    assert inspect_object(client, "synthetic", manifest) == "c" * 32
    info.metadata["X-Amz-Meta-rag-receipt"] = str(uuid4())
    with pytest.raises(DocumentError, match="STATE_CONFLICT"):
        inspect_object(client, "synthetic", manifest)


def test_acl_denial_precedes_secret_and_storage_client():
    repository = SimpleNamespace(
        control=None,
        authority=None,
        require=lambda *_: (_ for _ in ()).throw(DocumentError("ROLE_DENIED")),
    )
    store = SimpleNamespace(read=lambda *_: pytest.fail("secret read"))
    gateway = ObjectGateway(repository, store, Path("/ca"))
    with pytest.raises(DocumentError, match="ROLE_DENIED"):
        with gateway.client(None, uuid4(), uuid4(), "upload"):
            pytest.fail("storage opened")


@pytest.mark.parametrize("mismatch", ["endpoint", "bucket", "version"])
def test_catalog_mismatch_denied_before_secret_or_network(mismatch):
    tenant, ref = uuid4(), SecretRef(uuid4(), 1)
    row = SimpleNamespace(
        endpoint="https://minio:9000",
        bucket="rag-t-" + tenant.hex,
        credential_ref=ref.id,
        credential_version=1,
    )
    if mismatch == "endpoint":
        row.endpoint = "https://untrusted.example"
    elif mismatch == "bucket":
        row.bucket = "another-bucket"
    else:
        row.credential_version = 2

    class Control:
        @contextmanager
        def connect(self):
            yield SimpleNamespace(execute=lambda *_: SimpleNamespace(one_or_none=lambda: row))

    context = SimpleNamespace(tenant_id=tenant, storage_ref=ref)
    repository = SimpleNamespace(
        control=Control(),
        authority=SimpleNamespace(validate=lambda *_: context),
        require=lambda *_: None,
    )
    gateway = ObjectGateway(
        repository,
        SimpleNamespace(read=lambda *_: pytest.fail("secret read")),
        Path(ssl.get_default_verify_paths().cafile),
    )
    with pytest.raises(DocumentError):
        with gateway.client(context, uuid4(), uuid4(), "read"):
            pytest.fail("storage client opened")


def test_early_conditional_rejection_discards_connection_without_put_retry(monkeypatch):
    from minio.error import S3Error

    with UploadSpool("file.txt", "text/plain") as spool:
        spool.accept(b"synthetic early rejection")
        file = spool.finish()
        pool = urllib3.PoolManager()
        client = Minio(
            "minio:9000",
            access_key="synthetic-key",
            secret_key="synthetic-secret",
            secure=True,
            region="us-east-1",
            http_client=pool,
        )
        calls = []
        response = urllib3.HTTPResponse(
            status=412,
            headers={"Content-Type": "application/xml"},
            body=b"<Error><Code>PreconditionFailed</Code><Message>synthetic</Message>"
            b"<Resource>/synthetic</Resource><RequestId>synthetic</RequestId>"
            b"<HostId>synthetic</HostId></Error>",
        )

        def urlopen(*_, **__):
            calls.append("PUT")
            return response  # Simulate a reply before the request body was consumed.

        monkeypatch.setattr(pool, "urlopen", urlopen)
        monkeypatch.setattr(pool, "clear", lambda: calls.append("CLEAR"))
        with pytest.raises(S3Error) as raised:
            conditional_put(client, "synthetic-bucket", blob(file), file)
        assert raised.value.code == "PreconditionFailed"
        assert calls == ["PUT", "CLEAR"]
