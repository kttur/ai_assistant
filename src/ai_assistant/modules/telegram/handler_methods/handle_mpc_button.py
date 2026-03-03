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
    if not self._mpc_controller:
        await self._answer_callback(query, "MPC-контроллер не настроен.", show_alert=True)
        return

    try:
        ok = False
        message = "Неизвестная команда."
        if query.data == MPC_AUDIO_PREVIOUS:
            ok = self._mpc_controller.audio_previous()
            message = "Аудио: предыдущая дорожка"
        elif query.data == MPC_AUDIO_NEXT:
            ok = self._mpc_controller.audio_next()
            message = "Аудио: следующая дорожка"
        elif query.data == MPC_SUBTITLE_PREVIOUS:
            ok = self._mpc_controller.subtitle_previous()
            message = "Субтитры: предыдущая дорожка"
        elif query.data == MPC_SUBTITLE_NEXT:
            ok = self._mpc_controller.subtitle_next()
            message = "Субтитры: следующая дорожка"
        elif query.data == MPC_AUDIO_RU:
            ok = self._mpc_controller.audio_set_language("ru")
            message = "Аудио: переключено на RU"
        elif query.data == MPC_AUDIO_EN:
            ok = self._mpc_controller.audio_set_language("en")
            message = "Аудио: переключено на EN"
        elif query.data == MPC_SUBTITLE_RU:
            ok = self._mpc_controller.subtitle_set_language("ru")
            message = "Субтитры: переключено на RU"
        elif query.data == MPC_SUBTITLE_EN:
            ok = self._mpc_controller.subtitle_set_language("en")
            message = "Субтитры: переключено на EN"

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


