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

async def _handle_terminal_command(
    self,
    update: Update,
    command: str,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not update.effective_message:
        return
    if not self._terminal_executor:
        await update.effective_message.reply_text("Терминал недоступен.")
        return

    bot = getattr(context, "bot", None)
    chat = getattr(update, "effective_chat", None)
    if bot is not None and chat is not None:
        try:
            await bot.send_chat_action(chat_id=chat.id, action=ChatAction.TYPING)
        except Exception:
            pass

    result = await self._terminal_executor.run_command(update.effective_user.id, command)
    for chunk in format_terminal_result_chunks(result):
        await update.effective_message.reply_text(chunk)


