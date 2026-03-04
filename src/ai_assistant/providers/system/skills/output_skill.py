from __future__ import annotations

from ai_assistant.core.interfaces import OutputController
from ai_assistant.skills.models import ExecutableSkill, SkillCommandSpec, SkillSpec


def build_output_skill(output_controller: OutputController | None) -> ExecutableSkill | None:
    if output_controller is None:
        return None

    spec = SkillSpec(
        skill_id="output",
        title="Audio output routing",
        llm_description=(
            "Control configured audio output route (enable/disable/toggle/status)."
        ),
        commands=(
            SkillCommandSpec(
                command="output.enable",
                description="Enable configured speakers/output route.",
            ),
            SkillCommandSpec(
                command="output.disable",
                description="Disable configured speakers/output route.",
            ),
            SkillCommandSpec(
                command="output.toggle",
                description="Toggle configured speakers/output route.",
            ),
            SkillCommandSpec(
                command="output.status",
                description="Get configured speakers/output route state.",
            ),
        ),
    )

    def execute(command: str, args: dict[str, object]) -> dict[str, object]:
        del args
        if command == "output.enable":
            enabled = output_controller.enable_output()
            return {"ok": enabled, "message": f"Output enabled: {enabled}"}
        if command == "output.disable":
            enabled = output_controller.disable_output()
            return {"ok": not enabled, "message": f"Output enabled: {enabled}"}
        if command == "output.toggle":
            enabled = output_controller.toggle_output()
            return {"ok": True, "message": f"Output enabled: {enabled}"}
        if command == "output.status":
            enabled = output_controller.is_output_enabled()
            return {"ok": True, "message": f"Output enabled: {enabled}"}
        return {"ok": False, "message": f"Unknown command: {command}"}

    return ExecutableSkill(spec=spec, execute=execute)
