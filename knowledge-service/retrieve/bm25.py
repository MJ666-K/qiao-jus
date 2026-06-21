from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

from rank_bm25 import BM25Okapi

_TOKEN_CN = re.compile(r"[\u4e00-\u9fff]|[a-zA-Z0-9]+")
_TOKEN_WORD = re.compile(r"\w+")


def tokenize(text: str) -> list[str]:
    # Chinese + alphanumeric tokens; falls back to word tokens for pure-Latin text.
    if any("\u4e00" <= c <= "\u9fff" for c in text):
        return [t for t in _TOKEN_CN.findall(text.lower()) if t]
    return _TOKEN_WORD.findall(text.lower())


class BM25Index:
    def __init__(self, corpus: Iterable[str]):
        self.docs: list[list[str]] = [tokenize(d) for d in corpus]
        self.bm25 = BM25Okapi(self.docs) if self.docs else None

    def get_scores(self, query: str) -> list[float]:
        if not self.bm25:
            return []
        tokens = tokenize(query)
        if not tokens:
            return [0.0] * len(self.docs)
        return self.bm25.get_scores(tokens).tolist()

    def top_k(self, query: str, k: int = 10) -> list[tuple[int, float]]:
        scores = self.get_scores(query)
        idx_score = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:k]
        return idx_score


def count_tokens(text: str) -> int:
    return len(tokenize(text))


def vocabulary(corpus: list[str]) -> Counter:
    c: Counter = Counter()
    for doc in corpus:
        c.update(tokenize(doc))
    return c
