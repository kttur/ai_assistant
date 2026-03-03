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

async def handle_settings_raw(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    if await self._reject_if_not_allowed(update):
        return
    if await self._reject_if_no_message_permission(update, "general", "usage"):
        return
    if await self._reject_if_no_message_permission(update, "command", "settings_raw"):
        return
    if not update.effective_message or not update.effective_user:
        return
    locale = await self._resolve_user_locale(update.effective_user.id)
    if not self._user_settings_store:
        await update.effective_message.reply_text(
            self._t("errors.settings_store_unconfigured", locale=locale)
        )
        return

    settings_map = await self._user_settings_store.get_all_settings(update.effective_user.id)
    if not settings_map:
        await update.effective_message.reply_text(self._t("settings_raw.empty", locale=locale))
        return

    lines = [self._t("settings_raw.header", locale=locale)]
    for key, value in sorted(settings_map.items()):
        lines.append(f"- {key}: {value}")
    await update.effective_message.reply_text("\n".join(lines))


