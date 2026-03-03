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

async def handle_terminal_mode(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    if await self._reject_if_not_allowed(update):
        return
    if await self._reject_if_no_message_permission(update, "general", "usage"):
        return
    if await self._reject_if_no_message_permission(update, "command", "terminal"):
        return
    if not update.effective_message or not update.effective_user:
        return

    if not self._terminal_executor:
        await update.effective_message.reply_text("Терминал недоступен в текущем окружении.")
        return

    user_id = update.effective_user.id
    try:
        await self._terminal_executor.start_session(user_id)
    except Exception as exc:
        await update.effective_message.reply_text(f"Не удалось запустить терминал: {exc}")
        return
    self._terminal_mode_users.add(user_id)
    shell = self._terminal_executor.describe_shell()
    await update.effective_message.reply_text(
        f"Terminal mode ON ({shell}). Отправляй команды как обычные сообщения. /exit для выхода."
    )


