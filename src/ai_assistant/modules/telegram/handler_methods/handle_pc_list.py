from __future__ import annotations

from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes


def _format_last_seen(value: datetime | None) -> str:
    if value is None:
        return "never"
    return value.isoformat()


async def handle_pc_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    if await self._reject_if_not_allowed(update):
        return
    if await self._reject_if_no_message_permission(update, "general", "usage"):
        return
    if await self._reject_if_no_message_permission(update, "command", "pc_list"):
        return
    if not update.effective_message or not update.effective_user:
        return

    if self._remote_device_service is None:
        await update.effective_message.reply_text("Remote device service is unavailable.")
        return

    clients = await self._remote_device_service.list_user_clients(update.effective_user.id)
    if not clients:
        await update.effective_message.reply_text("No linked devices.")
        return

    lines = ["Your devices:"]
    for client in clients:
        ownership = "owner" if client.is_owner else "shared"
        default_marker = " [default]" if client.is_default else ""
        lines.append(
            f"- {client.client_id}{default_marker} | {client.display_name} | {client.platform} | {ownership} | last_seen={_format_last_seen(client.last_seen_at)}"
        )

    await update.effective_message.reply_text("\n".join(lines))
