"""Bounded local adapters. Called only after OS isolation in parser_child."""

import codecs
import re
import zipfile

import docx
import pypdf
from docx.table import Table
from docx.text.paragraph import Paragraph
from lxml import etree

from rag_platform.documents.errors import DocumentError
from rag_platform.documents.validation import MAX_BYTES, check_docx
from rag_platform.ingestion.extraction import (
    MAX_BLOCKS,
    MAX_CHARACTERS,
    MAX_PAGES,
    NORMALIZER,
    PARSERS,
    ExtractionError,
    normalize,
)

WORD = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
HEADING = re.compile(r"^Heading([1-9])$")
MD_HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
FENCE = re.compile(r"^ {0,3}([" + chr(96) + r"~]{3,})(.*)$")
UNSUPPORTED = {
    "ins",
    "del",
    "moveFrom",
    "moveTo",
    "txbxContent",
    "sdt",
    "altChunk",
    "customXml",
    "fldSimple",
    "vanish",
    "object",
}


def preload():
    if pypdf.__version__ != "6.21.4" or docx.__version__ != "1.2.0":
        raise ExtractionError("PARSER_UNSUPPORTED")
    for encoding in (
        "utf-8",
        "utf-8-sig",
        "utf-16",
        "utf-16-be",
        "utf-16-le",
        "utf-32-be",
        "utf-32-le",
        "cp1252",
        "cp437",
        "mac-roman",
        "latin-1",
        "ascii",
    ):
        codecs.lookup(encoding)


class Collector:
    def __init__(self):
        self.blocks, self.characters = [], 0

    def add(self, text, *, page=None, section=(), kind="text"):
        text = normalize(text)
        if not text.strip() and kind != "blank_page":
            return
        self.characters += len(text) + (1 if self.blocks else 0)
        if self.characters > MAX_CHARACTERS or len(self.blocks) >= MAX_BLOCKS:
            raise ExtractionError("PARSER_LIMIT")
        self.blocks.append({"text": text, "page": page, "section": list(section), "kind": kind})


def _text(stream):
    decoder = codecs.getincrementaldecoder("utf-8-sig")("strict")
    parts, count, raw = [], 0, 0
    while piece := stream.read(65536):
        raw += len(piece)
        if raw > MAX_BYTES:
            raise ExtractionError("PARSER_LIMIT")
        text = decoder.decode(piece)
        count += len(text)
        if count > MAX_CHARACTERS:
            raise ExtractionError("PARSER_LIMIT")
        parts.append(text)
    parts.append(decoder.decode(b"", final=True))
    return normalize("".join(parts))


def _markdown(text, result):
    headings, pending, active = [], [], None
    section = ()

    def flush(kind):
        nonlocal pending
        if pending:
            result.add("".join(pending), section=section, kind=kind)
            pending = []

    for line in text.splitlines(keepends=True):
        fence = FENCE.match(line.rstrip("\n"))
        if active is not None:
            pending.append(line)
            if fence and set(fence[1]) == {active[0]} and len(fence[1]) >= active[1]:
                if not fence[2].strip():
                    flush("code")
                    active = None
            continue
        if fence and len(set(fence[1])) == 1:
            flush("markdown")
            active = (fence[1][0], len(fence[1]))
            pending.append(line)
            continue
        heading = MD_HEADING.match(line.rstrip("\n"))
        if heading:
            flush("markdown")
            level, title = len(heading[1]), normalize(heading[2])
            headings = [(n, t) for n, t in headings if n < level]
            headings.append((level, title))
            section = tuple(t for _, t in headings)
            result.add(line, section=section, kind="heading")
        else:
            pending.append(line)
    flush("code" if active is not None else "markdown")


def _blank_page(page):
    content = page.get_contents()
    if content is None:
        return True
    positioning = {
        b"q",
        b"Q",
        b"cm",
        b"BT",
        b"ET",
        b"Tf",
        b"Td",
        b"TD",
        b"Tm",
        b"T*",
        b"TL",
        b"Ts",
        b"Tr",
        b"Tz",
        b"Tc",
        b"Tw",
    }

    def empty(value):
        if isinstance(value, (str, bytes)):
            return not value.strip()
        if isinstance(value, (list, tuple)):
            return all(empty(x) for x in value)
        return isinstance(value, (int, float))

    for operands, operator in content.operations:
        if operator in positioning:
            continue
        if operator in {b"Tj", b"TJ", b"'", b'"'} and all(empty(x) for x in operands):
            continue
        return False
    return True


def _pdf(stream, result):
    reader = pypdf.PdfReader(stream, strict=True)
    if reader.is_encrypted:
        raise ExtractionError("PARSER_ENCRYPTED")
    count = len(reader.pages)
    if not 1 <= count <= MAX_PAGES:
        raise ExtractionError("PARSER_LIMIT")
    for index, page in enumerate(reader.pages):
        text = normalize(page.extract_text(extraction_mode="layout"))
        if not text.strip():
            if not _blank_page(page):
                raise ExtractionError("NEEDS_OCR")
            result.add("", page=index + 1, kind="blank_page")
        else:
            result.add(text, page=index + 1, kind="page")
    if not any(block["text"].strip() for block in result.blocks):
        raise ExtractionError("NEEDS_OCR")
    return count


def _docx_features(stream, size):
    try:
        check_docx(stream, size)
    except DocumentError as error:
        raise ExtractionError(
            "PARSER_LIMIT" if error.code == "TOO_LARGE" else "PARSER_INVALID"
        ) from None
    stream.seek(0)
    parser = etree.XMLParser(
        resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False
    )
    with zipfile.ZipFile(stream) as archive:
        for name in archive.namelist():
            if not name.startswith("word/") or not name.endswith(".xml"):
                continue
            root = etree.fromstring(archive.read(name), parser)
            if root.getroottree().docinfo.doctype:
                raise ExtractionError("PARSER_UNSUPPORTED")
            for node in root.iter():
                if not isinstance(node.tag, str) or not node.tag.startswith("{" + WORD + "}"):
                    continue
                if etree.QName(node).localname in UNSUPPORTED:
                    raise ExtractionError("PARSER_UNSUPPORTED")
            if re.fullmatch(r"word/(header\d*|footer\d*|footnotes|endnotes)\.xml", name):
                if any((node.text or "").strip() for node in root.iter("{" + WORD + "}t")):
                    raise ExtractionError("PARSER_UNSUPPORTED")
    stream.seek(0)


def _docx(stream, size, result):
    _docx_features(stream, size)
    document = docx.Document(stream)
    headings, cells = [], 0

    def cell_text(cell, depth):
        nonlocal cells
        cells += 1
        if cells > 10000 or depth > 8:
            raise ExtractionError("PARSER_LIMIT")
        values = []
        for item in cell.iter_inner_content():
            if isinstance(item, Paragraph):
                values.append(item.text)
            else:
                values.extend(table_rows(item, depth + 1))
        return "\n".join(values)

    def table_rows(table, depth=0):
        seen, rows = set(), []
        for row in table.rows:
            values = []
            for cell in row.cells:
                if cell._tc in seen:
                    values.append("")
                else:
                    seen.add(cell._tc)
                    values.append(cell_text(cell, depth))
            rows.append("\t".join(values))
        return rows

    for item in document.iter_inner_content():
        if isinstance(item, Paragraph):
            style = item.style
            heading = HEADING.fullmatch(style.style_id) if style is not None else None
            if heading:
                level = int(heading[1])
                title = normalize(item.text)
                headings = [(n, t) for n, t in headings if n < level]
                headings.append((level, title))
            result.add(
                item.text,
                section=tuple(t for _, t in headings),
                kind="heading" if heading else "paragraph",
            )
        elif isinstance(item, Table):
            for row in table_rows(item):
                result.add(row, section=tuple(t for _, t in headings), kind="table")


def extract(stream, mime, size):
    if mime not in PARSERS or not 1 <= size <= MAX_BYTES:
        raise ExtractionError("INPUT_INVALID")
    result, pages = Collector(), None
    if mime == "application/pdf":
        pages = _pdf(stream, result)
    elif mime.startswith("text/"):
        text = _text(stream)
        if mime == "text/markdown":
            _markdown(text, result)
        else:
            result.add(text)
    else:
        _docx(stream, size, result)
    if not result.blocks:
        raise ExtractionError("NO_TEXT")
    return {
        "version": 1,
        "parser": PARSERS[mime],
        "normalizer": NORMALIZER,
        "page_count": pages,
        "blocks": result.blocks,
    }
