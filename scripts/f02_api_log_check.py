"""Host-only closed-result inspection; container logs never leave ragdev01."""

import json
import re
import subprocess
from pathlib import Path

DATA = Path("/srv/rag-data/rag-platform/f02")


def run(*, extra_forbidden=(), extra_patterns=()):
    values = json.loads((DATA / "secrets/identity-fixture-v2.json").read_text())
    forbidden = (
        list(extra_forbidden)
        + [values["client_secret"]]
        + [item[field] for item in values["users"].values() for field in ("password", "id")]
    )
    forbidden += [
        (DATA / "secrets/identity_app_password").read_text(),
        (DATA / "secrets/identity_admin_password").read_text(),
    ]
    result = subprocess.run(
        ["docker", "logs", "rag-f02-dev-api-1"], capture_output=True, text=True, check=True
    )
    body = result.stdout + result.stderr
    if any(secret in body for secret in forbidden):
        raise ValueError("LEAK")
    if any(re.search(pattern, body) for pattern in extra_patterns):
        raise ValueError("LEAK")
    if re.search(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", body):
        raise ValueError("LEAK")
    if any(value in body for value in ("Authorization", "alice@", "bob@", "Traceback")):
        raise ValueError("LEAK")
    print("PASS T005 LOGS: captured API output has no JWT, credentials or IdP subjects.")


if __name__ == "__main__":
    try:
        run()
    except Exception:
        raise SystemExit("F02-T005 LOG_CHECK: stopped; no log body displayed.") from None
