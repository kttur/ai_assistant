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
    split_telegram_text_chunks,
)

logger = logging.getLogger(__name__)
TELEGRAM_TEXT_LIMIT = 4096


async def _send_llm_reply(self, update: Update, text: str) -> None:
    if not update.effective_message:
        return
    chunks = split_telegram_text_chunks(text, max_chars=TELEGRAM_TEXT_LIMIT)
    logger.debug(
        "Sending Telegram reply: chars=%d chunks=%d limit=%d",
        len(text),
        len(chunks),
        TELEGRAM_TEXT_LIMIT,
    )

    for index, chunk in enumerate(chunks, start=1):
        try:
            await update.effective_message.reply_text(
                chunk,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        except BadRequest:
            # Fallback to plain text if this chunk contains invalid Telegram HTML.
            logger.warning(
                "Telegram HTML parse failed for chunk %d/%d, retrying plain text.",
                index,
                len(chunks),
            )
            await update.effective_message.reply_text(chunk)


