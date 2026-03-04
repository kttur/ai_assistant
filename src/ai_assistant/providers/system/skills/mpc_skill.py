from __future__ import annotations

from ai_assistant.core.interfaces import MPCController
from ai_assistant.skills.models import ExecutableSkill, SkillCommandSpec, SkillSpec


SUPPORTED_LANGUAGES = {"ru", "en"}


def build_mpc_skill(mpc_controller: MPCController | None) -> ExecutableSkill | None:
    if mpc_controller is None:
        return None

    spec = SkillSpec(
        skill_id="mpc",
        title="MPC-HC track control",
        llm_description=(
            "Control MPC-HC audio/subtitle tracks, including next/previous and language switching."
        ),
        commands=(
            SkillCommandSpec(
                command="mpc.audio_next",
                description="Switch MPC-HC audio track to the next one.",
            ),
            SkillCommandSpec(
                command="mpc.audio_previous",
                description="Switch MPC-HC audio track to the previous one.",
            ),
            SkillCommandSpec(
                command="mpc.subtitle_next",
                description="Switch MPC-HC subtitle track to the next one.",
            ),
            SkillCommandSpec(
                command="mpc.subtitle_previous",
                description="Switch MPC-HC subtitle track to the previous one.",
            ),
            SkillCommandSpec(
                command="mpc.audio_set_language",
                description="Set MPC-HC audio track language.",
                args={"language": "ru|en"},
            ),
            SkillCommandSpec(
                command="mpc.subtitle_set_language",
                description="Set MPC-HC subtitle track language.",
                args={"language": "ru|en"},
            ),
        ),
    )

    def execute(command: str, args: dict[str, object]) -> dict[str, object]:
        if command == "mpc.audio_next":
            ok = mpc_controller.audio_next()
            return {
                "ok": ok,
                "message": "MPC audio switched to next track."
                if ok
                else "MPC audio next track failed.",
            }
        if command == "mpc.audio_previous":
            ok = mpc_controller.audio_previous()
            return {
                "ok": ok,
                "message": "MPC audio switched to previous track."
                if ok
                else "MPC audio previous track failed.",
            }
        if command == "mpc.subtitle_next":
            ok = mpc_controller.subtitle_next()
            return {
                "ok": ok,
                "message": "MPC subtitles switched to next track."
                if ok
                else "MPC subtitles next track failed.",
            }
        if command == "mpc.subtitle_previous":
            ok = mpc_controller.subtitle_previous()
            return {
                "ok": ok,
                "message": "MPC subtitles switched to previous track."
                if ok
                else "MPC subtitles previous track failed.",
            }

        if command in {"mpc.audio_set_language", "mpc.subtitle_set_language"}:
            language = str(args.get("language", "")).strip().lower()
            if language not in SUPPORTED_LANGUAGES:
                return {"ok": False, "message": "language must be ru or en"}

            if command == "mpc.audio_set_language":
                ok = mpc_controller.audio_set_language(language)
                return {
                    "ok": ok,
                    "message": f"MPC audio language set to {language}."
                    if ok
                    else f"MPC audio language {language} not available.",
                }

            ok = mpc_controller.subtitle_set_language(language)
            return {
                "ok": ok,
                "message": f"MPC subtitle language set to {language}."
                if ok
                else f"MPC subtitle language {language} not available.",
            }

        return {"ok": False, "message": f"Unknown command: {command}"}

    return ExecutableSkill(spec=spec, execute=execute)
