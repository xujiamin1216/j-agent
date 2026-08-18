"""UseSkillTool -- let the LLM invoke skills by name.

Skills are discovered from ``<work_dir>/.j-agent/skills/`` and their
descriptions are injected into the system prompt. When the LLM determines
that a user's request matches a skill's trigger conditions, it calls this
tool to load and expand the skill's prompt template.

The SkillRegistry is created lazily on first execution (progressive
loading), using the ``work_dir`` set by ToolRegistry.
"""

from __future__ import annotations

from typing import Any

from src.skills.discovery import discover_skills
from src.skills.skill import SkillRegistry
from src.tools.base import Tool


class UseSkillTool(Tool):
    name = "use_skill"
    description = (
        "Use a skill by name. Skills provide specialized capabilities and "
        "instructions. Available skills and their trigger conditions are "
        "listed in the system prompt. Call this tool when the user's request "
        "matches a skill's trigger conditions, BEFORE generating any other "
        "response about the task."
    )
    parameters = {
        "type": "object",
        "properties": {
            "skill_name": {
                "type": "string",
                "description": "The name of the skill to invoke.",
            },
            "args": {
                "type": "string",
                "description": "Additional context or arguments for the skill.",
            },
        },
        "required": ["skill_name"],
        "additionalProperties": False,
    }

    def __init__(self) -> None:
        self._registry: SkillRegistry | None = None

    def _get_registry(self) -> SkillRegistry:
        """Lazily create a SkillRegistry, scoped to work_dir if bound."""
        if self._registry is None:
            if self.work_dir is not None:
                skills_dir = self.work_dir / ".j-agent" / "skills"
            else:
                skills_dir = None

            self._registry = SkillRegistry(skills_dir=skills_dir)
            for skill in discover_skills(skills_dir):
                self._registry.register(skill)

        return self._registry

    def execute(
        self,
        *,
        skill_name: str,
        args: str = "",
        **kwargs: Any,
    ) -> str:
        registry = self._get_registry()

        result = registry.invoke(skill_name, args)
        if result is None:
            available = ", ".join(registry.names()) or "(none)"
            return (
                f"Skill '{skill_name}' not found. "
                f"Available skills: {available}"
            )

        return result
