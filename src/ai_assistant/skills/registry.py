from __future__ import annotations

from ai_assistant.skills.models import ExecutableSkill


class SkillRegistry:
    def __init__(
        self,
        skills: list[ExecutableSkill],
        active_skill_ids: tuple[str, ...] | None = None,
    ) -> None:
        self._skills: dict[str, ExecutableSkill] = {}
        self._command_to_skill_id: dict[str, str] = {}

        if active_skill_ids is None or not active_skill_ids:
            self._active_skill_ids = set()
        else:
            self._active_skill_ids = {item.strip().lower() for item in active_skill_ids if item.strip()}

        for skill in skills:
            skill_id = skill.spec.skill_id.strip().lower()
            if not skill_id:
                raise ValueError("skill_id must not be empty")
            if skill_id in self._skills:
                raise ValueError(f"Duplicate skill_id: {skill_id}")
            self._skills[skill_id] = skill

            for command in skill.spec.commands:
                command_name = command.command.strip().lower()
                if not command_name:
                    raise ValueError(f"Skill {skill_id} contains empty command name")
                if command_name in self._command_to_skill_id:
                    owner = self._command_to_skill_id[command_name]
                    raise ValueError(
                        f"Duplicate command name: {command_name} (skills: {owner}, {skill_id})"
                    )
                self._command_to_skill_id[command_name] = skill_id

    def _is_skill_active(self, skill_id: str) -> bool:
        if not self._active_skill_ids:
            return True
        return skill_id in self._active_skill_ids

    def get_command_catalog(self) -> list[dict[str, object]]:
        catalog: list[dict[str, object]] = []
        for skill_id, skill in self._skills.items():
            if not self._is_skill_active(skill_id):
                continue
            for command in skill.spec.commands:
                catalog.append(
                    {
                        "skill": skill.spec.skill_id,
                        "skill_title": skill.spec.title,
                        "skill_description": skill.spec.llm_description,
                        "command": command.command,
                        "description": command.description,
                        "args": dict(command.args),
                    }
                )
        return catalog

    def execute_command(self, command: str, args: dict[str, object]) -> dict[str, object]:
        normalized_command = command.strip().lower()
        skill_id = self._command_to_skill_id.get(normalized_command)
        if not skill_id:
            return {"ok": False, "message": f"Unknown command: {command}"}
        if not self._is_skill_active(skill_id):
            return {"ok": False, "message": f"Skill is disabled for command: {command}"}

        skill = self._skills[skill_id]
        return skill.execute(normalized_command, args)
