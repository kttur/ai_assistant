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

async def handle_user_permissions(
    self, update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if await self._reject_if_not_allowed(update):
        return
    if await self._reject_if_no_message_permission(update, "general", "usage"):
        return
    if await self._reject_if_no_message_permission(update, "command", "user_permissions"):
        return
    if not update.effective_message:
        return
    if await self._reject_if_permission_admin_unavailable(update):
        return
    admin = self._permission_admin
    if admin is None:
        return
    if len(context.args) != 1:
        await update.effective_message.reply_text(
            "Использование: /user_permissions <user_id>"
        )
        return
    try:
        target_user_id = int(context.args[0].strip())
    except ValueError:
        await update.effective_message.reply_text("user_id должен быть целым числом.")
        return

    try:
        report = await admin.get_user_permission_report(target_user_id)
    except Exception as exc:
        await update.effective_message.reply_text(f"Ошибка user_permissions: {exc}")
        return

    user_overrides = list(report.get("user_overrides", []))
    role_permissions = list(report.get("role_permissions", []))
    effective = list(report.get("effective", []))

    lines = [f"user={target_user_id} permissions:"]
    lines.append("user_overrides:")
    if user_overrides:
        for item in user_overrides:
            lines.append(
                f"- {item.get('type')}/{item.get('name')} = {item.get('is_active')}"
            )
    else:
        lines.append("- (none)")

    lines.append("role_permissions:")
    if role_permissions:
        for item in role_permissions:
            lines.append(
                f"- role={item.get('role')}: {item.get('type')}/{item.get('name')}"
            )
    else:
        lines.append("- (none)")

    lines.append("effective:")
    if effective:
        for item in effective:
            lines.append(
                f"- {item.get('type')}/{item.get('name')} = {item.get('is_active')} "
                f"(source={item.get('source')}, roles={','.join(item.get('roles', []))})"
            )
    else:
        lines.append("- (none)")

    await update.effective_message.reply_text("\n".join(lines))


