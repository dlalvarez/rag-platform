"""Private parser/chunker contracts. Offsets index Unicode normalized text."""

import hashlib
import json
import unicodedata
from dataclasses import dataclass

MAX_CHARACTERS = 2_000_000
MAX_BLOCKS = MAX_CHUNKS = 10_000
MAX_PAGES = 200
MAX_OUTPUT = 16 * 1024 * 1024
NORMALIZER = "nfc-lf-v1"
CHUNKER = "block-characters-v1"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PARSERS = {
    "application/pdf": "pypdf-6.21.4-layout-v1",
    DOCX_MIME: "python-docx-1.2.0-blocks-v1",
    "text/plain": "utf8-v1",
    "text/markdown": "markdown-blocks-v1",
}
ERRORS = frozenset(
    {
        "INPUT_INVALID",
        "PARSER_INVALID",
        "PARSER_LIMIT",
        "PARSER_ENCRYPTED",
        "PARSER_UNSUPPORTED",
        "NEEDS_OCR",
        "NO_TEXT",
        "SANDBOX_UNAVAILABLE",
    }
)


class ExtractionError(RuntimeError):
    def __init__(self, code="PARSER_INVALID"):
        self.code = code if isinstance(code, str) and code in ERRORS else "PARSER_INVALID"
        super().__init__(self.code)


def normalize(text):
    if not isinstance(text, str):
        raise ExtractionError()
    value = unicodedata.normalize(
        "NFC", text.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n")
    )
    if any(
        (ord(c) < 32 and c not in "\n\t") or 127 <= ord(c) <= 159 or 0xD800 <= ord(c) <= 0xDFFF
        for c in value
    ):
        raise ExtractionError()
    return value


@dataclass(frozen=True, slots=True, repr=False)
class Block:
    ordinal: int
    start: int
    end: int
    text: str
    page: int | None
    section: tuple[str, ...]
    kind: str

    def __repr__(self):
        return "Block(<private>)"


@dataclass(frozen=True, slots=True, repr=False)
class Extraction:
    parser: str
    text: str
    blocks: tuple[Block, ...]
    page_count: int | None

    def __repr__(self):
        return "Extraction(<private>)"


def from_wire(data, mime):
    if (
        not isinstance(mime, str)
        or mime not in PARSERS
        or not isinstance(data, dict)
        or set(data) != {"version", "parser", "normalizer", "page_count", "blocks"}
        or type(data["version"]) is not int
        or data["version"] != 1
        or data["parser"] != PARSERS[mime]
        or data["normalizer"] != NORMALIZER
        or not isinstance(data["blocks"], list)
        or not 1 <= len(data["blocks"]) <= MAX_BLOCKS
    ):
        raise ExtractionError()
    pages = data["page_count"]
    pdf = mime == "application/pdf"
    if (pdf and (type(pages) is not int or not 1 <= pages <= MAX_PAGES)) or (
        not pdf and pages is not None
    ):
        raise ExtractionError()
    if pdf and len(data["blocks"]) != pages:
        raise ExtractionError()
    blocks, total = [], 0
    for i, raw in enumerate(data["blocks"]):
        if not isinstance(raw, dict) or set(raw) != {"text", "page", "section", "kind"}:
            raise ExtractionError()
        text, page, section, kind = (raw[k] for k in ("text", "page", "section", "kind"))
        if (
            not isinstance(text, str)
            or (not text.strip() and not (pdf and kind == "blank_page" and text == ""))
            or text != normalize(text)
            or not isinstance(section, list)
            or len(section) > 9
            or any(
                not isinstance(s, str) or not 1 <= len(s) <= 512 or s != normalize(s)
                for s in section
            )
            or sum(len(s) for s in section) > 2048
            or not isinstance(kind, str)
            or kind
            not in {
                "page",
                "blank_page",
                "paragraph",
                "heading",
                "table",
                "text",
                "markdown",
                "code",
            }
            or (
                pdf
                and (type(page) is not int or page != i + 1 or kind not in {"page", "blank_page"})
            )
            or (not pdf and page is not None)
        ):
            raise ExtractionError()
        start = total + (1 if blocks else 0)
        total = start + len(text)
        if total > MAX_CHARACTERS:
            raise ExtractionError("PARSER_LIMIT")
        blocks.append(Block(i, start, total, text, page, tuple(section), kind))
    return Extraction(data["parser"], "\n".join(b.text for b in blocks), tuple(blocks), pages)


@dataclass(frozen=True, slots=True)
class ChunkConfig:
    size: int = 1024
    overlap: int = 128

    def __post_init__(self):
        if (
            type(self.size) is not int
            or not 128 <= self.size <= 8192
            or type(self.overlap) is not int
            or not 0 <= self.overlap <= self.size // 2
        ):
            raise ExtractionError("INPUT_INVALID")

    def fingerprint(self, mime):
        if mime not in PARSERS:
            raise ExtractionError("INPUT_INVALID")
        value = [PARSERS[mime], NORMALIZER, CHUNKER, self.size, self.overlap]
        return hashlib.sha256(json.dumps(value, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True, slots=True, repr=False)
class Chunk:
    ordinal: int
    block_ordinal: int
    start: int
    end: int
    text: str
    page: int | None
    section: tuple[str, ...]
    kind: str
    content_hash: str

    def __repr__(self):
        return "Chunk(<private>)"


def chunks(extraction, config=None):
    config = ChunkConfig() if config is None else config
    if not isinstance(extraction, Extraction) or not isinstance(config, ChunkConfig):
        raise ExtractionError("INPUT_INVALID")
    result = []
    for block in extraction.blocks:
        position = 0
        while position < len(block.text):
            end = min(len(block.text), position + config.size)
            if end < len(block.text):
                # Prefer line/word boundaries, while keeping exact source slices.
                floor = position + config.size // 2
                boundary = block.text.rfind("\n", floor, end)
                if boundary < floor and block.kind != "code":
                    boundary = block.text.rfind(" ", floor, end)
                if boundary >= floor:
                    end = boundary + 1
            text = block.text[position:end]
            result.append(
                Chunk(
                    len(result),
                    block.ordinal,
                    block.start + position,
                    block.start + end,
                    text,
                    block.page,
                    block.section,
                    block.kind,
                    hashlib.sha256(text.encode()).hexdigest(),
                )
            )
            if len(result) > MAX_CHUNKS:
                raise ExtractionError("PARSER_LIMIT")
            if end == len(block.text):
                break
            position = end - config.overlap
    return tuple(result)
