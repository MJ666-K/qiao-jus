from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import Skill


class SkillRegistry:
    """Skill 注册中心

    管理所有 Skill 的注册和获取。
    """

    _skills: dict[str, type["Skill"]] = {}

    @classmethod
    def register(cls, skill_class: type["Skill"]) -> None:
        """注册 Skill 类

        Args:
            skill_class: Skill 子类
        """
        if not hasattr(skill_class, "name") or not skill_class.name:
            raise ValueError(f"Skill class {skill_class.__name__} must have a name")
        cls._skills[skill_class.name] = skill_class

    @classmethod
    def get(cls, name: str) -> "Skill | None":
        """获取 Skill 实例

        Args:
            name: Skill 名称

        Returns:
            Skill 实例，如果不存在返回 None
        """
        skill_class = cls._skills.get(name)
        if not skill_class:
            return None
        skill = skill_class()
        skill._registry = cls
        return skill

    @classmethod
    def list_skills(cls) -> list[dict]:
        """列出所有已注册的 Skill 元数据"""
        result = []
        for skill_class in cls._skills.values():
            instance = skill_class()
            result.append(instance.get_metadata())
        return result

    @classmethod
    def get_all_names(cls) -> list[str]:
        """获取所有已注册 Skill 的名称"""
        return list(cls._skills.keys())

    @classmethod
    def clear(cls) -> None:
        """清空所有注册的 Skill（主要用于测试）"""
        cls._skills.clear()
