"""Sentence-boundary splitting for document chunking.

Chunks are assembled from complete sentences; overlap tails also start/end on
sentence boundaries (句号 / 句末标点 / 段落换行).
"""

from __future__ import annotations

import re
from collections.abc import Callable

_SENTENCE_END = "。！？.!?"
_PARA_BREAK_RE = re.compile(r"\n\s*\n+")


def split_sentences(text: str) -> list[str]:
    """Split at sentence-ending punctuation and paragraph line breaks."""
    if not text or not text.strip():
        return []

    paragraphs = _PARA_BREAK_RE.split(text.strip())
    sentences: list[str] = []
    for para in paragraphs:
        if not para.strip():
            continue
        sentences.extend(_split_para(para))
    return [s for s in sentences if s.strip()]


def _split_para(para: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    for ch in para:
        buf.append(ch)
        if ch in _SENTENCE_END:
            parts.append("".join(buf))
            buf = []
        elif ch == "\n":
            line = "".join(buf).strip()
            if line:
                parts.append("".join(buf))
            buf = []
    if buf:
        tail = "".join(buf).strip()
        if tail:
            parts.append(tail)
    return parts


def merge_sentences_to_chunks(
    sentences: list[str],
    max_units: int,
    overlap_units: int,
    unit_fn: Callable[[str], int],
) -> list[str]:
    """Merge sentences into chunks; overlap is whole sentences from the tail."""
    if not sentences:
        return []

    pieces: list[str] = []
    cur: list[str] = []
    cur_units = 0

    for s in sentences:
        su = unit_fn(s)
        if cur and cur_units + su > max_units:
            pieces.append("".join(cur).strip())
            tail: list[str] = []
            tail_units = 0
            for x in reversed(cur):
                xu = unit_fn(x)
                if tail_units + xu > overlap_units and tail:
                    break
                tail.insert(0, x)
                tail_units += xu
            cur = list(tail)
            cur_units = tail_units
        cur.append(s)
        cur_units += su

    if cur:
        pieces.append("".join(cur).strip())
    return [p for p in pieces if p]
