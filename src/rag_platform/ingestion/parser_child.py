"""Private stdio child. No document is parsed before sealing the process."""

import io
import json
import logging
import os
import sys

from rag_platform.ingestion import parsers
from rag_platform.ingestion.extraction import (
    ERRORS,
    MAX_OUTPUT,
    PARSERS,
    ExtractionError,
    from_wire,
)
from rag_platform.ingestion.parser_sandbox import seal

FAILURES = {code: json.dumps({"error": code}).encode() for code in ERRORS}


def main():
    logging.disable(logging.CRITICAL)
    error, result = "PARSER_INVALID", None
    try:
        if len(sys.argv) != 3 or sys.argv[1] not in PARSERS:
            raise ExtractionError("INPUT_INVALID")
        cpu = int(sys.argv[2])
        parsers.preload()
        # FileIO wraps an existing descriptor, opening no filesystem path.
        stream = io.BufferedReader(io.FileIO(0, mode="rb", closefd=False), 65536)
        size = os.fstat(0).st_size
        seal(cpu_seconds=cpu)
        result = parsers.extract(stream, sys.argv[1], size)
        from_wire(result, sys.argv[1])
        data = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode()
        if len(data) > MAX_OUTPUT:
            raise ExtractionError("PARSER_LIMIT")
    except MemoryError:
        error, result = "PARSER_LIMIT", None
    except ExtractionError as failure:
        error, result = failure.code, None
    except BaseException:
        error, result = "PARSER_INVALID", None
    if result is None:
        data = FAILURES[error]
    view = memoryview(data)
    while view:
        written = os.write(1, view[:65536])
        view = view[written:]
    os._exit(0 if result is not None else 1)


if __name__ == "__main__":
    main()
