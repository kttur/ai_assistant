from __future__ import annotations

import asyncio

from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

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
    VALID_PERMISSION_TYPES,
)
from ai_assistant.modules.telegram.handler_functions import (
    format_terminal_result_chunks,
    has_forward_metadata,
    is_truthy_value,
    normalize_permission_type,
    option_display_name,
    render_contact_section,
    render_forward_origin_section,
    render_user_section,
)

async def handle_set_setting(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await self._reject_if_not_allowed(update):
        return
    if await self._reject_if_no_message_permission(update, "general", "usage"):
        return
    if await self._reject_if_no_message_permission(update, "command", "set"):
        return
    if not update.effective_message or not update.effective_user:
        return
    locale = await self._resolve_user_locale(update.effective_user.id)
    if not self._user_settings_store:
        await update.effective_message.reply_text(
            self._t("errors.settings_store_unconfigured", locale=locale)
        )
        return
    if len(context.args) < 2:
        await update.effective_message.reply_text(self._t("set.usage", locale=locale))
        return

    key = context.args[0].strip().lower()
    value = " ".join(context.args[1:]).strip()
    if not key or not value:
        await update.effective_message.reply_text(self._t("set.usage", locale=locale))
        return

    await self._user_settings_store.set_setting(
        user_id=update.effective_user.id,
        key=key,
        value=value,
    )
    await update.effective_message.reply_text(
        self._t("set.saved", locale=locale, key=key, value=value)
    )


