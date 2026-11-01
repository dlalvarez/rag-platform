"""Fail-closed boundaries: no SQL completion or object repair after loss of authority."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from rag_platform.control.identity import AccessError
from rag_platform.documents.errors import DocumentError
from rag_platform.documents.receipt import Plan, ReceiptService, Received, quota_key
from rag_platform.documents.validation import UploadSpool


class Authority:
    def __init__(self, events, revoked_at=None):
        self.events, self.revoked_at, self.calls = events, revoked_at, 0

    def validate(self, context, trace):
        self.events.append("authority")
        self.calls += 1
        if self.calls == self.revoked_at:
            raise AccessError("MEMBERSHIP_REQUIRED")
        return context


class Gateway:
    def __init__(self, events, present=True):
        self.events, self.present = events, present

    def inspect(self, *_):
        self.events.append("inspect")
        return "owned" if self.present else None

    def create(self, *_):
        self.events.append("create")


class Probe(ReceiptService):
    def __init__(self, *, committed=False, present=True, revoked_at=None):
        self.events = []
        repos = SimpleNamespace(
            authority=Authority(self.events, revoked_at),
            require=lambda *_: self.events.append("preflight"),
        )
        super().__init__(repos, Gateway(self.events, present))
        self.plan = Plan(
            uuid4(),
            uuid4(),
            uuid4(),
            uuid4(),
            uuid4(),
            uuid4(),
            "COMMITTED" if committed else "PENDING",
            "a" * 64,
        )

    def _reserve(self, *_):
        self.events.append("reserve")
        return self.plan

    def _stored(self, *_):
        self.events.append("journal")

    def _complete(self, *_):
        self.events.append("complete")
        return Received({"logical": "fixture"}, True)

    def _duplicate(self, *_):
        self.events.append("duplicate")
        return Received({"logical": "fixture"}, False)


def call(service, *, key="synthetic-key-123456"):
    with UploadSpool("fixture.txt", "text/plain") as spool:
        spool.accept(b"synthetic")
        context = SimpleNamespace(principal_id=service.plan.principal_id)
        return service.receive(context, uuid4(), service.plan.repository_id, key, spool.finish())


def test_committed_missing_original_is_not_silently_repaired():
    service = Probe(committed=True, present=False)
    with pytest.raises(DocumentError, match="DEPENDENCY_UNAVAILABLE"):
        call(service)
    assert service.events == ["preflight", "authority", "reserve", "inspect"]


def test_committed_replay_checks_storage_and_does_not_create_or_complete():
    service = Probe(committed=True)
    assert call(service).created is False
    assert service.events == ["preflight", "authority", "reserve", "inspect", "duplicate"]


@pytest.mark.parametrize(
    "at,expected",
    [
        (2, ["preflight", "authority", "reserve", "create", "authority"]),
        (
            3,
            [
                "preflight",
                "authority",
                "reserve",
                "create",
                "authority",
                "journal",
                "inspect",
                "authority",
            ],
        ),
    ],
)
def test_authority_revoked_between_durable_stages_blocks_completion(at, expected):
    service = Probe(revoked_at=at)
    with pytest.raises(AccessError):
        call(service)
    assert service.events == expected
    assert "complete" not in service.events


def test_missing_object_after_journal_cannot_become_received():
    service = Probe(present=False)
    with pytest.raises(DocumentError):
        call(service)
    assert "journal" in service.events and "complete" not in service.events


@pytest.mark.parametrize("key", ["short", "x" * 129, "a" * 15 + "\n", "ñ" * 20, None])
def test_bad_idempotency_keys_never_reserve_or_write_storage(key):
    service = Probe()
    with pytest.raises(DocumentError, match="INPUT_INVALID"):
        call(service, key=key)
    assert service.events == ["preflight"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"tenant_bytes": 0},
        {"tenant_bytes": True},
        {"tenant_bytes": 1024**3 + 1},
        {"lease_seconds": 1},
        {"lease_seconds": 61},
        {"lease_seconds": True},
        {"max_receipts": 0},
        {"max_receipts": 10001},
        {"max_receipts": True},
    ],
)
def test_invalid_resource_budgets_rejected(kwargs):
    with pytest.raises(ValueError):
        ReceiptService(None, None, **kwargs)


def test_quota_lock_is_tenant_scoped_stable_signed_int64():
    first, second = uuid4(), uuid4()
    assert quota_key(first) == quota_key(first) != quota_key(second)
    assert -(2**63) <= quota_key(first) < 2**63


def test_internal_receipt_results_do_not_print_identifiers_or_metadata():
    service = Probe()
    assert repr(service.plan) == "ReceiptPlan(<private>)"
    assert repr(Received({"filename": "private marker"}, True)) == "Received(<private>)"
