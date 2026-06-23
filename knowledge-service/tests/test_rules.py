"""Rules engine tests.

Run with: pytest -q tests/test_rules.py
"""
import asyncio

import pytest


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture(scope="module", autouse=True)
def _load_skills():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from skills import load_skills
    load_skills()


def test_labor_rules_loaded():
    from skills.check_rules.runner import _load_ruleset, _RULES_CACHE
    _RULES_CACHE.clear()
    rs = _load_ruleset("labor_rules")
    assert len(rs.rules) >= 15, f"expected >= 15 labor rules, got {len(rs.rules)}"
    for rule in rs.rules:
        assert rule.id
        assert rule.title
        assert rule.level in ("高", "中", "低")
        assert rule.law_ref


def test_probation_rule_matches():
    from skills.registry import SkillRegistry
    skill = SkillRegistry.get("check_rules")
    result = asyncio.run(skill.execute({
        "text": "本合同约定试用期为一年。",
        "ruleset": "labor_rules",
    }))
    ids = {m["rule_id"] for m in result["matched"]}
    assert "LAB-002" in ids, "probation rule should match"


def test_overtime_rule_matches():
    from skills.registry import SkillRegistry
    skill = SkillRegistry.get("check_rules")
    result = asyncio.run(skill.execute({
        "text": "员工加班无加班费，公司不支付任何报酬。",
        "ruleset": "labor_rules",
    }))
    ids = {m["rule_id"] for m in result["matched"]}
    assert "LAB-005" in ids


def test_social_security_rule_matches():
    from skills.registry import SkillRegistry
    skill = SkillRegistry.get("check_rules")
    result = asyncio.run(skill.execute({
        "text": "员工自愿放弃社保，公司不缴纳社会保险。",
        "ruleset": "labor_rules",
    }))
    ids = {m["rule_id"] for m in result["matched"]}
    assert "LAB-008" in ids or "LAB-014" in ids


def test_no_false_positive_on_clean_text():
    from skills.registry import SkillRegistry
    skill = SkillRegistry.get("check_rules")
    result = asyncio.run(skill.execute({
        "text": "本合同遵照劳动合同法订立，试用期一个月，工资按月支付，依法缴纳社保。",
        "ruleset": "labor_rules",
    }))
    high_severity = [m for m in result["matched"] if m["level"] == "高"]
    assert not high_severity, f"false positive on clean text: {high_severity}"


def test_unknown_ruleset_returns_empty():
    from skills.check_rules.runner import _load_ruleset, _RULES_CACHE
    _RULES_CACHE.clear()
    rs = _load_ruleset("nonexistent_ruleset_v2")
    assert rs.rules == []
