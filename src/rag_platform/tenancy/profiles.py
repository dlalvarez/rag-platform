"""Explicit known tenant schema profiles. Unknown/future heads are always rejected."""

IDENTITY_VERSION = "f01_tenant_0001"
DOCUMENTS_VERSION = "f03_tenant_0002"
INGESTION_VERSION = "f04_tenant_0003"
PROFILES = {
    "identity": IDENTITY_VERSION,
    "documents": DOCUMENTS_VERSION,
    "ingestion": INGESTION_VERSION,
}


def version_for(profile):
    if not isinstance(profile, str) or profile not in PROFILES:
        raise ValueError("Unknown tenant schema profile")
    return PROFILES[profile]


def migration_sources(profile):
    expected = version_for(profile)
    if profile == "ingestion":
        return frozenset((DOCUMENTS_VERSION, INGESTION_VERSION))
    return frozenset((IDENTITY_VERSION, expected))
