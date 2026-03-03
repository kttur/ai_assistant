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

async def _handle_pending_text_setting_input(
    self,
    update: Update,
    user_id: int,
    new_value: str,
) -> bool:
    pending = self._pending_text_setting_inputs.get(user_id)
    if pending is None:
        return False
    locale = await self._resolve_user_locale(user_id)
    if not self._user_settings_store or not update.effective_message:
        self._pending_text_setting_inputs.pop(user_id, None)
        return True

    definitions = await self._user_settings_store.get_setting_definitions(locale=locale)
    target_definition: SettingDefinition | None = None
    for item in definitions:
        if item.key == pending.setting_key:
            target_definition = item
            break

    if target_definition is None or target_definition.value_type != "text":
        self._pending_text_setting_inputs.pop(user_id, None)
        await update.effective_message.reply_text(
            self._t("settings.text_input.unavailable", locale=locale)
        )
        return True

    can_write = await self._has_optional_permission(
        user_id,
        target_definition.write_permission_type,
        target_definition.write_permission_name,
    )
    if not can_write:
        self._pending_text_setting_inputs.pop(user_id, None)
        await update.effective_message.reply_text(
            self._t("settings.text_input.no_permission", locale=locale)
        )
        return True

    await self._user_settings_store.set_setting(
        user_id=user_id,
        key=pending.setting_key,
        value=new_value,
    )
    self._pending_text_setting_inputs.pop(user_id, None)
    await update.effective_message.reply_text(
        self._t(
            "settings.text_input.saved",
            locale=locale,
            key=pending.setting_key,
            value=new_value,
        )
    )
    return True

