from abc import ABC, abstractmethod
from typing import Any


class Skill(ABC):
    """Skill 抽象基类

    所有 Skill 必须实现 execute 方法。
    Skill 可以通过 call_skill 调用其他 Skill。
    """

    name: str = ""
    description: str = ""

    _registry: "SkillRegistry | None" = None

    @abstractmethod
    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """执行 Skill，返回结果"""
        pass

    async def call_skill(self, skill_name: str, params: dict[str, Any]) -> dict[str, Any]:
        """组合调用其他 Skill

        Args:
            skill_name: 被调用的 Skill 名称
            params: 调用参数

        Returns:
            被调用 Skill 的执行结果

        Raises:
            RuntimeError: 如果注册中心未设置
            KeyError: 如果 Skill 不存在
        """
        if not self._registry:
            raise RuntimeError("Skill registry not set, cannot call other skills")
        skill = self._registry.get(skill_name)
        if not skill:
            raise KeyError(f"Skill not found: {skill_name}")
        return await skill.execute(params)

    def get_metadata(self) -> dict[str, Any]:
        """返回 Skill 元数据"""
        return {
            "name": self.name,
            "description": self.description,
        }
