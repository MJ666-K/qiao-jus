"""Schema validation tests.

Run with: pytest -q tests/test_schemas.py
"""
import pytest


def test_analyze_request_dual_mode():
    from schemas.report import AnalyzeRequest
    doc_mode = AnalyzeRequest(source_doc_id="00000000-0000-0000-0000-000000000000")
    assert doc_mode.source_doc_id is not None
    assert doc_mode.text is None
    assert doc_mode.resolved_doc_ids() == [doc_mode.source_doc_id]

    multi = AnalyzeRequest(source_doc_ids=[
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000002",
    ])
    assert len(multi.resolved_doc_ids()) == 2

    text_mode = AnalyzeRequest(text="这是一段合同文本", title="测试")
    assert text_mode.text is not None
    assert text_mode.source_doc_id is None
    assert text_mode.resolved_doc_ids() == []


def test_report_out_includes_phase4_fields():
    from schemas.report import ReportOut
    fields = set(ReportOut.model_fields.keys())
    for required in (
        "parties", "claims", "facts", "evidence_list",
        "evidence_items", "procedure_steps", "status", "error",
        "risk_items", "citations", "suggested_questions", "confidence",
    ):
        assert required in fields, f"ReportOut missing field: {required}"


def test_citation_source_type_enum():
    from schemas.search import Citation, SourceType
    from typing import get_args
    valid_types = set(get_args(SourceType))
    assert valid_types == {"law", "case", "report", "user_doc", "compliance", "graph"}
    c = Citation(source_type="law", source_title="劳动合同法第39条")
    assert c.source_type == "law"


def test_risk_item_level_enum():
    from schemas.report import RiskItem
    ri = RiskItem(level="高", desc="风险描述")
    assert ri.level == "高"
    ri_en = RiskItem(level="high", desc="english level")
    assert ri_en.level == "高"
    ri_unknown = RiskItem(level="X", desc="fallback")
    assert ri_unknown.level == "中"


def test_report_type_literal_complete():
    from schemas.report import ReportType
    from typing import get_args
    types = set(get_args(ReportType))
    assert types == {
        "contract_review", "dispute_analysis", "labor_risk",
        "litigation_draft", "evidence_checklist",
    }


def test_conversation_create_optional_fields():
    from schemas.conversation import ConversationCreate
    c = ConversationCreate()
    assert c.title == "新对话"
    assert c.report_id is None
    c2 = ConversationCreate(title="合同审查问答", report_id="00000000-0000-0000-0000-000000000000")
    assert c2.title == "合同审查问答"


def test_message_out_shape():
    from schemas.conversation import MessageOut
    fields = set(MessageOut.model_fields.keys())
    assert {"id", "role", "content", "citations", "suggested_questions", "confidence"} <= fields
