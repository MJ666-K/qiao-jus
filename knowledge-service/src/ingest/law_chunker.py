"""Law document chunker: 1 article (第X条) = 1 chunk."""

from __future__ import annotations

import re
from dataclasses import dataclass

# 第39条 / 第三十九条 / 第39条之一
_ARTICLE_RE = re.compile(
    r"(?:^|\n)\s*(?:#{1,3}\s*)?"
    r"(第[0-9一二三四五六七八九十百零〇两]+条(?:之[0-9一二三四五六七八九十]+)?)"
    r"\s*\n?",
    re.MULTILINE,
)

_LAW_META_RE = {
    "domain": re.compile(r"【领域】\s*(.+)"),
    "level": re.compile(r"【法律层级】\s*(.+)"),
    "law_name": re.compile(r"^#\s*(.+)$", re.MULTILINE),
}


@dataclass
class LawArticle:
    article_no: str
    text: str
    metadata: dict


def _parse_header(text: str) -> dict:
    meta: dict = {}
    for key, pat in _LAW_META_RE.items():
        m = pat.search(text)
        if m:
            meta[key] = m.group(1).strip()
    return meta


def split_law_articles(text: str, law_name: str | None = None, domain: str | None = None) -> list[LawArticle]:
    """Split law text into one chunk per 法条."""
    header_meta = _parse_header(text)
    name = law_name or header_meta.get("law_name") or "未知法律"
    dom = domain or header_meta.get("domain") or "综合"

    matches = list(_ARTICLE_RE.finditer(text))
    if not matches:
        # Fallback: treat whole doc as one article
        body = text.strip()
        if body:
            return [LawArticle(
                article_no="全文",
                text=body,
                metadata={"doc_type": "law", "law_name": name, "domain": dom, "article_no": "全文"},
            )]
        return []

    articles: list[LawArticle] = []
    for i, m in enumerate(matches):
        article_no = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if not body:
            continue
        full = f"{article_no}\n{body}"
        articles.append(LawArticle(
            article_no=article_no,
            text=full,
            metadata={
                "doc_type": "law",
                "law_name": name,
                "domain": dom,
                "article_no": article_no,
                "level": header_meta.get("level", "法律"),
            },
        ))
    return articles
