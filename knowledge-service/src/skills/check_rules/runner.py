from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from skills.base import Skill


class Rule(BaseModel):
    id: str
    title: str
    pattern: str | None = None
    keyword: str | None = None
    level: str = "中"
    law_ref: str | None = None
    suggestion: str = ""


class RuleSet(BaseModel):
    ruleset: str
    rules: list[Rule] = Field(default_factory=list)


_RULES_CACHE: dict[str, RuleSet] = {}
_RULES_DIR = Path(__file__).resolve().parent / "rules"


def _load_ruleset(name: str) -> RuleSet:
    if name not in _RULES_CACHE:
        path = _RULES_DIR / f"{name}.yaml"
        if not path.exists():
            _RULES_CACHE[name] = RuleSet(ruleset=name)
        else:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            _RULES_CACHE[name] = RuleSet.model_validate({**data, "ruleset": name})
    return _RULES_CACHE[name]


class CheckRulesSkill(Skill):
    """Rules engine. Matches user text against YAML-defined patterns/keywords.

    Phase 1 ships a placeholder labor_rules.yaml covering common employment
    risks (试用期/违约金/加班费/未签书面合同). Real production rules need legal
    review and a proper evaluation set.
    """

    name = "check_rules"
    description = "Apply domain rule engine to detect hard compliance violations"

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        text = params.get("text", "") or ""
        ruleset = params.get("ruleset", "labor_rules")
        rs = _load_ruleset(ruleset)
        hits: list[dict[str, Any]] = []
        for rule in rs.rules:
            matched = False
            if rule.pattern and re.search(rule.pattern, text):
                matched = True
            elif rule.keyword and rule.keyword in text:
                matched = True
            if matched:
                hits.append({
                    "rule_id": rule.id,
                    "title": rule.title,
                    "level": rule.level,
                    "law_ref": rule.law_ref,
                    "suggestion": rule.suggestion,
                })
        return {
            "ruleset": ruleset,
            "total_rules": len(rs.rules),
            "matched": hits,
            "matched_count": len(hits),
        }
