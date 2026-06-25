import json
import logging
import uuid
from typing import Any

from sqlalchemy import select

from core.llm import chat_json
from models.base import Chunk, Document
from skills.base import Skill
from storage.postgres import SessionLocal

logger = logging.getLogger(__name__)


PROMPTS: dict[str, dict[str, str]] = {
    "contract_review": {
        "system": (
            "你是合同审查专家。基于用户合同原文与平台法规/类案，输出合同风险审查报告。"
            "必须严格 JSON：{summary, risk_items:[{level,desc,law_ref,chunk_id,suggestion}], "
            "suggested_questions:[str,str,str], confidence:0-100}。"
            "level 取值 高/中/低；chunk_id 来自 citations；confidence 自评。"
            "无风险时 risk_items 为空数组，confidence 相应降低。"
        ),
        "ruleset": None,
    },
    "dispute_analysis": {
        "system": (
            "你是纠纷研判专家。基于用户纠纷材料与平台类案/法规，输出纠纷研判报告。"
            "必须严格 JSON：{summary, risk_items:[{level,desc,law_ref,chunk_id,suggestion}], "
            "suggested_questions, confidence}。risk_items 描述潜在风险点/争议焦点/"
            "举证瑕疵。chunk_id 取自 citations。"
        ),
        "ruleset": None,
    },
    "labor_risk": {
        "system": (
            "你是用工合规专家。结合规则引擎命中项 + 用户材料 + 劳动法规，输出用工风险报告。"
            "必须严格 JSON：{summary, risk_items:[{level,desc,law_ref,chunk_id,suggestion}], "
            "suggested_questions, confidence}。规则命中项必须出现在 risk_items 中，"
            "law_ref 字段填入规则附带的法条。"
        ),
        "ruleset": "labor_rules",
    },
    "litigation_draft": {
        "system": (
            "你是诉讼文书起草专家。基于案由与事实，输出民事起诉状草稿。"
            "必须严格 JSON：{summary, parties:{plaintiff,defendant}, claims:[str,str], "
            "facts:[str,str,str], evidence_list:[{name,purpose}], risk_items:[{level,desc,"
            "law_ref,chunk_id,suggestion}], suggested_questions, confidence}。"
            "其中 risk_items 用来填「法律依据与请求权基础」（每条 desc 写一条法条依据，"
            "law_ref 写法条全名）；claims 是诉讼请求；facts 是事实与理由段；"
            "evidence_list 是证据清单（name 证据名称，purpose 证明目的）。"
        ),
        "ruleset": None,
    },
    "evidence_checklist": {
        "system": (
            "你是证据指引专家。基于案由与图谱证据关系，输出证据清单报告。"
            "必须严格 JSON：{summary, evidence_items:[{name,level,purpose,collect_tip}], "
            "procedure_steps:[str,str,str], risk_items:[{level,desc,law_ref,chunk_id,"
            "suggestion}], suggested_questions, confidence}。"
            "其中 evidence_items 是按重要性排序的证据清单（level 高/中/低 表示关键程度，"
            "purpose 证明目的，collect_tip 取证要点）；procedure_steps 是举证流程步骤；"
            "risk_items 用于标注每项证据对应的法条依据（law_ref）。"
        ),
        "ruleset": None,
    },
}


async def _load_doc_chunks(doc_id: str, limit: int = 50) -> list[dict[str, Any]]:
    async with SessionLocal() as session:
        res = await session.execute(
            select(Chunk, Document.title, Document.metadata_)
            .join(Document, Chunk.document_id == Document.id)
            .where(Chunk.document_id == uuid.UUID(doc_id), Chunk.parent_id.is_(None))
            .order_by(Chunk.chunk_index)
            .limit(limit)
        )
        out: list[dict[str, Any]] = []
        for c, title, doc_meta in res.all():
            out.append({
                "chunk_id": str(c.id),
                "text": c.text,
                "title": title,
                "doc_meta": doc_meta or {},
                "document_id": doc_id,
            })
        return out


async def _load_multi_doc_chunks(doc_ids: list[str], limit_per_doc: int = 20) -> list[dict[str, Any]]:
    all_chunks: list[dict[str, Any]] = []
    for doc_id in doc_ids:
        chunks = await _load_doc_chunks(doc_id, limit=limit_per_doc)
        all_chunks.extend(chunks)
    return all_chunks


def _compose_doc_text(chunks: list[dict[str, Any]], max_chars: int = 12000) -> tuple[str, dict[str, Any]]:
    if not chunks:
        return "", {}
    sections: list[str] = []
    current_doc_id = None
    current_title = "文档"
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        if buffer:
            sections.append(f"【文档：{current_title}】\n" + "\n\n".join(buffer))
            buffer = []

    for c in chunks:
        doc_id = c.get("document_id")
        if doc_id != current_doc_id:
            flush()
            current_doc_id = doc_id
            current_title = c.get("title") or "文档"
        buffer.append(c["text"])
        if len("\n\n".join(sections)) + len("\n\n".join(buffer)) >= max_chars:
            break
    flush()
    doc_meta = chunks[0].get("doc_meta") or {}
    return "\n\n".join(sections)[:max_chars], doc_meta


def _map_source_type(doc_type: str | None) -> str:
    if doc_type == "law":
        return "law"
    if doc_type == "case":
        return "case"
    if doc_type == "compliance":
        return "compliance"
    return "user_doc"


_REPORT_TYPE_TO_DOC_TYPE = {
    "contract_review": "contract",
    "dispute_analysis": "dispute",
    "labor_risk": "contract",
    "litigation_draft": "dispute",
    "evidence_checklist": "dispute",
}


def _infer_doc_type(report_type: str) -> str:
    return _REPORT_TYPE_TO_DOC_TYPE.get(report_type, "contract")


def _to_citations(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for h in hits:
        cid = h.get("chunk_id")
        if not cid or cid in seen:
            continue
        seen.add(cid)
        out.append({
            "chunk_id": cid,
            "document_id": h.get("document_id"),
            "source_type": h.get("source_type") or _map_source_type(h.get("doc_type")),
            "source_title": h.get("source_title") or h.get("source") or "未知来源",
            "excerpt": (h.get("text") or "")[:280],
            "page": h.get("page"),
            "score": h.get("score"),
        })
    return out


def _rule_hits_to_citations(matched_rules: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Rules don't have chunk_id (they're external law_ref). Return as
    synthesized citations + risk_items seed."""
    citations = [
        {
            "chunk_id": None,
            "document_id": None,
            "source_type": "law",
            "source_title": r.get("law_ref") or r.get("title"),
            "excerpt": r.get("suggestion"),
            "page": None,
            "score": None,
        }
        for r in matched_rules
    ]
    risk_seed = [
        {
            "level": r.get("level", "中"),
            "desc": r.get("title"),
            "law_ref": r.get("law_ref"),
            "chunk_id": None,
            "suggestion": r.get("suggestion"),
        }
        for r in matched_rules
    ]
    return citations, risk_seed


class ReportGenerationSkill(Skill):
    """Agent flow for report generation. Per report_type it:
    1) reads user source-doc chunks
    2) calls search_law / search_case / query_graph / check_rules tools
    3) assembles a structured prompt and calls LLM with JSON output
    4) returns parsed report dict
    """

    name = "report_generation"
    description = "Generate structured analysis report from user materials + platform KB"

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        tenant_id = params["tenant_id"]
        source_doc_ids = params.get("source_doc_ids") or []
        source_doc_id = params.get("source_doc_id")
        if not source_doc_ids and source_doc_id:
            source_doc_ids = [source_doc_id]
        direct_text = params.get("text")
        report_type = params.get("report_type") or "contract_review"
        prompt_cfg = PROMPTS.get(report_type) or PROMPTS["contract_review"]

        if source_doc_ids:
            per_doc = max(10, 30 // len(source_doc_ids))
            user_chunks = await _load_multi_doc_chunks(source_doc_ids, limit_per_doc=per_doc)
            if not user_chunks:
                raise ValueError(f"source docs {source_doc_ids} have no chunks; cannot generate report")
            doc_text, doc_meta = _compose_doc_text(user_chunks)
        elif direct_text:
            doc_text = direct_text[:8000]
            doc_meta = {"doc_type": _infer_doc_type(report_type)}
        else:
            raise ValueError("either source_doc_id or text must be provided")

        all_hits: list[dict[str, Any]] = []
        query_text = doc_text[:1500]

        law_task = self.call_skill("search_law", {"query": query_text, "tenant_id": tenant_id})
        case_task = self.call_skill("search_case", {"query": query_text, "tenant_id": tenant_id})
        law_res, case_res = await law_task, await case_task
        all_hits.extend(law_res.get("hits", []))
        all_hits.extend(case_res.get("hits", []))

        graph_citations: list[dict[str, Any]] = []
        graph_path: list[str] = []
        try:
            graph_res = await self.call_skill("graph_query", {
                "query": query_text, "tenant_id": tenant_id, "depth": 2,
            })
            for e in (graph_res or {}).get("entities", [])[:5]:
                if isinstance(e, dict) and e.get("name"):
                    graph_path.append(f"{e.get('type','实体')}:{e['name']}")
        except Exception as e:
            logger.warning("graph_query failed during report gen: %s", e)

        risk_seed: list[dict[str, Any]] = []
        if prompt_cfg["ruleset"]:
            rules_res = await self.call_skill("check_rules", {
                "text": doc_text, "ruleset": prompt_cfg["ruleset"],
            })
            rule_cits, risk_seed = _rule_hits_to_citations(rules_res.get("matched", []))
            graph_citations.extend(rule_cits)

        citations = _to_citations(all_hits) + graph_citations

        cited_block = "\n".join(
            f"[C{i+1}] {c['source_title']} ({c['source_type']})"
            + (f": {c['excerpt']}" if c.get("excerpt") else "")
            + (f" chunk_id={c['chunk_id']}" if c.get("chunk_id") else "")
            for i, c in enumerate(citations[:15])
        )
        seed_block = ""
        if risk_seed:
            seed_block = "\n\n规则引擎已命中以下风险（必须包含在 risk_items 中）：\n" + json.dumps(risk_seed, ensure_ascii=False)

        user_msg = (
            f"用户材料（doc_type={doc_meta.get('doc_type', '?')}）：\n{doc_text}\n\n"
            f"参考来源（citations）：\n{cited_block or '（无）'}{seed_block}\n\n"
            f"图谱关联：{', '.join(graph_path) or '（无）'}\n\n"
            "请输出报告 JSON。"
        )
        messages = [
            {"role": "system", "content": prompt_cfg["system"]},
            {"role": "user", "content": user_msg},
        ]
        try:
            report = chat_json(messages, temperature=0.2)
        except Exception as e:
            logger.exception("LLM JSON failed for report_type=%s", report_type)
            raise RuntimeError(f"LLM 报告生成失败: {e}") from e

        risk_items = report.get("risk_items") or []
        if risk_seed:
            existing_titles = {r.get("desc") for r in risk_items if isinstance(r, dict)}
            for seed in risk_seed:
                if seed["desc"] not in existing_titles:
                    risk_items.append(seed)
        summary = report.get("summary") or ""
        suggested = report.get("suggested_questions") or []
        confidence = int(report.get("confidence") or 0)

        return {
            "report_type": report_type,
            "summary": summary,
            "risk_items": risk_items,
            "citations": citations,
            "suggested_questions": suggested,
            "confidence": confidence,
            "graph_path": graph_path,
        }
