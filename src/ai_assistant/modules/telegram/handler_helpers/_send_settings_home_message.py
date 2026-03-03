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

async def _send_settings_home_message(self, update: Update) -> None:
    if not update.effective_message or not update.effective_user:
        return
    locale = await self._resolve_user_locale(update.effective_user.id)
    if not self._user_settings_store:
        await update.effective_message.reply_text(
            self._t("errors.settings_store_unconfigured", locale=locale)
        )
        return

    sections = await self._get_visible_settings_sections(
        user_id=update.effective_user.id,
        ui_only=True,
        locale=locale,
    )
    text = self._render_settings_home_text(sections, locale=locale)
    markup = self._settings_home_keyboard(sections)
    await update.effective_message.reply_text(text, reply_markup=markup)

