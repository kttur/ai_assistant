from __future__ import annotations

import asyncio
import logging

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

logger = logging.getLogger(__name__)


async def handle_ask(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await self._reject_if_not_allowed(update):
        return
    if await self._reject_if_no_message_permission(update, "general", "usage"):
        return
    if await self._reject_if_no_message_permission(update, "command", "ask"):
        return
    if await self._reject_if_no_message_permission(update, "general", "assistant"):
        return
    if not update.effective_message or not update.effective_user:
        return

    incoming_text = update.effective_message.text or ""
    user_text = incoming_text.replace("/ask", "", 1).strip()
    if not user_text:
        await update.effective_message.reply_text("Использование: /ask <вопрос>")
        return
    logger.debug(
        "Telegram /ask command received: user_id=%s text_chars=%d",
        update.effective_user.id,
        len(user_text),
    )

    await self._reply_with_llm(
        user_id=update.effective_user.id,
        user_text=user_text,
        update=update,
        context=context,
    )


