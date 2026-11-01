"""Authorized private S3 objects; conditional creation and bounded streams, no admin."""

import base64
import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import wraps
from uuid import UUID

import sqlalchemy as sa
from minio.error import S3Error

from rag_platform.control.identity import AccessError
from rag_platform.control.models import StorageLocation
from rag_platform.documents.errors import DocumentError
from rag_platform.documents.validation import CHUNK, MAX_BYTES, MIMES, ValidatedFile
from rag_platform.provisioning.storage import REGION, StorageNames, StorageTarget
from rag_platform.tenancy.contracts import SecretRef


@dataclass(frozen=True, slots=True, repr=False)
class Blob:
    receipt_id: UUID
    repository_id: UUID
    version_id: UUID
    fingerprint: str = field(repr=False)
    content_hash: str = field(repr=False)
    byte_size: int
    mime: str
    md5: str | None = field(default=None, repr=False)

    def __post_init__(self):
        if (
            not all(
                isinstance(value, UUID)
                for value in (self.receipt_id, self.repository_id, self.version_id)
            )
            or not all(
                isinstance(value, str) and re.fullmatch("[0-9a-f]{64}", value)
                for value in (self.fingerprint, self.content_hash)
            )
            or type(self.byte_size) is not int
            or not 1 <= self.byte_size <= MAX_BYTES
            or not isinstance(self.mime, str)
            or self.mime not in MIMES
            or (
                self.md5 is not None
                and (
                    not isinstance(self.md5, str) or re.fullmatch("[0-9a-f]{32}", self.md5) is None
                )
            )
        ):
            raise DocumentError("INPUT_INVALID")

    def __repr__(self):
        return "Blob(<private>)"

    @property
    def key(self):
        return f"f03/{self.repository_id.hex}/{self.version_id.hex}"

    @property
    def metadata(self):
        values = {
            "rag-receipt": str(self.receipt_id),
            "rag-repository": str(self.repository_id),
            "rag-version": str(self.version_id),
            "rag-fingerprint": self.fingerprint,
            "rag-sha256": self.content_hash,
        }
        if self.md5 is not None:
            values["rag-md5"] = self.md5
        return values


class BoundedBody:
    """Pinned SDK calls len(), urllib3 reads chunks; never materialize the full body."""

    def __init__(self, source, length):
        self.source, self.length = source, length
        source.seek(0, 2)
        if source.tell() != length:
            raise DocumentError("INPUT_INVALID")
        source.seek(0)

    def __len__(self):
        return self.length

    def __repr__(self):
        return "BoundedBody(<private>)"

    def read(self, size=-1):
        return self.source.read(CHUNK if size is None or size < 0 else min(size, CHUNK))


def conditional_put(client, bucket, blob, file):
    """One native SigV4 attempt, private pinned SDK extension verified in integration.

    minio 7.2.20 _build_headers uses len(body), HTTPS UNSIGNED-PAYLOAD and the supplied
    Content-MD5; it does not hash/read the complete file. No presigned URL or SDK trace.
    """
    if (
        not isinstance(file, ValidatedFile)
        or file.byte_size != blob.byte_size
        or file.content_hash != blob.content_hash
        or file.md5 != blob.md5
        or file.mime != blob.mime
        or getattr(client, "_trace_stream", None) is not None
    ):
        raise DocumentError("INPUT_INVALID")
    headers = {
        "Content-Type": blob.mime,
        "If-None-Match": "*",
        "Content-MD5": base64.b64encode(bytes.fromhex(file.md5)).decode("ascii"),
        **{"X-Amz-Meta-" + key: value for key, value in blob.metadata.items()},
    }
    try:
        response = client._url_open(
            "PUT",
            REGION,
            bucket_name=bucket,
            object_name=blob.key,
            body=BoundedBody(file.file, file.byte_size),
            headers=headers,
            no_body_trace=True,
        )
    except S3Error as error:
        # An early rejected streamed PUT must not leave its connection available
        # for a subsequent HEAD. No automatic PUT retry or unsafe overwrite.
        error.response.close()
        error.response.release_conn()
        client._http.clear()
        raise
    try:
        return response.headers.get("etag", "").strip('"')
    finally:
        response.close()
        response.release_conn()


def inspect_object(client, bucket, blob):
    try:
        value = client.stat_object(bucket, blob.key)
    except S3Error as error:
        if error.code == "NoSuchKey":
            return None
        raise DocumentError() from None
    metadata = {str(key).lower(): str(item) for key, item in value.metadata.items()}
    expected = {"x-amz-meta-" + key: item for key, item in blob.metadata.items()}
    md5 = metadata.get("x-amz-meta-rag-md5", "")
    if (
        value.size != blob.byte_size
        or value.content_type != blob.mime
        or any(metadata.get(key) != item for key, item in expected.items())
        or re.fullmatch("[0-9a-f]{32}", md5) is None
        or value.etag != md5
    ):
        raise DocumentError("STATE_CONFLICT")
    return value.etag


def closed_storage(function):
    @wraps(function)
    def operation(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (DocumentError, AccessError):
            raise
        except Exception:
            raise DocumentError() from None

    return operation


class ObjectGateway:
    def __init__(self, repository_service, store, ca, *, allowed_endpoints=("https://minio:9000",)):
        self.repositories, self.store, self.ca = repository_service, store, ca
        self.control = repository_service.control
        self.authority = repository_service.authority
        self.allowed_endpoints = frozenset(allowed_endpoints)

    @contextmanager
    def client(self, context, trace, repo, action):
        target = None
        try:
            self.repositories.require(context, trace, repo, action)
            checked = self.authority.validate(context, trace)
            with self.control.connect() as c:
                row = c.execute(
                    sa.select(
                        StorageLocation.endpoint,
                        StorageLocation.bucket,
                        StorageLocation.credential_ref,
                        StorageLocation.credential_version,
                    ).where(StorageLocation.tenant_id == checked.tenant_id)
                ).one_or_none()
            if row is None or row.endpoint not in self.allowed_endpoints:
                raise DocumentError()
            names = StorageNames(checked.tenant_id)
            ref = SecretRef(row.credential_ref, row.credential_version)
            if ref != checked.storage_ref or row.bucket != names.bucket:
                raise DocumentError("STATE_CONFLICT")
            credential = self.store.read(ref)
            if credential.username != names.user:
                raise DocumentError()
            target = StorageTarget(row.endpoint, self.ca)
            client = target.s3(credential)
            del credential
        except (DocumentError, AccessError):
            if target is not None:
                target.close()
            raise
        except Exception:
            if target is not None:
                target.close()
            raise DocumentError() from None
        # Cleanup must not translate a consumer's deliberate fault/test exception
        # into a storage failure; public gateway operations translate transport errors.
        try:
            yield client, row.bucket
        finally:
            target.close()

    @closed_storage
    def inspect(self, context, trace, blob, *, action="upload"):
        with self.client(context, trace, blob.repository_id, action) as (client, bucket):
            return inspect_object(client, bucket, blob)

    @closed_storage
    def create(self, context, trace, blob, file):
        with self.client(context, trace, blob.repository_id, "upload") as (client, bucket):
            if inspect_object(client, bucket, blob) is not None:
                return False
            try:
                conditional_put(client, bucket, blob, file)
            except S3Error as error:
                if error.code not in {"PreconditionFailed", "ConditionalRequestConflict"}:
                    raise DocumentError() from None
                if inspect_object(client, bucket, blob) is None:
                    raise DocumentError("STATE_CONFLICT") from None
                return False
            if inspect_object(client, bucket, blob) is None:
                raise DocumentError()
            return True

    @contextmanager
    def original(self, context, trace, blob):
        with self.client(context, trace, blob.repository_id, "read") as (client, bucket):
            etag = inspect_object(client, bucket, blob)
            if etag is None:
                raise DocumentError()
            response = client._url_open(
                "GET",
                REGION,
                bucket_name=bucket,
                object_name=blob.key,
                headers={"If-Match": '"' + etag + '"'},
                preload_content=False,
                no_body_trace=True,
            )
            try:
                yield response
            finally:
                response.close()
                response.release_conn()
