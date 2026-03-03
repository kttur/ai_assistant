from __future__ import annotations

from dataclasses import dataclass

from ai_assistant.core.models import SettingChoiceOption


@dataclass(slots=True, frozen=True)
class VisibleSetting:
    key: str
    value_type: str
    section: str
    title: str
    description: str
    current_value: str | None
    can_write: bool
    options: tuple[SettingChoiceOption, ...]


@dataclass(slots=True, frozen=True)
class PendingTextSettingInput:
    setting_key: str
