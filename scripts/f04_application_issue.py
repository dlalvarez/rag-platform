"""Trusted operator issues only the existing fixed AppRole, never a daily token."""

import argparse
import json
import logging
from pathlib import Path

from f01_daily import session
from f03_application_issue import ensure


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["ensure", "replace"])
    args = parser.parse_args()
    with session() as (day, _, _):
        return ensure(day, Path("/run/f04-worker"), replace=args.action == "replace")


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    try:
        print(json.dumps(main(), sort_keys=True))
    except (Exception, KeyboardInterrupt):
        raise SystemExit("F04 WORKER ISSUE: REFUSED; sin detalles sensibles.") from None
