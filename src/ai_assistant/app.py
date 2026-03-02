from __future__ import annotations

from ai_assistant.bootstrap import build_channel_module
from ai_assistant.config.settings import Settings


def run() -> None:
    settings = Settings.from_env()
    module = build_channel_module(settings)
    module.run()

