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

async def _sync_llm_model_with_provider(
    self,
    user_id: int,
    provider_name: str,
    locale: str,
) -> None:
    if not self._user_settings_store:
        return
    target_provider = provider_name.strip().lower()
    if not target_provider:
        return
    if target_provider == "auto":
        return

    sections = await self._get_visible_settings_sections(
        user_id=user_id,
        ui_only=True,
        locale=locale,
    )
    llm_model_setting: _VisibleSetting | None = None
    for _, settings_list in sections:
        for item in settings_list:
            if item.key == "llm_model":
                llm_model_setting = item
                break
        if llm_model_setting is not None:
            break

    if llm_model_setting is None:
        return
    if extract_model_provider(llm_model_setting.current_value) == target_provider:
        return

    exact_matches: list[SettingChoiceOption] = []
    ambiguous: list[SettingChoiceOption] = []
    for option in llm_model_setting.options:
        option_provider = extract_model_provider_from_option(option)
        if option_provider is None:
            ambiguous.append(option)
            continue
        if option_provider == target_provider:
            exact_matches.append(option)

    preferred = exact_matches[0] if exact_matches else (ambiguous[0] if ambiguous else None)
    if preferred is None:
        return
    await self._user_settings_store.set_setting(user_id=user_id, key="llm_model", value=preferred.name)

