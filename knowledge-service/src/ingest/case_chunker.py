"""Sliding-window chunker for case / compliance documents."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class TextChunk:
    text: str
    metadata: dict
    chunk_index: int


def _split_sentences(text: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    for ch in text:
        buf.append(ch)
        if ch in "。！？!?；;\n":
            parts.append("".join(buf))
            buf = []
    if buf:
        parts.append("".join(buf))
    return [p for p in parts if p.strip()]


def sliding_window_chunks(
    text: str,
    max_chars: int,
    overlap: int,
    base_metadata: dict | None = None,
) -> list[TextChunk]:
    """Split text into fixed-size chunks with overlap, respecting sentence boundaries."""
    meta = dict(base_metadata or {})
    sentences = _split_sentences(text)
    if not sentences:
        stripped = text.strip()
        if not stripped:
            return []
        return [TextChunk(text=stripped, metadata=meta, chunk_index=0)]

    chunks: list[TextChunk] = []
    cur: list[str] = []
    cur_len = 0
    idx = 0

    def flush() -> None:
        nonlocal idx, cur, cur_len
        if not cur:
            return
        body = "".join(cur).strip()
        if body:
            chunks.append(TextChunk(text=body, metadata={**meta, "chunk_index": idx}, chunk_index=idx))
            idx += 1
        # overlap tail
        tail: list[str] = []
        tail_len = 0
        for s in reversed(cur):
            if tail_len + len(s) > overlap:
                break
            tail.insert(0, s)
            tail_len += len(s)
        cur = tail
        cur_len = tail_len

    for s in sentences:
        if cur and cur_len + len(s) > max_chars:
            flush()
        cur.append(s)
        cur_len += len(s)
    flush()
    return chunks


_CASE_META_RE = {
    "cause": re.compile(r"【案由】\s*(.+)"),
    "court": re.compile(r"【法院】\s*(.+)"),
    "case_no": re.compile(r"【案号】\s*(.+)"),
    "year": re.compile(r"【裁判年份】\s*(\d{4})"),
}


def parse_case_header(text: str) -> dict:
    meta: dict = {"doc_type": "case"}
    title = re.search(r"^#\s*(.+)$", text, re.MULTILINE)
    if title:
        meta["title"] = title.group(1).strip()
    for key, pat in _CASE_META_RE.items():
        m = pat.search(text)
        if m:
            meta[key] = m.group(1).strip()
    return meta
