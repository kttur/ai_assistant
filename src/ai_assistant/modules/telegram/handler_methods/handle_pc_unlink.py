from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from ai_assistant.providers.remote.remote_device_service import OwnershipError, RemoteDeviceError


async def handle_pc_unlink(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await self._reject_if_not_allowed(update):
        return
    if await self._reject_if_no_message_permission(update, "general", "usage"):
        return
    if await self._reject_if_no_message_permission(update, "command", "pc_unlink"):
        return
    if not update.effective_message or not update.effective_user:
        return

    if self._remote_device_service is None:
        await update.effective_message.reply_text("Remote device service is unavailable.")
        return

    if len(context.args) < 1:
        await update.effective_message.reply_text("Usage: /pc_unlink <client_id>")
        return

    client_id = context.args[0].strip()

    if self._remote_ws_hub is not None:
        try:
            await self._remote_ws_hub.execute_client_command(
                user_id=update.effective_user.id,
                client_id=client_id,
                command="client.unlink_server",
                args={},
                wait_for_response=False,
            )
        except Exception:
            pass

    try:
        await self._remote_device_service.unlink_client(
            owner_user_id=update.effective_user.id,
            client_id=client_id,
        )
    except OwnershipError:
        await update.effective_message.reply_text("Only owner can unlink this client.")
        return
    except RemoteDeviceError as exc:
        await update.effective_message.reply_text(f"Unlink failed: {exc}")
        return
    except Exception as exc:
        await update.effective_message.reply_text(f"Unlink failed: {exc}")
        return

    await update.effective_message.reply_text(f"Client unlinked: {client_id}")
