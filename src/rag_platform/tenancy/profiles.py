"""Explicit known tenant schema profiles. Unknown/future heads are always rejected."""

IDENTITY_VERSION = "f01_tenant_0001"
DOCUMENTS_VERSION = "f03_tenant_0002"
PROFILES = {"identity": IDENTITY_VERSION, "documents": DOCUMENTS_VERSION}


def version_for(profile):
    if not isinstance(profile, str) or profile not in PROFILES:
        raise ValueError("Unknown tenant schema profile")
    return PROFILES[profile]
