from __future__ import annotations

import asyncio

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest

from ai_assistant.core.models import SettingChoiceOption, SettingDefinition
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
    START_COMMAND_HELP,
)
from ai_assistant.modules.telegram.handler_functions import (
    bool_to_storage_value,
    extract_model_provider,
    extract_model_provider_from_option,
    is_truthy_value,
    option_display_name,
)
from ai_assistant.modules.telegram.handler_types import (
    PendingTextSettingInput as _PendingTextSettingInput,
    VisibleSetting as _VisibleSetting,
)

async def _build_start_message(self, user_id: int) -> str:
    locale = await self._resolve_user_locale(user_id)
    lines: list[str] = [self._t("start.title", locale=locale)]
    is_admin = self._admin_telegram_id is not None and user_id == self._admin_telegram_id
    if is_admin:
        lines.append(self._t("start.admin_mode", locale=locale))

    if self._permission_admin is not None:
        try:
            roles = await self._permission_admin.get_user_roles(user_id)
            roles_label = ", ".join(roles) if roles else self._t("start.roles_none", locale=locale)
            lines.append(self._t("start.roles", locale=locale, roles=roles_label))
        except Exception:
            lines.append(self._t("start.roles_unavailable", locale=locale))

    command_lines = await self._build_start_command_lines(user_id=user_id, locale=locale)
    lines.append("")
    lines.append(self._t("start.commands_header", locale=locale))
    if command_lines:
        lines.extend(command_lines)
    else:
        lines.append(self._t("start.no_commands", locale=locale))

    has_assistant_access = await self._has_permission(user_id, "general", "assistant")
    if has_assistant_access:
        lines.append("")
        lines.append(self._t("start.ai_header", locale=locale))
        lines.append(self._t("start.ai_text_message", locale=locale))

        ask_available = (
            self._is_command_runtime_available("ask")
            and await self._has_permission(user_id, "command", "ask")
        )
        if ask_available:
            lines.append(self._t("start.ai_ask_available", locale=locale))

        clear_available = (
            self._is_command_runtime_available("clear")
            and await self._has_permission(user_id, "command", "clear")
        )
        if clear_available:
            lines.append(self._t("start.ai_clear_available", locale=locale))

    return "\n".join(lines)

