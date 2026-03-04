from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from ai_assistant.providers.remote.remote_device_service import AccessDeniedError, RemoteDeviceError


async def handle_pc_default(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await self._reject_if_not_allowed(update):
        return
    if await self._reject_if_no_message_permission(update, "general", "usage"):
        return
    if await self._reject_if_no_message_permission(update, "command", "pc_default"):
        return
    if not update.effective_message or not update.effective_user:
        return

    if self._remote_device_service is None:
        await update.effective_message.reply_text("Remote device service is unavailable.")
        return

    if len(context.args) < 1:
        await update.effective_message.reply_text("Usage: /pc_default <client_id|none>")
        return

    raw_value = context.args[0].strip()
    client_id = None if raw_value.lower() in {"none", "off", "clear"} else raw_value

    try:
        await self._remote_device_service.set_default_client(
            user_id=update.effective_user.id,
            client_id=client_id,
        )
    except AccessDeniedError:
        await update.effective_message.reply_text("No access to this client.")
        return
    except RemoteDeviceError as exc:
        await update.effective_message.reply_text(f"Default client update failed: {exc}")
        return
    except Exception as exc:
        await update.effective_message.reply_text(f"Default client update failed: {exc}")
        return

    if client_id is None:
        await update.effective_message.reply_text("Default device cleared.")
    else:
        await update.effective_message.reply_text(f"Default device set to: {client_id}")
