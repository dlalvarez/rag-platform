"""Offline real-OS acceptance; no data service/network or credentials are required."""

import hashlib
import json
import logging
import os
import resource
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

from f04_corpus import corpus, pdf

from rag_platform.ingestion.extraction import ChunkConfig, ExtractionError, chunks
from rag_platform.ingestion.extractor import _collect, extract

ROOT = Path(__file__).resolve().parents[1]
PHASE = "START"


def parse(body, mime):
    with tempfile.TemporaryFile(mode="w+b") as stream:
        stream.write(body)
        stream.flush()
        return extract(
            stream, mime, expected_size=len(body), expected_hash=hashlib.sha256(body).hexdigest()
        )


def sandbox(mode):
    with tempfile.TemporaryFile(mode="w+b") as stream:
        stream.write(b"synthetic sandbox fixture")
        stream.flush()
        fd = os.open("/proc/self/fd/" + str(stream.fileno()), os.O_RDONLY | os.O_CLOEXEC)
        process = None
        try:
            env = {"PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"}
            process = subprocess.Popen(
                [sys.executable, str(ROOT / "scripts/f04_sandbox_check.py"), mode],
                stdin=fd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=env,
                close_fds=True,
            )
            try:
                data = _collect(process, 15)
            except ExtractionError as error:
                if mode != "output" or error.code != "PARSER_LIMIT":
                    raise
                data = None
            if mode == "restrictions":
                flags = json.loads(data)
                assert len(flags) == 8 and all(type(v) is bool and v for v in flags.values())
            elif mode == "cpu":
                assert process.returncode in (-signal.SIGXCPU, -signal.SIGKILL)
            else:
                assert data is None
        finally:
            if process is not None:
                if process.poll() is None:
                    process.kill()
                process.wait()
                process.stdout.close()
            os.close(fd)


def run():
    global PHASE
    PHASE = "FORMATS"
    values = corpus()
    assert values == corpus()
    manifest = json.loads((ROOT / "ops/f04/corpus-manifest.json").read_text())
    expected = {row["id"]: row for row in manifest["files"]}
    assert len(expected) == 4
    for kind, (mime, body) in values.items():
        recorded = expected["f04-parser-" + kind + "-v1"]
        assert recorded["mime"] == mime and recorded["byte_size"] == len(body)
        assert recorded["sha256"] == hashlib.sha256(body).hexdigest()
    for mime, body in values.values():
        first, second = parse(body, mime), parse(body, mime)
        assert first == second
        emitted = chunks(first)
        assert emitted == chunks(second)
        for piece in emitted:
            assert piece.text == first.text[piece.start : piece.end]
            assert piece.page == first.blocks[piece.block_ordinal].page
            assert piece.content_hash == hashlib.sha256(piece.text.encode()).hexdigest()
        assert ChunkConfig().fingerprint(mime) == ChunkConfig().fingerprint(mime)
    print(
        "PASS T004: PDF/DOCX/MD/TXT semánticos; repetición, páginas/offsets/hash y chunks estables."
    )
    PHASE = "OCR"
    for body in (pdf(("scan",), scanned=True), pdf(("text", "scan"), scanned=(1,))):
        try:
            parse(body, "application/pdf")
        except ExtractionError as error:
            assert error.code == "NEEDS_OCR"
        else:
            raise RuntimeError("OCR_NOT_DETECTED")
    blank = parse(pdf(("text", "")), "application/pdf")
    assert blank.blocks[1].kind == "blank_page" and blank.blocks[1].page == 2
    print("PASS T004: escaneado/mixto NEEDS_OCR sin parcial; página vacía conserva procedencia.")
    PHASE = "SANDBOX"
    for mode in ("restrictions", "cpu", "output"):
        sandbox(mode)
    print("PASS T004: sin open/red/fork/exec; FD original RO, memoria/CPU/salida limitados.")
    PHASE = "FINAL"
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    assert usage.ru_maxrss < 512 * 1024
    try:
        os.waitpid(-1, os.WNOHANG)
    except ChildProcessError:
        pass
    else:
        raise RuntimeError("CHILD_NOT_REAPED")
    for fd in Path("/proc/self/fd").iterdir():
        try:
            target = os.readlink(fd)
        except OSError:
            continue
        if target.startswith("/tmp/") and "(deleted)" in target:
            raise RuntimeError("TEMPORARY_NOT_CLOSED")
    print("T004: measured child peak RSS KiB=" + str(usage.ru_maxrss))
    print("PASS T004: sin credenciales/red/SQL/S3; temporales y procesos propios cerrados.")
    print("T004: componente probado; sin worker ni publicación o aceptación E2E de F04.")


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    try:
        run()
    except ExtractionError as error:
        print("F04-T004 " + PHASE + " " + error.code + "; sin detalles sensibles.")
        raise SystemExit(1) from None
    except Exception:
        print("F04-T004 " + PHASE + " FAILED; sin detalles sensibles.")
        raise SystemExit(1) from None
