"""Actual isolated parser and provenance tests; no external service or credential."""

import hashlib
import importlib.util
import io
import json
import os
import signal
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import docx
import pytest

from rag_platform.ingestion.extraction import (
    ChunkConfig,
    ExtractionError,
    chunks,
    from_wire,
)
from rag_platform.ingestion.extractor import _collect, extract

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("f04_corpus", ROOT / "scripts/f04_corpus.py")
corpus = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(corpus)


def parsed(body, mime="text/plain", **limits):
    with tempfile.TemporaryFile(mode="w+b") as stream:
        stream.write(body)
        stream.flush()
        return extract(
            stream,
            mime,
            expected_size=len(body),
            expected_hash=hashlib.sha256(body).hexdigest(),
            **limits,
        )


@pytest.mark.parametrize("kind", ["pdf", "docx", "md", "txt"])
def test_four_formats_deterministic_provenance(kind):
    mime, body = corpus.corpus()[kind]
    first, second = parsed(body, mime), parsed(body, mime)
    assert first == second and chunks(first) == chunks(second)
    assert first.text and "á" in first.text or "Á" in first.text
    assert first.page_count == (2 if kind == "pdf" else None)
    for block in first.blocks:
        assert first.text[block.start : block.end] == block.text
    for chunk in chunks(first):
        assert first.text[chunk.start : chunk.end] == chunk.text
        assert chunk.content_hash == hashlib.sha256(chunk.text.encode()).hexdigest()
        assert chunk.page == first.blocks[chunk.block_ordinal].page
    assert "<private>" in repr(first) and "<private>" in repr(first.blocks[0])


def test_corpus_stable_bytes_no_zip_timestamps():
    assert corpus.corpus() == corpus.corpus()


def test_pdf_actual_pages_and_text_no_invented_mapping():
    value = parsed(corpus.pdf(), "application/pdf")
    assert [b.page for b in value.blocks] == [1, 2]
    assert "Página uno" in value.blocks[0].text and "Página dos" in value.blocks[1].text


@pytest.mark.parametrize(
    "body",
    [
        corpus.pdf(("ignored",), scanned=True),
        corpus.pdf(("text", "scan"), scanned=(1,)),
    ],
)
def test_scanned_or_mixed_pdf_is_needs_ocr_without_partial(body):
    with pytest.raises(ExtractionError, match="NEEDS_OCR"):
        parsed(body, "application/pdf")


def test_encrypted_and_malformed_pdf_closed():
    with pytest.raises(ExtractionError, match="PARSER_ENCRYPTED"):
        parsed(corpus.pdf(encrypted=True), "application/pdf")
    with pytest.raises(ExtractionError, match="PARSER_INVALID"):
        parsed(b"%PDF-1.4\nnot-semantic\n%%EOF", "application/pdf")


def test_pdf_page_budget():
    with pytest.raises(ExtractionError, match="PARSER_LIMIT"):
        parsed(corpus.pdf(("valid text",) * 201), "application/pdf")


def test_docx_headings_table_order_no_fake_pages():
    value = parsed(corpus.word(), corpus.corpus()["docx"][0])
    assert [b.kind for b in value.blocks] == [
        "heading",
        "paragraph",
        "table",
        "table",
        "heading",
        "paragraph",
    ]
    assert value.blocks[2].text == "Clave\tValor"
    assert value.blocks[3].text == "réplica\tsí"
    assert value.blocks[-1].section == ("Operación RAG", "Recuperación")
    assert all(b.page is None for b in value.blocks)


def test_docx_unhandled_text_is_rejected_not_silently_omitted():
    document = docx.Document(io.BytesIO(corpus.word()))
    document.sections[0].header.paragraphs[0].text = "synthetic hidden header content"
    output = io.BytesIO()
    document.save(output)
    with pytest.raises(ExtractionError, match="PARSER_UNSUPPORTED"):
        parsed(output.getvalue(), corpus.corpus()["docx"][0])


def test_docx_zip_bomb_before_xml():
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", b"x" * 2_000_000)
        archive.writestr("word/document.xml", b"x")
    with pytest.raises(ExtractionError, match="PARSER_(INVALID|LIMIT)"):
        parsed(output.getvalue(), corpus.corpus()["docx"][0])


def test_markdown_code_headings_and_punctuation_preserved():
    value = parsed(corpus.corpus()["md"][1], "text/markdown")
    code = next(b for b in value.blocks if b.kind == "code")
    assert "SELECT * FROM tabla WHERE clave = 'á';" in code.text
    assert code.section == ("Operación",)
    assert value.blocks[-1].section == ("Operación", "Réplicas")


def test_normalization_and_offsets_unicode_not_bytes():
    value = parsed("Cafe\u0301\r\n  SELECT x;\r\n".encode())
    assert value.text == "Café\n  SELECT x;\n"
    assert value.blocks[0].end == len(value.text) != len(value.text.encode())


@pytest.mark.parametrize("body", [b"\xff", b"hello\x00private", b"  \n  "])
def test_invalid_or_empty_text_closed(body):
    with pytest.raises(ExtractionError, match="PARSER_INVALID|NO_TEXT"):
        parsed(body)


def test_character_budget_and_no_partial():
    with pytest.raises(ExtractionError, match="PARSER_LIMIT"):
        parsed(b"x" * 2_000_001)


@pytest.mark.parametrize("size,overlap", [(128, 0), (128, 64), (1024, 128), (8192, 4000)])
def test_chunk_coverage_size_overlap_and_exact_slices(size, overlap):
    value = parsed(("line with SQL a->b != c;\n" * 700).encode())
    config = ChunkConfig(size, overlap)
    result = chunks(value, config)
    covered = set()
    prior = None
    for item in result:
        assert 0 < len(item.text) <= size
        assert item.text == value.text[item.start : item.end]
        if prior is not None:
            assert prior.end - item.start == overlap
            assert item.end > prior.end
        covered.update(range(item.start, item.end))
        prior = item
    assert covered == set(range(len(value.text)))


def test_chunk_config_identity_changes_only_when_relevant():
    a = ChunkConfig()
    assert a.fingerprint("text/plain") == ChunkConfig().fingerprint("text/plain")
    assert a.fingerprint("text/plain") != ChunkConfig(2048).fingerprint("text/plain")
    assert a.fingerprint("text/plain") != a.fingerprint("text/markdown")
    for values in ((127, 0), (128, 65), (True, 0), (8193, 1)):
        with pytest.raises(ExtractionError):
            ChunkConfig(*values)


def test_private_input_hash_and_size_checked_before_child():
    with tempfile.TemporaryFile(mode="w+b") as stream:
        stream.write(b"private fixture")
        stream.flush()
        with pytest.raises(ExtractionError, match="INPUT_INVALID"):
            extract(stream, "text/plain", expected_size=15, expected_hash="0" * 64)


def test_wall_timeout_closes_child_and_releases_slot():
    with pytest.raises(ExtractionError, match="PARSER_LIMIT"):
        parsed(b"fixture text", wall_seconds=0.001)
    assert parsed(b"successful next job").text == "successful next job"


def probe(mode):
    with tempfile.TemporaryFile(mode="w+b") as stream:
        stream.write(b"fixture")
        stream.flush()
        fd = os.open("/proc/self/fd/" + str(stream.fileno()), os.O_RDONLY)
        process = None
        try:
            env = {"PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"}
            process = subprocess.Popen(
                [sys.executable, str(ROOT / "scripts/f04_sandbox_check.py"), mode],
                stdin=fd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                env=env,
            )
            try:
                output = _collect(process, 5)
            except ExtractionError:
                assert mode == "output"
                output = None
            if mode == "restrictions":
                flags = json.loads(output)
                assert len(flags) == 8 and all(flags.values())
            elif mode == "cpu":
                assert process.returncode in (-signal.SIGXCPU, -signal.SIGKILL)
            else:
                assert output is None
        finally:
            if process is not None:
                if process.poll() is None:
                    process.kill()
                process.wait()
                process.stdout.close()
            os.close(fd)


@pytest.mark.parametrize("mode", ["restrictions", "cpu", "output"])
def test_real_kernel_sandbox_limits(mode):
    probe(mode)


def test_blank_pdf_page_retains_mapping_without_false_ocr():
    value = parsed(corpus.pdf(("text", "")), "application/pdf")
    assert value.page_count == 2 and value.blocks[1].kind == "blank_page"
    assert value.blocks[1].page == 2 and value.blocks[1].text == ""
    assert all(chunk.page == 1 for chunk in chunks(value))


def test_pdf_punctuation_is_not_discarded_as_useless_text():
    value = parsed(corpus.pdf(("-- += / *",)), "application/pdf")
    assert "-- += / *" in value.text


def test_docx_external_entity_fails_closed():
    body = corpus.word()
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(body)) as source, zipfile.ZipFile(output, "w") as target:
        for name in source.namelist():
            data = source.read(name)
            if name == "word/document.xml":
                close = data.find(b"?>")
                declaration = b'<!DOCTYPE w:document [<!ENTITY ext SYSTEM "file:///etc/passwd">]>'
                data = data[: close + 2] + declaration + data[close + 2 :]
            target.writestr(name, data)
    with pytest.raises(ExtractionError, match="PARSER_UNSUPPORTED"):
        parsed(output.getvalue(), corpus.corpus()["docx"][0])


def test_untrusted_wire_types_fail_closed():
    for mime in ([], {}, None):
        with pytest.raises(ExtractionError):
            from_wire({}, mime)
    with pytest.raises(ExtractionError):
        parsed(bytes((0xED, 0xA0, 0x80)))


def test_chunk_budget_returns_no_partial_tuple():
    value = parsed(b"x" * 1_000_000)
    with pytest.raises(ExtractionError, match="PARSER_LIMIT"):
        chunks(value, ChunkConfig(128, 64))
