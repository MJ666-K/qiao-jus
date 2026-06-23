"""WebSocket message protocol tests (pure helpers, no actual socket).

Run with: pytest -q tests/test_ws_helpers.py
"""
import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def test_extract_meta_parses_confidence_and_questions():
    from api.routes.ws import _extract_meta
    sample = (
        "根据劳动合同法第39条...\n\n"
        "置信度: 82\n"
        "建议问题: 风险2怎么改？; 有没有类似类案？; 怎么修改这一条款？"
    )
    suggested, conf, body = _extract_meta(sample)
    assert conf == 82
    assert len(suggested) == 3
    assert "风险2怎么改？" in suggested[0]
    assert "根据劳动合同法第39条" in body
    assert "置信度" not in body
    assert "建议问题" not in body


def test_extract_meta_clamps_confidence_range():
    from api.routes.ws import _extract_meta
    _, conf_high, _ = _extract_meta("答案\n置信度: 250")
    assert conf_high == 100
    _, conf_three_digits, _ = _extract_meta("答案\n置信度: 999")
    assert conf_three_digits == 100


def test_extract_meta_handles_missing_meta():
    from api.routes.ws import _extract_meta
    suggested, conf, body = _extract_meta("纯文本回答，无元信息")
    assert suggested == []
    assert conf is None
    assert body == "纯文本回答，无元信息"


def test_system_prompt_differs_for_report_mode():
    from api.routes.ws import _system_prompt
    general = _system_prompt(False)
    bound = _system_prompt(True)
    assert "依据上下文" in general
    assert "绑定" in bound
    assert "报告" in bound


def test_context_block_renders_citations():
    from api.routes.ws import _context_block
    from schemas.search import Citation
    cits = [
        Citation(source_type="law", source_title="劳动合同法第39条", excerpt="用人单位可以解除..."),
        Citation(source_type="case", source_title="类似物业纠纷案"),
    ]
    block = _context_block(cits, "")
    assert "[C1]" in block
    assert "劳动合同法第39条" in block
    assert "[C2]" in block
    assert "类似物业纠纷案" in block


def test_context_block_with_report():
    from api.routes.ws import _context_block
    block = _context_block([], "【已绑定报告 type=contract_review】\n摘要：合同存在3处风险")
    assert "已绑定报告" in block
    assert "合同存在3处风险" in block


def test_format_history_reverses_to_chronological():
    from api.routes.ws import _format_history
    class FakeMsg:
        def __init__(self, role, content):
            self.role = role
            self.content = content
    rows = [
        FakeMsg("user", "first"),
        FakeMsg("assistant", "answer1"),
        FakeMsg("user", "second"),
        FakeMsg("assistant", "answer2"),
    ]
    formatted = _format_history(rows)
    assert formatted[0] == {"role": "user", "content": "first"}
    assert formatted[-1] == {"role": "assistant", "content": "answer2"}
