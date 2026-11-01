"""A startup failure is evidence only when it identifies the expected rejection."""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from f02_isolation_check import expected_cross_rejection  # noqa: E402


class StartupError(Exception):
    def __init__(self, body, state):
        super().__init__(body)
        self.sqlstate = state


@pytest.mark.parametrize(
    "different,state,message,accepted",
    [
        (False, None, 'FATAL: permission denied for database "other"', True),
        (False, "42501", 'FATAL: permission denied for database "other"', True),
        (False, None, 'FATAL: permission denied for database "unrelated"', False),
        (False, None, "connection timed out", False),
        (True, None, 'FATAL: password authentication failed for user "fixture_app"', True),
        (True, "28P01", 'FATAL: password authentication failed for user "fixture_app"', True),
        (True, None, 'FATAL: password authentication failed for user "someone_else"', False),
        (True, "08006", 'FATAL: password authentication failed for user "fixture_app"', False),
        (True, None, "SSL error: certificate verify failed", False),
    ],
)
def test_only_exact_startup_denial_counts(different, state, message, accepted):
    source = SimpleNamespace(host="one", port=5432)
    target = SimpleNamespace(host="two" if different else "one", port=5432, database="other")
    assert (
        expected_cross_rejection(StartupError(message, state), source, target, "fixture_app")
        is accepted
    )
