"""Bounded assistant configuration. These values never establish authorization."""

import re
import unicodedata
from dataclasses import dataclass
from uuid import UUID

from rag_platform.providers.generation import text

READ_ROLES = frozenset(("owner", "admin", "editor", "reader"))
WRITE_ROLES = frozenset(("owner", "admin", "editor"))


class AssistantError(RuntimeError):
    CODES = frozenset(
        (
            "INPUT_INVALID",
            "NOT_FOUND",
            "ROLE_DENIED",
            "STATE_CONFLICT",
            "PROFILE_MISMATCH",
            "DEPENDENCY_UNAVAILABLE",
        )
    )

    def __init__(self, code="DEPENDENCY_UNAVAILABLE"):
        self.code = (
            code if isinstance(code, str) and code in self.CODES else "DEPENDENCY_UNAVAILABLE"
        )
        super().__init__(self.code)


def uuid(value):
    if not isinstance(value, UUID) or value.int == 0:
        raise AssistantError("INPUT_INVALID")
    return value


@dataclass(frozen=True, slots=True, repr=False)
class AssistantConfiguration:
    name: str
    purpose: str
    repository_ids: tuple[UUID, ...]
    space_id: UUID
    generation_fingerprint: str
    top_k: int = 8

    def __post_init__(self):
        if (
            not text(self.name, 120)
            or self.name != self.name.strip()
            or unicodedata.normalize("NFC", self.name) != self.name
            or any(unicodedata.category(c).startswith("C") for c in self.name)
            or not text(self.purpose, 2000, empty=True)
            or type(self.repository_ids) is not tuple
            or not 1 <= len(self.repository_ids) <= 16
            or not isinstance(self.generation_fingerprint, str)
            or re.fullmatch("[0-9a-f]{64}", self.generation_fingerprint) is None
            or type(self.top_k) is not int
            or not 1 <= self.top_k <= 8
        ):
            raise AssistantError("INPUT_INVALID")
        uuid(self.space_id)
        for value in self.repository_ids:
            uuid(value)
        if len(set(self.repository_ids)) != len(self.repository_ids):
            raise AssistantError("INPUT_INVALID")
        # Repository ordering has no policy meaning and must not alter identity/CAS.
        object.__setattr__(self, "repository_ids", tuple(sorted(self.repository_ids)))

    def __repr__(self):
        return "AssistantConfiguration(<private configuration>)"


def owner_allows(role, actor, owner, action):
    """Additional tenant-local rule AFTER fresh TenantAuthorizer validation.

    No platform or tenant administrator inherits access to another owner's content.
    A successful result still requires active assistant and all current repository ACLs.
    """
    return (
        isinstance(role, str)
        and isinstance(actor, UUID)
        and actor.int != 0
        and isinstance(owner, UUID)
        and actor == owner
        and isinstance(action, str)
        and (
            (action in ("read", "use") and role in READ_ROLES)
            or (action in ("create", "update", "delete") and role in WRITE_ROLES)
        )
    )


def expected_revision(value):
    if type(value) is not int or not 1 <= value <= 2**63 - 1:
        raise AssistantError("INPUT_INVALID")
    return value
