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

async def _edit_setting_page_message(
    self,
    query,
    user_id: int,
    section_index: int,
    setting_index: int,
    locale: str,
) -> None:
    resolved = await self._resolve_setting_page(
        user_id=user_id,
        section_index=section_index,
        setting_index=setting_index,
        locale=locale,
    )
    if resolved is None:
        await self._answer_callback(
            query,
            self._t("settings.callback.list_changed", locale=locale),
            show_alert=True,
        )
        return
    text, markup = resolved
    try:
        await query.edit_message_text(text=text, reply_markup=markup)
    except BadRequest:
        pass

