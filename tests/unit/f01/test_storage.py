"""T003 offline policy/ownership checks. Real denials run in storage_check."""

import importlib.util
import json
import sys
from pathlib import Path
from uuid import uuid4

import pytest
import yaml
from minio.error import MinioAdminException

from rag_platform.providers.secrets import Credential
from rag_platform.provisioning.storage import (
    StorageError,
    StorageNames,
    StorageProvisioner,
    StorageTarget,
    admin_error,
    policy_signature,
    tenant_policy,
)

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("value", ["slug", "uuid/bucket", None, 1])
def test_storage_names_require_internal_uuid(value):
    with pytest.raises(ValueError):
        StorageNames(value)


def test_policy_allows_only_explicit_own_bucket_actions():
    names, other, ref = StorageNames(uuid4()), StorageNames(uuid4()), uuid4()
    document = tenant_policy(names, ref)
    statements = document["Statement"]
    assert {action for s in statements for action in s["Action"]} == {
        "s3:ListBucket",
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
    }
    assert statements[0]["Resource"] == ["arn:aws:s3:::" + names.bucket]
    assert statements[1]["Resource"] == ["arn:aws:s3:::" + names.bucket + "/*"]
    assert other.bucket not in json.dumps(document)
    changed = json.loads(json.dumps(document))
    changed["Statement"][1]["Action"].append("admin:CreateUser")
    assert policy_signature(changed) != policy_signature(document)
    changed["Statement"][1]["Resource"] = ["*"]
    assert policy_signature(changed) != policy_signature(document)


@pytest.mark.parametrize("extra", ["Principal", "Condition", "NotAction"])
def test_unexpected_policy_semantics_are_rejected(extra):
    policy = tenant_policy(StorageNames(uuid4()), uuid4())
    policy["Statement"][0][extra] = "*"
    with pytest.raises(StorageError):
        policy_signature(policy)


@pytest.mark.parametrize(
    "url",
    [
        "http://minio:9000",
        "https://user:password@minio:9000",
        "https://minio:9000/customer",
        "https://minio:9000?token=value",
        "https://minio:9000#fragment",
    ],
)
def test_endpoint_cannot_disable_tls_or_embed_credentials(url):
    with pytest.raises(ValueError):
        StorageTarget(url, Path("/public/ca.crt"))


@pytest.mark.parametrize(
    "http,code,expected",
    [
        ("404", "XMinioAdminNoSuchUser", "MISSING"),
        ("404", "XMinioAdminNoSuchPolicy", "MISSING"),
        ("404", "Unknown", "STORAGE_UNAVAILABLE"),
        ("403", "AccessDenied", "STORAGE_DENIED"),
        ("500", "InternalError", "STORAGE_UNAVAILABLE"),
    ],
)
def test_admin_error_classification_never_exposes_body(http, code, expected):
    error = MinioAdminException(http, json.dumps({"Code": code, "secret": "never-echo-marker"}))
    assert admin_error(error) == expected
    assert "never-echo-marker" not in str(StorageError(admin_error(error)))


def test_foreign_bucket_is_preserved_before_any_mutation():
    names = StorageNames(uuid4())
    calls = []

    class S3:
        def bucket_exists(self, bucket):
            return True

        def get_bucket_tags(self, bucket):
            return {"synthetic-owner": "foreign"}

        def make_bucket(self, *args, **kwargs):
            calls.append("mutation")

    class Admin:
        def policy_info(self, policy):
            raise MinioAdminException("404", '{"Code":"XMinioAdminNoSuchPolicy"}')

        def user_info(self, user):
            raise MinioAdminException("404", '{"Code":"XMinioAdminNoSuchUser"}')

        def user_add(self, *args):
            calls.append("mutation")

    provisioner = object.__new__(StorageProvisioner)
    provisioner.s3, provisioner.admin = S3(), Admin()
    with pytest.raises(StorageError, match="OWNERSHIP_CONFLICT"):
        provisioner.provision(names, uuid4(), Credential(names.user, "synthetic-not-real"))
    assert calls == []


def test_existing_iam_group_is_not_silently_adopted():
    names, ref = StorageNames(uuid4()), uuid4()

    class S3:
        def bucket_exists(self, bucket):
            return False

    class Admin:
        def policy_info(self, policy):
            return json.dumps({"policy": tenant_policy(names, ref)})

        def user_info(self, user):
            return json.dumps(
                {"policyName": names.policy, "status": "enabled", "memberOf": ["foreign-admin"]}
            )

    provisioner = object.__new__(StorageProvisioner)
    provisioner.s3, provisioner.admin = S3(), Admin()
    with pytest.raises(StorageError, match="OWNERSHIP_CONFLICT"):
        provisioner.inspect(names, ref)


def test_partial_storage_preparation_is_never_overwritten(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("f01_storage_host", ROOT / "scripts/f01_host.py")
    host = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(host)
    for folder in ("tls", "secrets", "minio"):
        (tmp_path / folder).mkdir()
    marker = tmp_path / "minio/preserve"
    marker.write_text("synthetic existing data")
    monkeypatch.setattr(host, "DATA", tmp_path)
    monkeypatch.setattr(host, "validate_host", lambda **kwargs: None)
    with pytest.raises(ValueError, match="overwritten"):
        host.prepare_storage()
    assert marker.read_text() == "synthetic existing data"


def test_storage_profile_keeps_bootstrap_out_of_default_tools():
    config = yaml.safe_load((ROOT / "ops/f01/compose.yaml").read_text())
    assert not config["services"]["minio"].get("ports")
    assert config["services"]["minio"]["environment"]["MINIO_BROWSER"] == "off"
    assert "--certs-dir" in config["services"]["minio"]["command"]
    assert not config["services"]["tools"].get("secrets")
    assert "storage_admin_password" in config["services"]["s3-check"]["secrets"]


def test_tenant_storage_check_rejects_automation_before_credentials(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(
        "f01_storage_cli", ROOT / "scripts/f01_storage_check.py"
    )
    check = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(check)
    monkeypatch.setattr(sys, "argv", ["f01_storage_check.py", "tenants"])
    monkeypatch.setattr(check, "tty_required", lambda: (_ for _ in ()).throw(RuntimeError()))
    monkeypatch.setattr(check, "admin_credential", lambda: pytest.fail("Must not read credentials"))
    with pytest.raises(SystemExit, match="START"):
        check.main()


def test_foreign_operation_policy_cannot_disable_principal():
    tenant, operation, ref = uuid4(), uuid4(), uuid4()
    names = StorageNames(tenant, operation)
    calls = []

    class S3:
        def bucket_exists(self, bucket):
            return False

    class Admin:
        def policy_info(self, policy):
            other = StorageNames(tenant, uuid4())
            return json.dumps({"policy": tenant_policy(other, ref)})

        def user_info(self, user):
            return json.dumps({"policyName": names.policy, "status": "enabled"})

        def user_disable(self, user):
            calls.append(user)

    provisioner = object.__new__(StorageProvisioner)
    provisioner.s3, provisioner.admin = S3(), Admin()
    with pytest.raises(StorageError, match="OWNERSHIP_CONFLICT"):
        provisioner.withdraw(names, ref)
    assert calls == []


def test_disabled_owned_principal_is_reconcilable_without_password_reset():
    names, ref = StorageNames(uuid4(), uuid4()), uuid4()
    calls = []

    class S3:
        def bucket_exists(self, bucket):
            return False

    class Admin:
        def policy_info(self, policy):
            return json.dumps({"policy": tenant_policy(names, ref)})

        def user_info(self, user):
            return json.dumps({"policyName": names.policy, "status": "disabled"})

        def user_disable(self, user):
            calls.append(user)

    provisioner = object.__new__(StorageProvisioner)
    provisioner.s3, provisioner.admin = S3(), Admin()
    with pytest.raises(StorageError):
        provisioner.inspect(names, ref)
    assert provisioner.inspect(names, ref, allow_disabled=True) == (False, True, True)
    assert provisioner.withdraw(names, ref) == {
        "STORAGE_BUCKET": "ABSENT",
        "STORAGE_USER": "ACCESS_REVOKED",
    }
    assert calls == [names.user]


def test_legacy_resources_cannot_be_compensated_by_saga():
    provisioner = object.__new__(StorageProvisioner)
    with pytest.raises(StorageError, match="OWNERSHIP_CONFLICT"):
        provisioner.withdraw(StorageNames(uuid4()), uuid4())
