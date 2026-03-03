from __future__ import annotations

from ai_assistant.core.interfaces import MediaController
from ai_assistant.providers.system.media_controller import WindowsMediaController


def build_media_controller() -> MediaController | None:
    try:
        return WindowsMediaController()
    except RuntimeError:
        return None
