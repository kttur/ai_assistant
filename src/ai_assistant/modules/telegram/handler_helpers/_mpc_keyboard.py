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
    MPC_FULLSCREEN_OFF,
    MPC_FULLSCREEN_ON,
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


def _mpc_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Аудио ⬅", callback_data=MPC_AUDIO_PREVIOUS),
                InlineKeyboardButton("Аудио ➡", callback_data=MPC_AUDIO_NEXT),
            ],
            [
                InlineKeyboardButton("Сабы ⬅", callback_data=MPC_SUBTITLE_PREVIOUS),
                InlineKeyboardButton("Сабы ➡", callback_data=MPC_SUBTITLE_NEXT),
            ],
            [
                InlineKeyboardButton("Аудио RU", callback_data=MPC_AUDIO_RU),
                InlineKeyboardButton("Аудио EN", callback_data=MPC_AUDIO_EN),
            ],
            [
                InlineKeyboardButton("Сабы RU", callback_data=MPC_SUBTITLE_RU),
                InlineKeyboardButton("Сабы EN", callback_data=MPC_SUBTITLE_EN),
            ],
            [
                InlineKeyboardButton("Full ON", callback_data=MPC_FULLSCREEN_ON),
                InlineKeyboardButton("Full OFF", callback_data=MPC_FULLSCREEN_OFF),
            ],
        ]
    )

