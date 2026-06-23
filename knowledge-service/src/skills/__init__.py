"""Skills 模块

提供模块化的 Skill 架构，支持组合调用。
"""

from skills.base import Skill
from skills.registry import SkillRegistry

# 导入所有 Skill 以自动注册
from skills.rag_search import RagSearchSkill
from skills.graph_query import GraphQuerySkill
from skills.qa import QASkill
from skills.document import DocumentSkill
from skills.search_law import SearchLawSkill
from skills.search_case import SearchCaseSkill
from skills.search_user_docs import SearchUserDocsSkill
from skills.get_user_report import GetUserReportSkill
from skills.check_rules import CheckRulesSkill
from skills.report_generation import ReportGenerationSkill

__all__ = [
    "Skill",
    "SkillRegistry",
    "RagSearchSkill",
    "GraphQuerySkill",
    "QASkill",
    "DocumentSkill",
    "SearchLawSkill",
    "SearchCaseSkill",
    "SearchUserDocsSkill",
    "GetUserReportSkill",
    "CheckRulesSkill",
    "ReportGenerationSkill",
]


def load_skills() -> None:
    """加载所有 Skill 并注册到 SkillRegistry

    幂等：重复调用只会覆盖同名 Skill，不会重复注册。
    """
    SkillRegistry.register(RagSearchSkill)
    SkillRegistry.register(GraphQuerySkill)
    SkillRegistry.register(QASkill)
    SkillRegistry.register(DocumentSkill)
    SkillRegistry.register(SearchLawSkill)
    SkillRegistry.register(SearchCaseSkill)
    SkillRegistry.register(SearchUserDocsSkill)
    SkillRegistry.register(GetUserReportSkill)
    SkillRegistry.register(CheckRulesSkill)
    SkillRegistry.register(ReportGenerationSkill)
