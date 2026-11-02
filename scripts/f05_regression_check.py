"""Reuse F01..F04 probes under the explicit F05 authority, never by relaxed heads."""

import logging

import f04_regression_check as regression

if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    try:
        regression.main(profile="embeddings")
        print("PASS F05 COMPAT: F01..F04 HTTP/SQL/S3 probes passed under exact F05 profile.")
    except Exception as error:
        print(
            "F05-COMPAT " + regression.PHASE + " " + type(error).__name__ + "; resources retained."
        )
        raise SystemExit(1) from None
