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

def _settings_nav_row(
    self,
    section_index: int,
    setting_index: int,
    total_settings: int,
    locale: str,
) -> list[InlineKeyboardButton]:
    row: list[InlineKeyboardButton] = []
    if setting_index > 0:
        row.append(
            InlineKeyboardButton(
                "⬅",
                callback_data=f"settings:view:{section_index}:{setting_index - 1}",
            )
        )
    row.append(
        InlineKeyboardButton(
            self._t("settings.nav.sections", locale=locale),
            callback_data=SETTINGS_HOME,
        )
    )
    if setting_index < total_settings - 1:
        row.append(
            InlineKeyboardButton(
                "➡",
                callback_data=f"settings:view:{section_index}:{setting_index + 1}",
            )
        )
    return row

