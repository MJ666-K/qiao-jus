"""Unified chunking strategies by doc_type."""

from __future__ import annotations

from dataclasses import dataclass

from ingest.case_chunker import parse_case_header, sliding_window_chunks
from ingest.chunker import build_parent_child
from ingest.doc_types import CASE, CHUNK_PARAMS, COMPLIANCE, GENERAL, LAW
from ingest.law_chunker import split_law_articles


@dataclass
class ChunkUnit:
    text: str
    metadata: dict
    is_parent: bool = True
    parent_index: int = 0


def build_chunks_for_doc(text: str, doc_type: str, doc_metadata: dict | None = None) -> list[ChunkUnit]:
    """Return flat list of chunk units. Law/case use 1-level; general uses parent→child expansion."""
    meta = dict(doc_metadata or {})
    doc_type = doc_type or GENERAL
    params = CHUNK_PARAMS.get(doc_type, CHUNK_PARAMS[GENERAL])

    if doc_type == LAW:
        articles = split_law_articles(
            text,
            law_name=meta.get("law_name"),
            domain=meta.get("domain"),
        )
        return [
            ChunkUnit(text=a.text, metadata={**a.metadata, **meta}, is_parent=True, parent_index=i)
            for i, a in enumerate(articles)
        ]

    if doc_type in {CASE, COMPLIANCE}:
        header = parse_case_header(text) if doc_type == CASE else {"doc_type": COMPLIANCE}
        merged = {**header, **meta}
        raw = sliding_window_chunks(
            text,
            max_chars=params["max_chars"],
            overlap=params["overlap"],
            base_metadata=merged,
        )
        return [
            ChunkUnit(text=c.text, metadata=c.metadata, is_parent=True, parent_index=c.chunk_index)
            for c in raw
        ]

    # Default parent-child RAG
    parents, child_groups = build_parent_child(text)
    units: list[ChunkUnit] = []
    for pi, (parent_text, children) in enumerate(zip(parents, child_groups, strict=False)):
        parent_meta = {**meta, "doc_type": doc_type, "is_parent": True, "parent_index": pi}
        units.append(ChunkUnit(text=parent_text, metadata=parent_meta, is_parent=True, parent_index=pi))
        for ci, child_text in enumerate(children):
            units.append(ChunkUnit(
                text=child_text,
                metadata={**meta, "doc_type": doc_type, "parent_index": pi, "child_index": ci},
                is_parent=False,
                parent_index=pi,
            ))
    return units
