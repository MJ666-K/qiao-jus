"""Smoke test: import everything and validate config can load.

Run with: pytest -q tests/test_smoke.py
"""
import importlib


MODULES = [
    "core.config",
    "core.security",
    "core.tenant",
    "core.llm",
    "models.base",
    "models",
    "schemas",
    "schemas.auth",
    "schemas.dataset",
    "schemas.document",
    "schemas.search",
    "schemas.graph",
    "ingest.parser",
    "ingest.chunker",
    "retrieve.bm25",
    "retrieve.reranker",
    "retrieve.hybrid",
    "pipeline.celery_app",
    "storage.qdrant_client",
    "storage.neo4j_client",
]


def test_modules_import_clean():
    for name in MODULES:
        importlib.import_module(name)


def test_chunker_basic():
    from ingest.chunker import build_parent_child

    text = "句子一。句子二。句子三。" * 30
    parents, groups = build_parent_child(text, parent_tokens=50, child_tokens=20, overlap=5)
    assert parents, "expected at least one parent chunk"
    assert sum(len(g) for g in groups) > 0


def test_rrf_fusion():
    from retrieve.hybrid import rrf_fusion

    fused = rrf_fusion(
        dense=[("a", 0.9), ("b", 0.7), ("c", 0.5)],
        sparse=[("b", 12.0), ("a", 8.0), ("d", 3.0)],
        k=60,
    )
    ids = [doc_id for doc_id, _ in fused]
    assert "a" in ids
    assert "b" in ids
    # Documents appearing in both lists should rank higher.
    assert ids[0] in {"a", "b"}
