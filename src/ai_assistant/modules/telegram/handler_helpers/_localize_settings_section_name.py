from __future__ import annotations

import asyncio

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest

from ai_assistant.core.models import SettingChoiceOption, SettingDefinition
from ai_assistant.modules.telegram.handler_constants import (
    MPC_AUDIO_EN,
    MPC_AUDIO_NEXT,
    MPC_AUDIO_PREVIOUS,
    MPC_AUDIO_RU,
    MPC_SUBTITLE_EN,
    MPC_SUBTITLE_NEXT,
    MPC_SUBTITLE_PREVIOUS,
    MPC_SUBTITLE_RU,
    PLAYER_NEXT,
    PLAYER_OUTPUT_TOGGLE,
    PLAYER_PLAY_PAUSE,
    PLAYER_PREVIOUS,
    SETTINGS_HOME,
    START_COMMAND_HELP,
)
from ai_assistant.modules.telegram.handler_functions import (
    bool_to_storage_value,
    extract_model_provider,
    extract_model_provider_from_option,
    is_truthy_value,
    option_display_name,
)
from ai_assistant.modules.telegram.handler_types import (
    PendingTextSettingInput as _PendingTextSettingInput,
    VisibleSetting as _VisibleSetting,
)

def _localize_settings_section_name(self, section_name: str, locale: str) -> str:
    section_key = self._normalize_settings_section_key(section_name)
    if section_key == "assistant":
        return self._t("settings.section.assistant", locale=locale)
    if section_key == "general":
        return self._t("settings.section.general", locale=locale)
    stripped = section_name.strip()
    if stripped:
        return stripped
    return self._t("settings.section.default", locale=locale)

