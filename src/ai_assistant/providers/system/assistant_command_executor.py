from __future__ import annotations

from ai_assistant.core.interfaces import (
    AssistantCommandExecutor,
    MPCController,
    MediaController,
    OutputController,
)
from ai_assistant.providers.system.skills import (
    SystemSkillFactoryContext,
    build_media_skill,
    build_mpc_skill,
    build_output_skill,
    load_custom_system_skills,
)
from ai_assistant.skills.executor import SkillCommandExecutor
from ai_assistant.skills.models import ExecutableSkill


class SystemAssistantCommandExecutor(AssistantCommandExecutor):
    def __init__(
        self,
        media_controller: MediaController | None = None,
        mpc_controller: MPCController | None = None,
        output_controller: OutputController | None = None,
        active_skill_ids: tuple[str, ...] | None = None,
        skill_factories: tuple[str, ...] | None = None,
    ) -> None:
        skills: list[ExecutableSkill] = []

        media_skill = build_media_skill(media_controller)
        if media_skill is not None:
            skills.append(media_skill)

        mpc_skill = build_mpc_skill(mpc_controller)
        if mpc_skill is not None:
            skills.append(mpc_skill)

        output_skill = build_output_skill(output_controller)
        if output_skill is not None:
            skills.append(output_skill)

        context = SystemSkillFactoryContext(
            media_controller=media_controller,
            mpc_controller=mpc_controller,
            output_controller=output_controller,
        )
        custom_skills = load_custom_system_skills(skill_factories or (), context)
        skills.extend(custom_skills)

        self._executor = SkillCommandExecutor(
            skills=skills,
            active_skill_ids=active_skill_ids,
        )

    async def get_command_catalog(self, user_id: int | None = None) -> list[dict[str, object]]:
        return await self._executor.get_command_catalog(user_id=user_id)

    async def execute_command(
        self,
        command: str,
        args: dict[str, object],
        user_id: int | None = None,
    ) -> dict[str, object]:
        return await self._executor.execute_command(command=command, args=args, user_id=user_id)
