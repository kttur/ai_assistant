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

async def handle_grant(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await self._reject_if_not_allowed(update):
        return
    if await self._reject_if_no_message_permission(update, "general", "usage"):
        return
    if await self._reject_if_no_message_permission(update, "command", "grant"):
        return
    if not update.effective_message:
        return
    if await self._reject_if_permission_admin_unavailable(update):
        return
    admin = self._permission_admin
    if admin is None:
        return
    if len(context.args) < 4:
        await update.effective_message.reply_text(
            "Использование: /grant user <user_id> <type> <name> | /grant role <role_name> <type> <name>"
        )
        return

    target_kind = context.args[0].strip().lower()
    permission_type = normalize_permission_type(context.args[2], VALID_PERMISSION_TYPES)
    permission_name = " ".join(context.args[3:]).strip().lower()
    if permission_type is None:
        await update.effective_message.reply_text(
            "type должен быть одним из: general, command, assistant."
        )
        return
    if not permission_name:
        await update.effective_message.reply_text("name не должен быть пустым.")
        return

    try:
        if target_kind == "user":
            target_user_id = int(context.args[1].strip())
            await admin.set_user_permission(
                user_id=target_user_id,
                permission_type=permission_type,
                name=permission_name,
                is_active=True,
            )
            await update.effective_message.reply_text(
                f"Granted user permission: user={target_user_id}, {permission_type}/{permission_name}"
            )
            return

        if target_kind == "role":
            role_name = context.args[1].strip().lower()
            if not role_name:
                await update.effective_message.reply_text("role_name не должен быть пустым.")
                return
            await admin.grant_role_permission(
                role_name=role_name,
                permission_type=permission_type,
                name=permission_name,
            )
            await update.effective_message.reply_text(
                f"Granted role permission: role={role_name}, {permission_type}/{permission_name}"
            )
            return
    except ValueError:
        await update.effective_message.reply_text("user_id должен быть целым числом.")
        return
    except Exception as exc:
        await update.effective_message.reply_text(f"Ошибка grant: {exc}")
        return

    await update.effective_message.reply_text(
        "Первый аргумент должен быть user или role."
    )


