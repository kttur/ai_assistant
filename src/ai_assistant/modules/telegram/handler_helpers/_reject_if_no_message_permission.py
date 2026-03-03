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

async def _reject_if_no_message_permission(
    self,
    update: Update,
    permission_type: str,
    name: str,
) -> bool:
    user = update.effective_user
    if not user:
        return True
    if await self._has_permission(
        user_id=user.id,
        permission_type=permission_type,
        name=name,
    ):
        return False
    locale = await self._resolve_user_locale(user.id)
    if update.effective_message:
        await update.effective_message.reply_text(
            self._t(
                "errors.permission_denied",
                locale=locale,
                permission=f"{permission_type}/{name}",
            )
        )
    return True

