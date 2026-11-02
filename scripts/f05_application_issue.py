"""Existing AppRole only; issue after the embedding consumer has released its lock."""

import argparse
import json
import logging
import os
from pathlib import Path

from f01_daily import session
from f03_application_issue import ensure

from rag_platform.providers.application_handoff import lock_file

DELIVERY = Path("/run/f05-worker")


def issue(*, replace=False):
    consumer = lock_file(DELIVERY / "consumer.lock")
    try:
        with session() as (day, _, _):
            return ensure(day, DELIVERY, replace=replace)
    finally:
        os.close(consumer)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("ensure", "replace"))
    args = parser.parse_args()
    return issue(replace=args.action == "replace")


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    try:
        print(json.dumps(main(), sort_keys=True))
    except (Exception, KeyboardInterrupt):
        raise SystemExit("F05 HANDOFF: REFUSED; no sensitive details.") from None
