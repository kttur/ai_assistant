from __future__ import annotations

import base64
import binascii
from io import BytesIO
import json

from telegram import InputFile, Update
from telegram.ext import ContextTypes

from ai_assistant.providers.remote.remote_device_service import AccessDeniedError


_FILESYSTEM_PERMISSION_BY_COMMAND = {
    "filesystem.list_directory": "remote.filesystem.list_directory",
    "filesystem.search_files": "remote.filesystem.list_directory",
    "filesystem.file_info": "remote.filesystem.read_file",
    "filesystem.read_file": "remote.filesystem.read_file",
    "filesystem.send_file": "remote.filesystem.read_file",
    "filesystem.write_file": "remote.filesystem.write_file",
}


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
            "Examples:\n"
            "- /pc_run media.play_pause\n"
            '- /pc_run mpc.audio_set_language {"language":"ru"}\n'
            '- /pc_run filesystem.list_directory {"path":"C:\\\\Users\\\\Public"}\n'
            '- /pc_run filesystem.search_files {"query":"*.mkv","path":"D:\\\\Media","max_items":50}\n'
            '- /pc_run filesystem.send_file {"path":"C:\\\\tmp\\\\report.pdf"}\n'
            '- /pc_run filesystem.write_file {"path":"C:\\\\tmp\\\\note.txt","content":"hello","append":false,"send_to_telegram":true}'
        )
        return

    command = context.args[0].strip().lower()
    required_assistant_permission = _FILESYSTEM_PERMISSION_BY_COMMAND.get(command)
    if required_assistant_permission is not None and await self._reject_if_no_message_permission(
        update,
        "assistant",
        required_assistant_permission,
    ):
        return

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

    sanitized_result = await _send_telegram_documents_from_result(
        message=update.effective_message,
        result=result,
    )
    await update.effective_message.reply_text(
        "Remote command result:\n" + json.dumps(sanitized_result, ensure_ascii=False, indent=2)
    )


async def _send_telegram_documents_from_result(
    *,
    message: object,
    result: dict[str, object],
) -> dict[str, object]:
    sanitized = dict(result)
    raw_documents = sanitized.pop("telegram_documents", None)
    if not isinstance(raw_documents, list):
        return sanitized

    sent_count = 0
    skipped_count = 0
    for item in raw_documents:
        if not isinstance(item, dict):
            skipped_count += 1
            continue
        filename = str(item.get("filename", "")).strip()
        content_base64 = str(item.get("content_base64", "")).strip()
        caption = str(item.get("caption", "")).strip()
        if not filename or not content_base64:
            skipped_count += 1
            continue

        try:
            content = base64.b64decode(content_base64, validate=True)
        except (binascii.Error, ValueError):
            skipped_count += 1
            continue

        input_file = InputFile(BytesIO(content), filename=filename)
        try:
            await message.reply_document(
                document=input_file,
                caption=caption or None,
            )
        except Exception:
            skipped_count += 1
            continue
        sent_count += 1

    if sent_count:
        sanitized["telegram_documents_sent"] = sent_count
    if skipped_count:
        sanitized["telegram_documents_skipped"] = skipped_count
    return sanitized
