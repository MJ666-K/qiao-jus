"""Sliding-window chunker for case / compliance documents."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from ingest.sentences import merge_sentences_to_chunks, split_sentences

logger = logging.getLogger(__name__)


@dataclass
class TextChunk:
    text: str
    metadata: dict
    chunk_index: int


def sliding_window_chunks(
    text: str,
    max_chars: int,
    overlap: int,
    base_metadata: dict | None = None,
) -> list[TextChunk]:
    """Split text into fixed-size chunks; overlap aligns to sentence boundaries."""
    meta = dict(base_metadata or {})
    sentences = split_sentences(text)
    if not sentences:
        stripped = text.strip()
        if not stripped:
            return []
        return [TextChunk(text=stripped, metadata=meta, chunk_index=0)]

    bodies = merge_sentences_to_chunks(
        sentences,
        max_units=max_chars,
        overlap_units=overlap,
        unit_fn=len,
    )
    chunks = [
        TextChunk(text=body, metadata={**meta, "chunk_index": i}, chunk_index=i)
        for i, body in enumerate(bodies)
    ]
    logger.info(
        "[Chunk] sliding_window: %d chunks (max_chars=%d overlap=%d sentences=%d)",
        len(chunks),
        max_chars,
        overlap,
        len(sentences),
    )
    return chunks


# 与 docs/data/README.md 类案格式约定一致，仅解析显式字段
_CASE_META_RE = {
    "cause": re.compile(r"^【案由】\s*([^\n]+)", re.MULTILINE),
    "court": re.compile(r"^【法院】\s*([^\n]+)", re.MULTILINE),
    "case_no": re.compile(r"^【案号】\s*([^\n]+)", re.MULTILINE),
    "year": re.compile(r"^【裁判年份】\s*(\d{4})", re.MULTILINE),
}

_HEADER_STRIP_RES = [
    re.compile(r"^#\s*.+$", re.MULTILINE),
    re.compile(r"^【案由】[^\n]*$", re.MULTILINE),
    re.compile(r"^【法院】[^\n]*$", re.MULTILINE),
    re.compile(r"^【案号】[^\n]*$", re.MULTILINE),
    re.compile(r"^【裁判年份】[^\n]*$", re.MULTILINE),
]


def extract_case_body(text: str) -> str:
    """Remove markdown header lines; return裁判要旨正文 for chunking."""
    body = text
    for pat in _HEADER_STRIP_RES:
        body = pat.sub("", body)
    return body.strip()


def split_case_document(text: str) -> tuple[dict, str]:
    """Parse case header metadata and return (meta, body_without_header)."""
    meta: dict = {"doc_type": "case"}
    title = re.search(r"^#\s*(.+)$", text, re.MULTILINE)
    if title:
        meta["title"] = title.group(1).strip()
    for key, pat in _CASE_META_RE.items():
        m = pat.search(text)
        if m:
            meta[key] = m.group(1).strip()
    body = extract_case_body(text)
    return meta, body


def parse_case_header(text: str) -> dict:
    """Backward-compatible: metadata only."""
    meta, _ = split_case_document(text)
    return meta
