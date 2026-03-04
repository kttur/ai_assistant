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

async def handle_mpc_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    query = update.callback_query
    if not query:
        return
    if await self._reject_callback_if_not_allowed(update):
        return
    if await self._reject_if_no_callback_permission(update, "general", "usage"):
        return
    if await self._reject_if_no_callback_permission(update, "command", "mpc"):
        return

    def _resolve_mpc_action(
        callback_data: str | None,
    ) -> tuple[str | None, dict[str, object], str]:
        mapping: dict[str, tuple[str, dict[str, object], str]] = {
            MPC_AUDIO_PREVIOUS: ("mpc.audio_previous", {}, "Аудио: предыдущая дорожка"),
            MPC_AUDIO_NEXT: ("mpc.audio_next", {}, "Аудио: следующая дорожка"),
            MPC_SUBTITLE_PREVIOUS: ("mpc.subtitle_previous", {}, "Субтитры: предыдущая дорожка"),
            MPC_SUBTITLE_NEXT: ("mpc.subtitle_next", {}, "Субтитры: следующая дорожка"),
            MPC_AUDIO_RU: ("mpc.audio_set_language", {"language": "ru"}, "Аудио: переключено на RU"),
            MPC_AUDIO_EN: ("mpc.audio_set_language", {"language": "en"}, "Аудио: переключено на EN"),
            MPC_SUBTITLE_RU: (
                "mpc.subtitle_set_language",
                {"language": "ru"},
                "Субтитры: переключено на RU",
            ),
            MPC_SUBTITLE_EN: (
                "mpc.subtitle_set_language",
                {"language": "en"},
                "Субтитры: переключено на EN",
            ),
        }
        if callback_data is None:
            return None, {}, "Неизвестная команда."
        return mapping.get(callback_data, (None, {}, "Неизвестная команда."))

    try:
        remote_command, remote_args, message = _resolve_mpc_action(query.data)
        if remote_command is None:
            await self._answer_callback(query, message, show_alert=True)
            return

        if self._mpc_controller is not None:
            ok = False
            if query.data == MPC_AUDIO_PREVIOUS:
                ok = self._mpc_controller.audio_previous()
            elif query.data == MPC_AUDIO_NEXT:
                ok = self._mpc_controller.audio_next()
            elif query.data == MPC_SUBTITLE_PREVIOUS:
                ok = self._mpc_controller.subtitle_previous()
            elif query.data == MPC_SUBTITLE_NEXT:
                ok = self._mpc_controller.subtitle_next()
            elif query.data == MPC_AUDIO_RU:
                ok = self._mpc_controller.audio_set_language("ru")
            elif query.data == MPC_AUDIO_EN:
                ok = self._mpc_controller.audio_set_language("en")
            elif query.data == MPC_SUBTITLE_RU:
                ok = self._mpc_controller.subtitle_set_language("ru")
            elif query.data == MPC_SUBTITLE_EN:
                ok = self._mpc_controller.subtitle_set_language("en")
        else:
            if self._remote_ws_hub is None or update.effective_user is None:
                await self._answer_callback(query, "MPC-контроллер не настроен.", show_alert=True)
                return
            remote_result = await self._remote_ws_hub.execute_user_remote_command(
                user_id=update.effective_user.id,
                command=remote_command,
                args=remote_args,
            )
            ok = bool(remote_result.get("ok"))
            if not ok:
                remote_error = str(remote_result.get("message", "")).strip()
                await self._answer_callback(
                    query,
                    remote_error
                    or "MPC-HC не найден, файл не открыт или нужная дорожка отсутствует.",
                    show_alert=True,
                )
                return

        if ok:
            await self._answer_callback(query, message)
        else:
            await self._answer_callback(
                query,
                "MPC-HC не найден, файл не открыт или нужная дорожка отсутствует.",
                show_alert=True,
            )
    except Exception:
        await self._answer_callback(query, "Ошибка управления MPC-HC.", show_alert=True)


