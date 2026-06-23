"""Skills + helpers tests (no DB / no LLM).

Run with: pytest -q tests/test_skills.py
"""
import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture(scope="module", autouse=True)
def _load_skills():
    from skills import load_skills
    load_skills()


def test_skill_registry_has_all_phase3_skills():
    from skills.registry import SkillRegistry
    names = set(SkillRegistry.get_all_names())
    required = {
        "rag_search", "graph_query", "qa", "document",
        "search_law", "search_case", "search_user_docs",
        "get_user_report", "check_rules", "report_generation",
    }
    missing = required - names
    assert not missing, f"missing skills: {missing}"


def test_skills_are_idempotent_to_load():
    from skills import load_skills
    from skills.registry import SkillRegistry
    load_skills()
    load_skills()
    names = set(SkillRegistry.get_all_names())
    assert len(names) == len(set(names))


def test_source_type_mapping_covers_all_doc_types():
    from skills.report_generation.runner import _map_source_type
    assert _map_source_type("law") == "law"
    assert _map_source_type("case") == "case"
    assert _map_source_type("compliance") == "compliance"
    for dt in ("contract", "dispute", "report", None):
        assert _map_source_type(dt) == "user_doc"


def test_infer_doc_type_for_each_report_type():
    from skills.report_generation.runner import _infer_doc_type
    assert _infer_doc_type("contract_review") == "contract"
    assert _infer_doc_type("dispute_analysis") == "dispute"
    assert _infer_doc_type("labor_risk") == "contract"
    assert _infer_doc_type("litigation_draft") == "dispute"
    assert _infer_doc_type("evidence_checklist") == "dispute"


def test_report_generation_skill_validates_input():
    from skills.registry import SkillRegistry
    skill = SkillRegistry.get("report_generation")
    with pytest.raises(ValueError, match="source_doc_id or text"):
        asyncio.run(skill.execute({"tenant_id": "x", "report_type": "contract_review"}))


def test_search_law_skill_requires_query():
    from skills.registry import SkillRegistry
    skill = SkillRegistry.get("search_law")
    with pytest.raises(KeyError):
        asyncio.run(skill.execute({"tenant_id": "x"}))


def test_get_user_report_returns_none_for_missing_id():
    from skills.registry import SkillRegistry
    skill = SkillRegistry.get("get_user_report")
    result = asyncio.run(skill.execute({}))
    assert result == {"report": None}


def test_court_level_inference():
    from ingest.case_chunker import _infer_court_level
    assert _infer_court_level("北京市第一中级人民法院") == "中级"
    assert _infer_court_level("最高人民法院") == "最高"
    assert _infer_court_level("上海市高级人民法院") == "高级"
    assert _infer_court_level("海淀区人民法院") == "基层"
    assert _infer_court_level("北京互联网法院") == "专门"
    assert _infer_court_level(None) is None
    assert _infer_court_level("某法院") == "基层"


def test_case_header_parses_court_level():
    from ingest.case_chunker import parse_case_header
    sample = """# 物业纠纷案

【案由】物业服务合同纠纷
【法院】北京市第一中级人民法院
【案号】（2024）京01民终123号
【裁判年份】2024
"""
    meta = parse_case_header(sample)
    assert meta["cause"] == "物业服务合同纠纷"
    assert meta["court"] == "北京市第一中级人民法院"
    assert meta["case_no"] == "（2024）京01民终123号"
    assert meta["year"] == "2024"
    assert meta["court_level"] == "中级"


def test_dominant_risk_level():
    from pipeline.report_tasks import _dominant_risk_level
    assert _dominant_risk_level([]) == "中"
    assert _dominant_risk_level([{"level": "低"}]) == "低"
    assert _dominant_risk_level([{"level": "低"}, {"level": "中"}]) == "中"
    assert _dominant_risk_level([{"level": "中"}, {"level": "高"}]) == "高"
    assert _dominant_risk_level([{"level": "高"}, {"level": "高"}]) == "高"
