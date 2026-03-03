from __future__ import annotations

from ai_assistant.core.models import SettingChoiceOption


def option_display_name(option: SettingChoiceOption) -> str:
    return option.display_name or option.name
