from dataclasses import dataclass

from core.config import settings


@dataclass
class ChunkUnit:
    text: str
    token_count: int
    is_parent: bool
    parent_index: int


def _approx_tokens(text: str) -> int:
    # 1 token ≈ 1.5 Chinese chars or 4 English chars; rough but chunking-tolerant.
    cn = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    en_chars = len(text) - cn
    return int(cn / 1.5 + en_chars / 4)


def _split_text(text: str, max_tokens: int, overlap: int) -> list[str]:
    if not text.strip():
        return []
    sentences: list[str] = []
    buf: list[str] = []
    for ch in text:
        buf.append(ch)
        if ch in "。！？!?；;\n":
            sentences.append("".join(buf))
            buf = []
    if buf:
        sentences.append("".join(buf))

    pieces: list[str] = []
    cur: list[str] = []
    cur_tokens = 0
    for s in sentences:
        st = _approx_tokens(s)
        if cur and cur_tokens + st > max_tokens:
            pieces.append("".join(cur).strip())
            tail = []
            tail_tokens = 0
            for x in reversed(cur):
                xt = _approx_tokens(x)
                if tail_tokens + xt > overlap:
                    break
                tail.insert(0, x)
                tail_tokens += xt
            cur = list(tail)
            cur_tokens = tail_tokens
        cur.append(s)
        cur_tokens += st
    if cur:
        pieces.append("".join(cur).strip())
    return [p for p in pieces if p]


def build_parent_child(
    text: str,
    parent_tokens: int | None = None,
    child_tokens: int | None = None,
    overlap: int | None = None,
) -> tuple[list[str], list[list[str]]]:
    """Returns (parents, parent_child_texts) where parent_child_texts[i] is the
    list of child strings for parent i. Children are searched; parents are
    returned for context (parent-child RAG trick)."""
    pt = parent_tokens or settings.chunk_parent_tokens
    ct = child_tokens or settings.chunk_child_tokens
    ov = overlap or settings.chunk_overlap_tokens

    parents = _split_text(text, pt, ov // 2)
    if not parents:
        return [], []
    parent_child_texts = [_split_text(p, ct, ov) for p in parents]
    return parents, parent_child_texts
