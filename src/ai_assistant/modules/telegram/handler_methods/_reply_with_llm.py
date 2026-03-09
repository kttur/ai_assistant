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


async def _reply_with_llm(
    self,
    user_id: int,
    user_text: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not update.effective_message:
        return

    logger.info("Telegram LLM request started: user_id=%s", user_id)
    typing_task: asyncio.Task | None = None
    bot = getattr(context, "bot", None)
    chat = getattr(update, "effective_chat", None)
    chat_id = chat.id if chat else None
    if bot is not None and chat_id is not None:
        try:
            await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            typing_task = asyncio.create_task(
                self._typing_heartbeat(bot=bot, chat_id=chat_id)
            )
        except Exception:
            logger.debug(
                "Unable to start typing heartbeat: user_id=%s chat_id=%s",
                user_id,
                chat_id,
            )
            typing_task = None

    try:
        reply = await self._assistant_service.process_text(user_id=user_id, text=user_text)
    except Exception as exc:
        logger.exception("Telegram LLM request failed: user_id=%s error=%s", user_id, exc)
        await update.effective_message.reply_text(f"Ошибка LLM: {exc}")
        return
    finally:
        if typing_task:
            typing_task.cancel()
            try:
                await typing_task
            except asyncio.CancelledError:
                pass

    logger.info("Telegram LLM request completed: user_id=%s reply_chars=%d", user_id, len(reply.text))
    await self._send_llm_reply(
        update=update,
        text=reply.text,
        documents=getattr(reply, "documents", ()),
    )


