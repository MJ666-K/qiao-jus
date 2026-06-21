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

__all__ = [
    "Skill",
    "SkillRegistry",
    "RagSearchSkill",
    "GraphQuerySkill",
    "QASkill",
    "DocumentSkill",
]


def load_skills() -> None:
    """加载所有 Skill 并注册到 SkillRegistry

    应在应用启动时调用。
    """
    SkillRegistry.register(RagSearchSkill)
    SkillRegistry.register(GraphQuerySkill)
    SkillRegistry.register(QASkill)
    SkillRegistry.register(DocumentSkill)
