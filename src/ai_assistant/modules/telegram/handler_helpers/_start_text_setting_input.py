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

async def _start_text_setting_input(
    self,
    update: Update,
    section_index: int,
    setting_index: int,
    locale: str,
) -> bool:
    user = update.effective_user
    query = update.callback_query
    if user is None or query is None:
        return False
    setting = await self._resolve_setting_for_write(
        user_id=user.id,
        section_index=section_index,
        setting_index=setting_index,
        locale=locale,
    )
    if setting is None or setting.value_type != "text":
        return False
    self._pending_text_setting_inputs[user.id] = _PendingTextSettingInput(setting_key=setting.key)
    await self._answer_callback(
        query,
        self._t("settings.text_input.alert", locale=locale),
        show_alert=True,
    )
    if query.message:
        await query.message.reply_text(
            self._t("settings.text_input.prompt", locale=locale, key=setting.key),
            parse_mode=ParseMode.MARKDOWN,
        )
    return True

