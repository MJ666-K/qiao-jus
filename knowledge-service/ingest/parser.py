from dataclasses import dataclass
from pathlib import Path


@dataclass
class ParsedBlock:
    type: str
    text: str
    page: int | None = None


_TEXT_EXTS = {".md", ".markdown", ".txt", ".text", ".rst", ".log", ".csv", ".json", ".yaml", ".yml"}


def parse_file(path: Path, mime_type: str | None = None) -> list[ParsedBlock]:
    # `unstructured`'s auto-detector pulls spaCy for hi_res on PDF/DOCX; that
    # download fails offline. For plain-text formats we bypass unstructured
    # entirely and read the file directly.
    suffix = path.suffix.lower()
    if suffix in _TEXT_EXTS:
        return _parse_text(path)

    from unstructured.partition.auto import partition

    strategy = "hi_res" if suffix in {".pdf", ".docx", ".pptx"} else "fast"
    elements = partition(filename=str(path), strategy=strategy)
    blocks: list[ParsedBlock] = []
    for el in elements:
        text = (el.text or "").strip()
        if not text:
            continue
        cat = el.category or "Text"
        page = getattr(el.metadata, "page_number", None)
        blocks.append(ParsedBlock(type=cat, text=text, page=page))
    return blocks


def _parse_text(path: Path) -> list[ParsedBlock]:
    # Strip Markdown heading markers so downstream chunker sees clean sentences.
    raw = path.read_text(encoding="utf-8", errors="replace")
    blocks: list[ParsedBlock] = []
    for line in raw.splitlines():
        line = line.rstrip()
        if not line:
            continue
        is_heading = line.lstrip().startswith("#")
        text = line.lstrip("# ").strip()
        if text:
            blocks.append(ParsedBlock(type="Title" if is_heading else "Text", text=text))
    return blocks or [ParsedBlock(type="Text", text=raw.strip())]


def merge_blocks_to_text(blocks: list[ParsedBlock]) -> str:
    parts: list[str] = []
    for b in blocks:
        if b.type.lower() == "title":
            parts.append(f"\n## {b.text}\n")
        elif b.type.lower() in {"table", "table_row"}:
            parts.append(f"\n{b.text}\n")
        else:
            parts.append(b.text)
    return "\n".join(parts).strip()
