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

async def handle_settings_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    query = update.callback_query
    if not query:
        return
    if await self._reject_callback_if_not_allowed(update):
        return
    if await self._reject_if_no_callback_permission(update, "general", "usage"):
        return
    if await self._reject_if_no_callback_permission(update, "command", "settings"):
        return
    if not self._user_settings_store or not update.effective_user:
        locale = None
        if update.effective_user:
            locale = await self._resolve_user_locale(update.effective_user.id)
        await self._answer_callback(
            query,
            self._t("errors.settings_store_unconfigured", locale=locale),
            show_alert=True,
        )
        return

    data = query.data or ""
    parts = data.split(":")
    if len(parts) < 2 or parts[0] != "settings":
        locale = await self._resolve_user_locale(update.effective_user.id)
        await self._answer_callback(
            query,
            self._t("settings.callback.unknown_action", locale=locale),
            show_alert=True,
        )
        return

    user_id = update.effective_user.id
    locale = await self._resolve_user_locale(user_id)
    action = parts[1]

    if action == "home":
        await self._edit_settings_home_message(query=query, user_id=user_id, locale=locale)
        await self._answer_callback(query, self._t("settings.callback.ready", locale=locale))
        return

    if action == "section":
        if len(parts) != 3:
            await self._answer_callback(
                query,
                self._t("settings.callback.invalid_section_request", locale=locale),
                show_alert=True,
            )
            return
        try:
            section_index = int(parts[2])
        except ValueError:
            await self._answer_callback(
                query,
                self._t("settings.callback.invalid_section_index", locale=locale),
                show_alert=True,
            )
            return
        await self._edit_setting_page_message(
            query=query,
            user_id=user_id,
            section_index=section_index,
            setting_index=0,
            locale=locale,
        )
        await self._answer_callback(query, self._t("settings.callback.ready", locale=locale))
        return

    if action == "view":
        if len(parts) != 4:
            await self._answer_callback(
                query,
                self._t("settings.callback.invalid_view_request", locale=locale),
                show_alert=True,
            )
            return
        try:
            section_index = int(parts[2])
            setting_index = int(parts[3])
        except ValueError:
            await self._answer_callback(
                query,
                self._t("settings.callback.invalid_setting_index", locale=locale),
                show_alert=True,
            )
            return
        await self._edit_setting_page_message(
            query=query,
            user_id=user_id,
            section_index=section_index,
            setting_index=setting_index,
            locale=locale,
        )
        await self._answer_callback(query, self._t("settings.callback.ready", locale=locale))
        return

    if action == "toggle":
        if len(parts) != 4:
            await self._answer_callback(
                query,
                self._t("settings.callback.invalid_toggle_request", locale=locale),
                show_alert=True,
            )
            return
        try:
            section_index = int(parts[2])
            setting_index = int(parts[3])
        except ValueError:
            await self._answer_callback(
                query,
                self._t("settings.callback.invalid_setting_index", locale=locale),
                show_alert=True,
            )
            return
        new_value = await self._toggle_bool_setting(
            user_id=user_id,
            section_index=section_index,
            setting_index=setting_index,
            locale=locale,
        )
        if new_value is None:
            await self._answer_callback(
                query,
                self._t("settings.callback.write_forbidden", locale=locale),
                show_alert=True,
            )
            return
        await self._edit_setting_page_message(
            query=query,
            user_id=user_id,
            section_index=section_index,
            setting_index=setting_index,
            locale=locale,
        )
        state = "ON" if is_truthy_value(new_value) else "OFF"
        await self._answer_callback(
            query,
            self._t("settings.callback.saved_state", locale=locale, state=state),
        )
        return

    if action == "choice":
        if len(parts) != 5:
            await self._answer_callback(
                query,
                self._t("settings.callback.invalid_choice_request", locale=locale),
                show_alert=True,
            )
            return
        try:
            section_index = int(parts[2])
            setting_index = int(parts[3])
            option_index = int(parts[4])
        except ValueError:
            await self._answer_callback(
                query,
                self._t("settings.callback.invalid_choice_index", locale=locale),
                show_alert=True,
            )
            return
        chosen = await self._set_choice_setting_value(
            user_id=user_id,
            section_index=section_index,
            setting_index=setting_index,
            option_index=option_index,
            locale=locale,
        )
        if chosen is None:
            await self._answer_callback(
                query,
                self._t("settings.callback.option_unavailable", locale=locale),
                show_alert=True,
            )
            return
        await self._edit_setting_page_message(
            query=query,
            user_id=user_id,
            section_index=section_index,
            setting_index=setting_index,
            locale=locale,
        )
        await self._answer_callback(
            query,
            self._t(
                "settings.callback.saved_value",
                locale=locale,
                value=option_display_name(chosen),
            ),
        )
        return

    if action == "text":
        if len(parts) != 4:
            await self._answer_callback(
                query,
                self._t("settings.callback.invalid_text_request", locale=locale),
                show_alert=True,
            )
            return
        try:
            section_index = int(parts[2])
            setting_index = int(parts[3])
        except ValueError:
            await self._answer_callback(
                query,
                self._t("settings.callback.invalid_setting_index", locale=locale),
                show_alert=True,
            )
            return
        started = await self._start_text_setting_input(
            update=update,
            section_index=section_index,
            setting_index=setting_index,
            locale=locale,
        )
        if not started:
            await self._answer_callback(
                query,
                self._t("settings.callback.write_forbidden", locale=locale),
                show_alert=True,
            )
        return

    if action == "text_clear":
        if len(parts) != 4:
            await self._answer_callback(
                query,
                self._t("settings.callback.invalid_text_clear_request", locale=locale),
                show_alert=True,
            )
            return
        try:
            section_index = int(parts[2])
            setting_index = int(parts[3])
        except ValueError:
            await self._answer_callback(
                query,
                self._t("settings.callback.invalid_setting_index", locale=locale),
                show_alert=True,
            )
            return
        cleared = await self._clear_text_setting_value(
            user_id=user_id,
            section_index=section_index,
            setting_index=setting_index,
            locale=locale,
        )
        if not cleared:
            await self._answer_callback(
                query,
                self._t("settings.callback.write_forbidden", locale=locale),
                show_alert=True,
            )
            return
        await self._edit_setting_page_message(
            query=query,
            user_id=user_id,
            section_index=section_index,
            setting_index=setting_index,
            locale=locale,
        )
        await self._answer_callback(query, self._t("settings.callback.cleared", locale=locale))
        return

    await self._answer_callback(
        query,
        self._t("settings.callback.unknown_action", locale=locale),
        show_alert=True,
    )


