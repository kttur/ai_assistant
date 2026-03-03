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

async def _resolve_setting_page(
    self,
    user_id: int,
    section_index: int,
    setting_index: int,
    locale: str,
) -> tuple[str, InlineKeyboardMarkup] | None:
    sections = await self._get_visible_settings_sections(
        user_id=user_id,
        ui_only=True,
        locale=locale,
    )
    if section_index < 0 or section_index >= len(sections):
        return None
    _, settings_list = sections[section_index]
    if setting_index < 0 or setting_index >= len(settings_list):
        return None
    setting = settings_list[setting_index]
    text = self._render_setting_text(
        setting=setting,
        setting_index=setting_index,
        total_settings=len(settings_list),
        locale=locale,
    )
    markup = self._settings_setting_keyboard(
        setting=setting,
        section_index=section_index,
        setting_index=setting_index,
        total_settings=len(settings_list),
        locale=locale,
    )
    return text, markup

