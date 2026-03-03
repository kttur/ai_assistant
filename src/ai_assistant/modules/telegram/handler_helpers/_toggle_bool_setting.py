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

async def _toggle_bool_setting(
    self,
    user_id: int,
    section_index: int,
    setting_index: int,
    locale: str,
) -> str | None:
    resolved = await self._resolve_setting_for_write(
        user_id,
        section_index,
        setting_index,
        locale=locale,
    )
    if resolved is None:
        return None
    setting = resolved
    if setting.value_type != "bool":
        return None
    current = is_truthy_value(setting.current_value)
    new_value = bool_to_storage_value(not current)
    if not self._user_settings_store:
        return None
    await self._user_settings_store.set_setting(user_id=user_id, key=setting.key, value=new_value)
    return new_value

