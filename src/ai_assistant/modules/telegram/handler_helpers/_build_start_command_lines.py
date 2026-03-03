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

async def _build_start_command_lines(self, user_id: int, locale: str) -> list[str]:
    lines: list[str] = []
    has_assistant_access = await self._has_permission(user_id, "general", "assistant")

    for item in START_COMMAND_HELP:
        command_name = str(item.get("name", "")).strip()
        if not command_name:
            continue
        if not self._is_command_runtime_available(command_name):
            continue
        if bool(item.get("requires_assistant")) and not has_assistant_access:
            continue
        if not await self._has_permission(
            user_id=user_id,
            permission_type="command",
            name=command_name,
        ):
            continue

        description_key = str(item.get("description_key", "")).strip()
        description = self._t(description_key, locale=locale) if description_key else ""
        usage = str(item.get("usage", "")).strip()
        line = f"/{command_name} - {description}" if description else f"/{command_name}"
        lines.append(line)
        if usage and usage != f"/{command_name}":
            lines.append(f"  usage: {usage}")

    return lines

