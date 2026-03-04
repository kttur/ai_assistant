from __future__ import annotations

import json

from telegram import Update
from telegram.ext import ContextTypes

from ai_assistant.providers.remote.remote_device_service import AccessDeniedError


async def handle_pc_run(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await self._reject_if_not_allowed(update):
        return
    if await self._reject_if_no_message_permission(update, "general", "usage"):
        return
    if await self._reject_if_no_message_permission(update, "command", "pc_run"):
        return
    if not update.effective_message or not update.effective_user:
        return

    if self._remote_ws_hub is None:
        await update.effective_message.reply_text("Remote runtime is unavailable.")
        return

    if len(context.args) < 1:
        await update.effective_message.reply_text(
            "Usage: /pc_run <command> [args_json]\n"
            'Examples:\n- /pc_run media.play_pause\n- /pc_run mpc.audio_set_language {"language":"ru"}\n- /pc_run media.play_pause {"client_id":"pc-1"}'
        )
        return

    command = context.args[0].strip().lower()
    raw_args_json = " ".join(context.args[1:]).strip()
    args: dict[str, object] = {}
    if raw_args_json:
        try:
            parsed = json.loads(raw_args_json)
        except json.JSONDecodeError:
            await update.effective_message.reply_text("args_json must be a valid JSON object.")
            return
        if not isinstance(parsed, dict):
            await update.effective_message.reply_text("args_json must be a JSON object.")
            return
        args = parsed

    try:
        result = await self._remote_ws_hub.execute_user_remote_command(
            user_id=update.effective_user.id,
            command=command,
            args=args,
        )
    except AccessDeniedError:
        await update.effective_message.reply_text("No access to this client.")
        return
    except Exception as exc:
        await update.effective_message.reply_text(f"Remote command failed: {exc}")
        return

    await update.effective_message.reply_text(
        "Remote command result:\n" + json.dumps(result, ensure_ascii=False, indent=2)
    )
