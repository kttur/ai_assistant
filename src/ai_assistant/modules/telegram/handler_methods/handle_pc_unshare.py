from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from ai_assistant.providers.remote.remote_device_service import AccessDeniedError, OwnershipError, RemoteDeviceError


async def handle_pc_unshare(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await self._reject_if_not_allowed(update):
        return
    if await self._reject_if_no_message_permission(update, "general", "usage"):
        return
    if await self._reject_if_no_message_permission(update, "command", "pc_unshare"):
        return
    if not update.effective_message or not update.effective_user:
        return

    if self._remote_device_service is None:
        await update.effective_message.reply_text("Remote device service is unavailable.")
        return

    if len(context.args) < 2:
        await update.effective_message.reply_text("Usage: /pc_unshare <client_id> <telegram_user_id>")
        return

    client_id = context.args[0].strip()
    try:
        target_user_id = int(context.args[1].strip())
    except ValueError:
        await update.effective_message.reply_text("telegram_user_id must be integer.")
        return

    try:
        await self._remote_device_service.revoke_client_access(
            owner_user_id=update.effective_user.id,
            client_id=client_id,
            target_user_id=target_user_id,
        )
    except AccessDeniedError:
        await update.effective_message.reply_text("Owner access cannot be revoked.")
        return
    except OwnershipError:
        await update.effective_message.reply_text("Only owner can revoke access for this client.")
        return
    except RemoteDeviceError as exc:
        await update.effective_message.reply_text(f"Revoke failed: {exc}")
        return
    except Exception as exc:
        await update.effective_message.reply_text(f"Revoke failed: {exc}")
        return

    await update.effective_message.reply_text(
        f"Access revoked: client={client_id}, user={target_user_id}"
    )
