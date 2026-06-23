from __future__ import annotations

import logging
from typing import Any

from core.llm import chat_json

logger = logging.getLogger(__name__)

# Domain-typed entities + relations per docs/技术架构文档.md §4.1
ENTITY_TYPES_HINT = (
    "LawArticle（法条）, CaseCause（案由）, EvidenceElement（证据要素）, "
    "ComplianceObligation（合规义务）, LegalCase（具体案例）, "
    "Person, Organization, Location, Date, Concept"
)

RELATION_TYPES_HINT = (
    "APPLIES_TO（法条适用于某案由）, REQUIRES（案由需要某证据）, "
    "CITES（案例引用某法条）, IMPLIES（法条蕴含某合规义务）, "
    "SIMILAR_TO（相似关系）, RELATED（其他关系）"
)

_SYSTEM = (
    "你是一个严谨的法律信息抽取引擎，从给定文本中抽取法律实体和实体关系，"
    "输出严格 JSON。实体 name 用规范全称（如「劳动合同法第39条」「物业纠纷」），"
    "去除代词；关系必须有 source/target/type；description 简洁客观，不超过 50 字。"
    "type 字段必须从给定可选实体类型中选取；relation.type 必须从给定关系类型中选取。"
)

_USER_TMPL = """可选实体类型：{types}
可选关系类型：{rel_types}

文本：
---
{text}
---

输出 JSON 格式：
{{
  "entities": [{{"name":"...", "type":"...", "description":"..."}}],
  "relations": [{{"source":"...", "target":"...", "type":"...", "description":"..."}}]
}}
"""


async def extract_entities_relations(text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if len(text.strip()) < 4:
        return [], []
    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": _USER_TMPL.format(types=ENTITY_TYPES_HINT, rel_types=RELATION_TYPES_HINT, text=text)},
    ]
    try:
        data = await _call_async(messages)
    except Exception as e:
        logger.warning("entity extraction failed: %s", e)
        return [], []

    entities = data.get("entities", []) or []
    relations = data.get("relations", []) or []
    entities = [_normalize_entity(e) for e in entities if e.get("name")]
    relations = [_normalize_relation(r) for r in relations if r.get("source") and r.get("target")]
    return entities, relations


def extract_entities_relations_sync(text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if len(text.strip()) < 4:
        return [], []
    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": _USER_TMPL.format(types=ENTITY_TYPES_HINT, rel_types=RELATION_TYPES_HINT, text=text)},
    ]
    try:
        data = chat_json(messages)
    except Exception as e:
        logger.warning("entity extraction failed: %s", e)
        return [], []

    entities = data.get("entities", []) or []
    relations = data.get("relations", []) or []
    entities = [_normalize_entity(e) for e in entities if e.get("name")]
    relations = [_normalize_relation(r) for r in relations if r.get("source") and r.get("target")]
    return entities, relations


def _normalize_entity(e: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(e["name"]).strip(),
        "type": str(e.get("type") or "Concept").strip(),
        "description": str(e.get("description") or "").strip(),
    }


def _normalize_relation(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": str(r["source"]).strip(),
        "target": str(r["target"]).strip(),
        "type": str(r.get("type") or "RELATED").strip(),
        "description": str(r.get("description") or "").strip(),
    }


async def _call_async(messages: list[dict[str, str]]) -> dict[str, Any]:
    import asyncio

    return await asyncio.to_thread(chat_json, messages)
