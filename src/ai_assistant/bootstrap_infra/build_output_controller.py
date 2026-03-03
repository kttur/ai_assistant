from __future__ import annotations

from ai_assistant.config.settings import Settings
from ai_assistant.core.interfaces import OutputController
from ai_assistant.providers.system.voicemeeter_output_controller import VoicemeeterOutputController


def build_output_controller(settings: Settings) -> OutputController | None:
    backend = settings.audio_output_backend.lower().strip()
    if backend in {"", "none"}:
        return None
    if backend == "voicemeeter":
        return VoicemeeterOutputController(
            strip_index=settings.voicemeeter_strip_index,
            bus=settings.voicemeeter_bus,
            output_param=settings.voicemeeter_output_param,
            remote_dll_path=settings.voicemeeter_remote_dll_path,
        )
    raise ValueError(f"Unsupported audio output backend: {settings.audio_output_backend}")
