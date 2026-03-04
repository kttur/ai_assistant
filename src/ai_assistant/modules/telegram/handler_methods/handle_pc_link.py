from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from ai_assistant.providers.remote.remote_device_service import (
    LinkCodeNotFoundError,
    OwnershipError,
    RemoteDeviceError,
)


async def handle_pc_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await self._reject_if_not_allowed(update):
        return
    if await self._reject_if_no_message_permission(update, "general", "usage"):
        return
    if await self._reject_if_no_message_permission(update, "command", "pc_link"):
        return
    if not update.effective_message or not update.effective_user:
        return

    if self._remote_ws_hub is None:
        await update.effective_message.reply_text("Remote link runtime is unavailable.")
        return

    if len(context.args) < 1:
        await update.effective_message.reply_text("Usage: /pc_link <one_time_code>")
        return

    code = context.args[0]
    try:
        result = await self._remote_ws_hub.complete_link_code(
            user_id=update.effective_user.id,
            code=code,
        )
    except LinkCodeNotFoundError:
        await update.effective_message.reply_text("Invalid or expired link code.")
        return
    except OwnershipError:
        await update.effective_message.reply_text(
            "This device is already linked to a different owner."
        )
        return
    except RemoteDeviceError as exc:
        await update.effective_message.reply_text(f"Link failed: {exc}")
        return
    except Exception as exc:
        await update.effective_message.reply_text(f"Link failed: {exc}")
        return

    default_suffix = " (set as default)" if result.default_assigned else ""
    await update.effective_message.reply_text(
        "Linked device successfully:\n"
        f"- client_id: {result.client.client_id}\n"
        f"- name: {result.client.display_name}\n"
        f"- platform: {result.client.platform}{default_suffix}"
    )
