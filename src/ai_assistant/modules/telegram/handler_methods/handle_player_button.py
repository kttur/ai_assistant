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

async def handle_player_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    query = update.callback_query
    if not query:
        return
    if await self._reject_callback_if_not_allowed(update):
        return
    if await self._reject_if_no_callback_permission(update, "general", "usage"):
        return
    if await self._reject_if_no_callback_permission(update, "command", "player"):
        return

    try:
        if query.data == PLAYER_OUTPUT_TOGGLE:
            if not self._output_controller:
                await self._answer_callback(
                    query,
                    "Output controller is not configured.",
                    show_alert=True,
                )
                return
            enabled = self._output_controller.toggle_output()
            state = "ON" if enabled else "OFF"
            await self._answer_callback(query, f"Speakers output: {state}")
            return

        if not self._media_controller:
            await self._answer_callback(query, "Медиа-контроль не настроен.", show_alert=True)
            return

        if query.data == PLAYER_PLAY_PAUSE:
            self._media_controller.play_pause()
            await self._answer_callback(query, "Play/Pause")
            return
        if query.data == PLAYER_PREVIOUS:
            self._media_controller.previous_track()
            await self._answer_callback(query, "Previous track")
            return
        if query.data == PLAYER_NEXT:
            self._media_controller.next_track()
            await self._answer_callback(query, "Next track")
            return
    except Exception as exc:
        if query.data == PLAYER_OUTPUT_TOGGLE:
            await self._answer_callback(
                query,
                f"Output error: {exc}",
                show_alert=True,
            )
            return
        await self._answer_callback(query, "Ошибка отправки клавиши.", show_alert=True)
        return

    await self._answer_callback(query, "Неизвестная кнопка.")


