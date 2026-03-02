from __future__ import annotations

from ai_assistant.core.interfaces import (
    AssistantCommandExecutor,
    MPCController,
    MediaController,
    OutputController,
)


class SystemAssistantCommandExecutor(AssistantCommandExecutor):
    def __init__(
        self,
        media_controller: MediaController | None = None,
        mpc_controller: MPCController | None = None,
        output_controller: OutputController | None = None,
    ) -> None:
        self._media_controller = media_controller
        self._mpc_controller = mpc_controller
        self._output_controller = output_controller

    def get_command_catalog(self) -> list[dict[str, object]]:
        commands: list[dict[str, object]] = []
        if self._media_controller:
            commands.extend(
                [
                    {
                        "command": "media.play_pause",
                        "description": "Toggle system media playback pause/play.",
                        "args": {},
                    },
                    {
                        "command": "media.previous_track",
                        "description": "Switch to previous system media track.",
                        "args": {},
                    },
                    {
                        "command": "media.next_track",
                        "description": "Switch to next system media track.",
                        "args": {},
                    },
                ]
            )
        if self._mpc_controller:
            commands.extend(
                [
                    {
                        "command": "mpc.audio_next",
                        "description": "Switch MPC-HC audio track to the next one.",
                        "args": {},
                    },
                    {
                        "command": "mpc.audio_previous",
                        "description": "Switch MPC-HC audio track to the previous one.",
                        "args": {},
                    },
                    {
                        "command": "mpc.subtitle_next",
                        "description": "Switch MPC-HC subtitle track to the next one.",
                        "args": {},
                    },
                    {
                        "command": "mpc.subtitle_previous",
                        "description": "Switch MPC-HC subtitle track to the previous one.",
                        "args": {},
                    },
                    {
                        "command": "mpc.audio_set_language",
                        "description": "Set MPC-HC audio track language.",
                        "args": {"language": "ru|en"},
                    },
                    {
                        "command": "mpc.subtitle_set_language",
                        "description": "Set MPC-HC subtitle track language.",
                        "args": {"language": "ru|en"},
                    },
                ]
            )
        if self._output_controller:
            commands.extend(
                [
                    {
                        "command": "output.enable",
                        "description": "Enable configured speakers/output route.",
                        "args": {},
                    },
                    {
                        "command": "output.disable",
                        "description": "Disable configured speakers/output route.",
                        "args": {},
                    },
                    {
                        "command": "output.toggle",
                        "description": "Toggle configured speakers/output route.",
                        "args": {},
                    },
                    {
                        "command": "output.status",
                        "description": "Get configured speakers/output route state.",
                        "args": {},
                    },
                ]
            )
        return commands

    def execute_command(self, command: str, args: dict[str, object]) -> dict[str, object]:
        if command.startswith("media.") and not self._media_controller:
            return {"ok": False, "message": "Media controller is unavailable."}
        if command.startswith("mpc.") and not self._mpc_controller:
            return {"ok": False, "message": "MPC controller is unavailable."}
        if command.startswith("output.") and not self._output_controller:
            return {"ok": False, "message": "Output controller is unavailable."}

        if command == "media.play_pause":
            self._media_controller.play_pause()  # type: ignore[union-attr]
            return {"ok": True, "message": "Media playback toggled."}
        if command == "media.previous_track":
            self._media_controller.previous_track()  # type: ignore[union-attr]
            return {"ok": True, "message": "Switched to previous media track."}
        if command == "media.next_track":
            self._media_controller.next_track()  # type: ignore[union-attr]
            return {"ok": True, "message": "Switched to next media track."}

        if command == "mpc.audio_next":
            ok = self._mpc_controller.audio_next()  # type: ignore[union-attr]
            return {
                "ok": ok,
                "message": "MPC audio switched to next track."
                if ok
                else "MPC audio next track failed.",
            }
        if command == "mpc.audio_previous":
            ok = self._mpc_controller.audio_previous()  # type: ignore[union-attr]
            return {
                "ok": ok,
                "message": "MPC audio switched to previous track."
                if ok
                else "MPC audio previous track failed.",
            }
        if command == "mpc.subtitle_next":
            ok = self._mpc_controller.subtitle_next()  # type: ignore[union-attr]
            return {
                "ok": ok,
                "message": "MPC subtitles switched to next track."
                if ok
                else "MPC subtitles next track failed.",
            }
        if command == "mpc.subtitle_previous":
            ok = self._mpc_controller.subtitle_previous()  # type: ignore[union-attr]
            return {
                "ok": ok,
                "message": "MPC subtitles switched to previous track."
                if ok
                else "MPC subtitles previous track failed.",
            }
        if command == "mpc.audio_set_language":
            language = str(args.get("language", "")).lower().strip()
            if language not in {"ru", "en"}:
                return {"ok": False, "message": "language must be ru or en"}
            ok = self._mpc_controller.audio_set_language(language)  # type: ignore[union-attr]
            return {
                "ok": ok,
                "message": f"MPC audio language set to {language}."
                if ok
                else f"MPC audio language {language} not available.",
            }
        if command == "mpc.subtitle_set_language":
            language = str(args.get("language", "")).lower().strip()
            if language not in {"ru", "en"}:
                return {"ok": False, "message": "language must be ru or en"}
            ok = self._mpc_controller.subtitle_set_language(language)  # type: ignore[union-attr]
            return {
                "ok": ok,
                "message": f"MPC subtitle language set to {language}."
                if ok
                else f"MPC subtitle language {language} not available.",
            }

        if command == "output.enable":
            enabled = self._output_controller.enable_output()  # type: ignore[union-attr]
            return {"ok": enabled, "message": f"Output enabled: {enabled}"}
        if command == "output.disable":
            enabled = self._output_controller.disable_output()  # type: ignore[union-attr]
            return {"ok": not enabled, "message": f"Output enabled: {enabled}"}
        if command == "output.toggle":
            enabled = self._output_controller.toggle_output()  # type: ignore[union-attr]
            return {"ok": True, "message": f"Output enabled: {enabled}"}
        if command == "output.status":
            enabled = self._output_controller.is_output_enabled()  # type: ignore[union-attr]
            return {"ok": True, "message": f"Output enabled: {enabled}"}

        return {"ok": False, "message": f"Unknown command: {command}"}
