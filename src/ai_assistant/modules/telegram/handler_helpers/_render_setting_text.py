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

def _render_setting_text(
    self,
    setting: _VisibleSetting,
    setting_index: int,
    total_settings: int,
    locale: str,
) -> str:
    lines = [f"{setting.title} ({setting_index + 1}/{total_settings})"]
    lines.append(self._t("settings.page.key", locale=locale, key=setting.key))
    lines.append(
        self._t(
            "settings.page.current_value",
            locale=locale,
            value=self._format_setting_value(setting, locale=locale),
        )
    )
    if setting.description:
        lines.append("")
        lines.append(setting.description)

    if setting.value_type == "choice":
        lines.append("")
        lines.append(self._t("settings.page.options", locale=locale))
        if setting.options:
            for option in setting.options:
                option_line = f"- {option_display_name(option)}"
                if option.description:
                    option_line += f": {option.description}"
                lines.append(option_line)
        else:
            lines.append(self._t("settings.page.option_empty", locale=locale))
    elif setting.value_type == "text":
        lines.append("")
        lines.append(self._t("settings.page.text_hint", locale=locale))

    return "\n".join(lines)

