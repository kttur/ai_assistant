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

async def handle_user_roles(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await self._reject_if_not_allowed(update):
        return
    if await self._reject_if_no_message_permission(update, "general", "usage"):
        return
    if await self._reject_if_no_message_permission(update, "command", "user_roles"):
        return
    if not update.effective_message:
        return
    if await self._reject_if_permission_admin_unavailable(update):
        return
    admin = self._permission_admin
    if admin is None:
        return
    if len(context.args) != 1:
        await update.effective_message.reply_text("Использование: /user_roles <user_id>")
        return
    try:
        target_user_id = int(context.args[0].strip())
    except ValueError:
        await update.effective_message.reply_text("user_id должен быть целым числом.")
        return

    try:
        roles = await admin.get_user_roles(target_user_id)
    except Exception as exc:
        await update.effective_message.reply_text(f"Ошибка user_roles: {exc}")
        return

    if not roles:
        await update.effective_message.reply_text(
            f"user={target_user_id}: роли не назначены."
        )
        return
    lines = [f"user={target_user_id} roles:"]
    for role in roles:
        lines.append(f"- {role}")
    await update.effective_message.reply_text("\n".join(lines))


