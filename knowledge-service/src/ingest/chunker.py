import logging
from dataclasses import dataclass

from core.config import settings
from ingest.sentences import merge_sentences_to_chunks, split_sentences

logger = logging.getLogger(__name__)


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
    """Split by sentence boundaries; overlap also aligns to full sentences."""
    sentences = split_sentences(text)
    if not sentences:
        return []
    return merge_sentences_to_chunks(
        sentences,
        max_units=max_tokens,
        overlap_units=overlap,
        unit_fn=_approx_tokens,
    )


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

    parents = _split_text(text, pt, ov)
    if not parents:
        return [], []
    parent_child_texts = [_split_text(p, ct, ov) for p in parents]
    logger.info(
        "[Chunk] parent_child: %d parents, %d children (parent_tokens=%d child_tokens=%d overlap=%d)",
        len(parents),
        sum(len(g) for g in parent_child_texts),
        pt,
        ct,
        ov,
    )
    return parents, parent_child_texts
