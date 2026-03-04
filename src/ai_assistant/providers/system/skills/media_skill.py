from __future__ import annotations

from ai_assistant.core.interfaces import MediaController
from ai_assistant.skills.models import ExecutableSkill, SkillCommandSpec, SkillSpec


def build_media_skill(media_controller: MediaController | None) -> ExecutableSkill | None:
    if media_controller is None:
        return None

    spec = SkillSpec(
        skill_id="media",
        title="System media control",
        llm_description=(
            "Control operating system media keys: play/pause and track switching. "
            "Use when user asks to pause, resume, or change current media track."
        ),
        commands=(
            SkillCommandSpec(
                command="media.play_pause",
                description="Toggle system media playback pause/play.",
            ),
            SkillCommandSpec(
                command="media.previous_track",
                description="Switch to previous system media track.",
            ),
            SkillCommandSpec(
                command="media.next_track",
                description="Switch to next system media track.",
            ),
        ),
    )

    def execute(command: str, args: dict[str, object]) -> dict[str, object]:
        del args
        if command == "media.play_pause":
            media_controller.play_pause()
            return {"ok": True, "message": "Media playback toggled."}
        if command == "media.previous_track":
            media_controller.previous_track()
            return {"ok": True, "message": "Switched to previous media track."}
        if command == "media.next_track":
            media_controller.next_track()
            return {"ok": True, "message": "Switched to next media track."}
        return {"ok": False, "message": f"Unknown command: {command}"}

    return ExecutableSkill(spec=spec, execute=execute)
