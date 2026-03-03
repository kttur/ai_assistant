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

def _settings_setting_keyboard(
    self,
    setting: _VisibleSetting,
    section_index: int,
    setting_index: int,
    total_settings: int,
    locale: str,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if setting.can_write:
        if setting.value_type == "bool":
            enabled = is_truthy_value(setting.current_value)
            icon = "✅" if enabled else "❌"
            state = "ON" if enabled else "OFF"
            rows.append(
                [
                    InlineKeyboardButton(
                        f"{icon} {state}",
                        callback_data=f"settings:toggle:{section_index}:{setting_index}",
                    )
                ]
            )
        elif setting.value_type == "choice":
            for option_index, option in enumerate(setting.options):
                mark = "✅ " if option.name == (setting.current_value or "") else ""
                rows.append(
                    [
                        InlineKeyboardButton(
                            f"{mark}{option_display_name(option)}",
                            callback_data=(
                                f"settings:choice:{section_index}:{setting_index}:{option_index}"
                            ),
                        )
                    ]
                )
        elif setting.value_type == "text":
            text_row = [
                InlineKeyboardButton(
                    f"✍️ {self._t('settings.nav.enter_value', locale=locale)}",
                    callback_data=f"settings:text:{section_index}:{setting_index}",
                )
            ]
            if setting.current_value is not None and setting.current_value != "":
                text_row.append(
                    InlineKeyboardButton(
                        f"🗑 {self._t('settings.nav.clear', locale=locale)}",
                        callback_data=f"settings:text_clear:{section_index}:{setting_index}",
                    )
                )
            rows.append(text_row)

    rows.append(self._settings_nav_row(section_index, setting_index, total_settings, locale=locale))
    return InlineKeyboardMarkup(rows)

