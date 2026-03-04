from __future__ import annotations

from ai_assistant.core.interfaces import AssistantCommandExecutor
from ai_assistant.skills.models import ExecutableSkill
from ai_assistant.skills.registry import SkillRegistry


class SkillCommandExecutor(AssistantCommandExecutor):
    def __init__(
        self,
        skills: list[ExecutableSkill],
        active_skill_ids: tuple[str, ...] | None = None,
    ) -> None:
        self._registry = SkillRegistry(skills=skills, active_skill_ids=active_skill_ids)

    async def get_command_catalog(self, user_id: int | None = None) -> list[dict[str, object]]:
        del user_id
        return self._registry.get_command_catalog()

    async def execute_command(
        self,
        command: str,
        args: dict[str, object],
        user_id: int | None = None,
    ) -> dict[str, object]:
        del user_id
        return self._registry.execute_command(command=command, args=args)
