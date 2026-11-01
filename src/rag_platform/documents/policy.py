"""Repository capabilities intersect with active tenant membership; deny by default."""

import re
import unicodedata

from rag_platform.documents.errors import DocumentError

ROLES = {"owner", "admin", "editor", "reader"}
READ = {"owner", "admin", "editor", "reader"}
WRITE = {"owner", "admin", "editor"}
MANAGE = {"owner", "admin"}


def tenant_allows(role, action):
    allowed = {
        "read": READ,
        "upload": WRITE,
        "create": MANAGE,
        "update": MANAGE,
        "delete": MANAGE,
        "acl": MANAGE,
    }
    return isinstance(role, str) and isinstance(action, str) and role in allowed.get(action, set())


def repository_allows(role, action):
    allowed = {"read": READ, "upload": WRITE, "update": MANAGE, "delete": MANAGE, "acl": MANAGE}
    return isinstance(role, str) and isinstance(action, str) and role in allowed.get(action, set())


def may_assign(actor_role, prior_role, target_role):
    if not isinstance(actor_role, str) or actor_role not in ROLES:
        return False
    if prior_role is not None and (not isinstance(prior_role, str) or prior_role not in ROLES):
        return False
    if target_role is not None and (not isinstance(target_role, str) or target_role not in ROLES):
        return False
    if actor_role == "owner":
        return True
    return actor_role == "admin" and prior_role not in MANAGE and target_role not in MANAGE


def target_allows(membership_role, repository_role):
    if not isinstance(membership_role, str) or not isinstance(repository_role, str):
        return False
    if membership_role in MANAGE:
        return repository_role in ROLES
    if membership_role == "editor":
        return repository_role in {"editor", "reader"}
    return membership_role == "reader" and repository_role == "reader"


def name_and_config(name, config):
    if (
        not isinstance(name, str)
        or not 1 <= len(name) <= 120
        or name != name.strip()
        or unicodedata.normalize("NFC", name) != name
        or any(unicodedata.category(char).startswith("C") for char in name)
    ):
        raise DocumentError("INPUT_INVALID")
    if config is None:
        config = {"language": "auto"}
    if not isinstance(config, dict) or set(config) != {"language"}:
        raise DocumentError("INPUT_INVALID")
    language = config["language"]
    if (
        not isinstance(language, str)
        or not 1 <= len(language) <= 35
        or re.fullmatch(r"(auto|[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*)", language) is None
    ):
        raise DocumentError("INPUT_INVALID")
    return name, {"language": language.lower()}
