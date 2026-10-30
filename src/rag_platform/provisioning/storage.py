"""T003 private bucket/IAM step; no saga, resolver, public onboarding or deletion."""

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

from minio import Minio, MinioAdmin
from minio.commonconfig import Tags
from minio.credentials import StaticProvider
from minio.error import MinioAdminException, S3Error
from urllib3 import PoolManager, Timeout
from urllib3.exceptions import HTTPError

from rag_platform.providers.secrets import Credential

REGION = "us-east-1"


class StorageError(RuntimeError):
    CODES = {
        "OWNERSHIP_CONFLICT",
        "STORAGE_DENIED",
        "STORAGE_UNAVAILABLE",
        "STORAGE_INVALID",
        "ISOLATION_FAILED",
    }

    def __init__(self, code="OWNERSHIP_CONFLICT"):
        super().__init__(code if code in self.CODES else "STORAGE_INVALID")


@dataclass(frozen=True)
class StorageNames:
    tenant: UUID

    def __post_init__(self):
        if not isinstance(self.tenant, UUID):
            raise ValueError("Internal UUID required")

    @property
    def bucket(self):
        return "rag-t-" + self.tenant.hex

    @property
    def user(self):
        return "f01-t-" + self.tenant.hex

    @property
    def policy(self):
        return "f01-t-" + self.tenant.hex


def tenant_policy(names: StorageNames, ref: UUID):
    if not isinstance(ref, UUID):
        raise ValueError("Opaque secret reference required")
    marker = "Tenant" + names.tenant.hex + "Ref" + ref.hex
    arn = "arn:aws:s3:::" + names.bucket
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": marker + "List",
                "Effect": "Allow",
                "Action": ["s3:ListBucket"],
                "Resource": [arn],
            },
            {
                "Sid": marker + "Objects",
                "Effect": "Allow",
                "Action": ["s3:DeleteObject", "s3:GetObject", "s3:PutObject"],
                "Resource": [arn + "/*"],
            },
        ],
    }


def policy_signature(value):
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict) or set(value) != {"Version", "Statement"}:
        raise StorageError()
    statements = []
    for item in value["Statement"]:
        if set(item) != {"Sid", "Effect", "Action", "Resource"}:
            raise StorageError()

        def values(key, item=item):
            raw = item[key]
            return tuple(sorted([raw] if isinstance(raw, str) else raw))

        statements.append((item["Sid"], item["Effect"], values("Action"), values("Resource")))
    return value["Version"], tuple(sorted(statements))


def admin_error(error):
    """Inspect only the pinned SDK exception internals; never expose body/exception text."""
    try:
        code = json.loads(error._body).get("Code")
    except (TypeError, ValueError, AttributeError):
        code = None
    missing = {"XMinioAdminNoSuchUser", "XMinioAdminNoSuchPolicy", "NoSuchUser", "NoSuchPolicy"}
    if error._code == "404" and code in missing:
        return "MISSING"
    if error._code in ("401", "403"):
        return "STORAGE_DENIED"
    return "STORAGE_UNAVAILABLE"


class StorageTarget:
    def __init__(self, endpoint: str, ca: Path):
        url = urlsplit(endpoint)
        if (
            url.scheme != "https"
            or not url.hostname
            or url.username
            or url.password
            or url.path not in ("", "/")
            or url.query
            or url.fragment
        ):
            raise ValueError("Trusted HTTPS storage endpoint required")
        self.endpoint = endpoint.rstrip("/")
        self.authority = url.netloc
        self.http = PoolManager(
            cert_reqs="CERT_REQUIRED",
            ca_certs=str(ca),
            timeout=Timeout(connect=3, read=5),
            retries=False,
            maxsize=2,
        )

    def s3(self, credential: Credential | None = None):
        return Minio(
            self.authority,
            access_key=credential.username if credential else None,
            secret_key=credential.password if credential else None,
            secure=True,
            region=REGION,
            http_client=self.http,
        )

    def admin(self, credential: Credential):
        return MinioAdmin(
            endpoint=self.authority,
            credentials=StaticProvider(credential.username, credential.password),
            secure=True,
            region=REGION,
            http_client=self.http,
        )

    def close(self):
        self.http.clear()


class StorageProvisioner:
    def __init__(self, target: StorageTarget, credential: Credential):
        self.target = target
        self.s3 = target.s3(credential)
        self.admin = target.admin(credential)

    def optional_admin(self, function, *args):
        try:
            return json.loads(function(*args))
        except MinioAdminException as error:
            code = admin_error(error)
            if code == "MISSING":
                return None
            raise StorageError(code) from None
        except (TypeError, ValueError):
            raise StorageError("STORAGE_INVALID") from None

    def inspect(self, names: StorageNames, ref: UUID):
        """Read-only ownership checks. A matching name never permits adoption."""
        try:
            bucket_exists = self.s3.bucket_exists(names.bucket)
            policy = self.optional_admin(self.admin.policy_info, names.policy)
            user = self.optional_admin(self.admin.user_info, names.user)
            expected = tenant_policy(names, ref)
            if policy is not None:
                document = policy.get("policy", policy)
                if policy_signature(document) != policy_signature(expected):
                    raise StorageError()
            if user is not None:
                if (
                    policy is None
                    or user.get("policyName") != names.policy
                    or user.get("status") not in ("enabled", "on")
                    or user.get("memberOf")
                ):
                    raise StorageError()
            if bucket_exists:
                expected_tags = {
                    "rag-platform-tenant": str(names.tenant),
                    "rag-platform-secret-ref": str(ref),
                    "rag-platform-contract": "f01-t003-v1",
                }
                if dict(self.s3.get_bucket_tags(names.bucket) or {}) != expected_tags:
                    raise StorageError()
                self.assert_private(names)
            return bucket_exists, policy is not None, user is not None
        except MinioAdminException as error:
            raise StorageError(admin_error(error)) from None
        except S3Error as error:
            raise StorageError(
                "STORAGE_DENIED" if error.code == "AccessDenied" else "STORAGE_UNAVAILABLE"
            ) from None
        except (HTTPError, OSError):
            raise StorageError("STORAGE_UNAVAILABLE") from None

    def assert_private(self, names):
        try:
            self.s3.get_bucket_policy(names.bucket)
        except S3Error as error:
            if error.code == "NoSuchBucketPolicy":
                return
            raise
        raise StorageError()

    def provision(self, names: StorageNames, ref: UUID, credential: Credential):
        if credential.username != names.user:
            raise StorageError()
        try:
            bucket, policy, user = self.inspect(names, ref)
            if not bucket:
                self.s3.make_bucket(names.bucket, location=REGION)
                tags = Tags.new_bucket_tags()
                tags.update(
                    {
                        "rag-platform-tenant": str(names.tenant),
                        "rag-platform-secret-ref": str(ref),
                        "rag-platform-contract": "f01-t003-v1",
                    }
                )
                self.s3.set_bucket_tags(names.bucket, tags)
            self.assert_private(names)
            if not policy:
                self.admin.policy_add(names.policy, policy=tenant_policy(names, ref))
            if not user:
                self.admin.user_add(names.user, credential.password)
                self.admin.attach_policy([names.policy], user=names.user)
            if self.inspect(names, ref) != (True, True, True):
                raise StorageError()
        except MinioAdminException as error:
            raise StorageError(admin_error(error)) from None
        except S3Error as error:
            raise StorageError(
                "STORAGE_DENIED" if error.code == "AccessDenied" else "STORAGE_UNAVAILABLE"
            ) from None
        except (HTTPError, OSError):
            raise StorageError("STORAGE_UNAVAILABLE") from None
