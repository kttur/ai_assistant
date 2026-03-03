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

async def handle_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    if await self._reject_if_not_allowed(update):
        return
    if await self._reject_if_no_message_permission(update, "general", "usage"):
        return
    if await self._reject_if_no_message_permission(update, "command", "id"):
        return
    if not update.effective_message or not update.effective_user:
        return

    message = update.effective_message
    replied = getattr(message, "reply_to_message", None)
    if replied:
        sections: list[str] = []
        replied_from = getattr(replied, "from_user", None)
        replied_contact = getattr(replied, "contact", None)
        has_forward = has_forward_metadata(replied)

        if replied_from is not None:
            if has_forward:
                sections.append(render_user_section("Forwarded by:", replied_from))
            elif replied_contact is not None:
                sections.append(render_user_section("Contact sent by:", replied_from))
            else:
                sections.append(render_user_section("Reply sender:", replied_from))

        forward_section = render_forward_origin_section(replied)
        if forward_section:
            sections.append(forward_section)

        if replied_contact is not None:
            sections.append(render_contact_section(replied_contact))

        if sections:
            await message.reply_text("\n\n".join(sections))
            return

    user = update.effective_user
    await message.reply_text(render_user_section("Your account:", user))


