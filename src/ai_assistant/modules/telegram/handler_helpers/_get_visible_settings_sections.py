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

async def _get_visible_settings_sections(
    self,
    user_id: int,
    ui_only: bool,
    locale: str,
) -> list[tuple[str, list[_VisibleSetting]]]:
    store = self._user_settings_store
    if store is None:
        return []

    definitions = await store.get_setting_definitions(locale=locale)
    values_map = await store.get_all_settings(user_id)
    grouped: dict[str, list[_VisibleSetting]] = {}
    section_labels: dict[str, str] = {}

    for definition in definitions:
        if ui_only and not definition.is_shown_in_ui:
            continue

        if not await self._has_optional_permission(
            user_id,
            definition.read_permission_type,
            definition.read_permission_name,
        ):
            continue

        can_write = await self._has_optional_permission(
            user_id,
            definition.write_permission_type,
            definition.write_permission_name,
        )

        options: tuple[SettingChoiceOption, ...] = ()
        if definition.value_type == "choice":
            raw_options = await store.get_setting_choice_options(
                definition.key,
                locale=locale,
            )
            visible_options: list[SettingChoiceOption] = []
            for option in raw_options:
                if await self._has_optional_permission(
                    user_id,
                    option.permission_type,
                    option.permission_name,
                ):
                    visible_options.append(option)
            if definition.key == "llm_model":
                active_provider = self._resolve_active_llm_provider(
                    values_map=values_map,
                    llm_model_value=values_map.get(definition.key),
                )
                if active_provider:
                    exact_matches: list[SettingChoiceOption] = []
                    ambiguous: list[SettingChoiceOption] = []
                    for option in visible_options:
                        provider_name = extract_model_provider_from_option(option)
                        if provider_name is None:
                            ambiguous.append(option)
                        elif provider_name == active_provider:
                            exact_matches.append(option)
                    if exact_matches:
                        visible_options = [*exact_matches, *ambiguous]
                    else:
                        visible_options = ambiguous
            options = tuple(visible_options)

        section_key = self._normalize_settings_section_key(definition.section)
        section_name = section_labels.setdefault(
            section_key,
            self._localize_settings_section_name(definition.section, locale=locale),
        )
        grouped.setdefault(section_key, []).append(
            _VisibleSetting(
                key=definition.key,
                value_type=definition.value_type,
                section=section_name,
                title=definition.title,
                description=definition.description,
                current_value=values_map.get(definition.key),
                can_write=can_write,
                options=options,
            )
        )

    sections: list[tuple[str, list[_VisibleSetting]]] = []
    for section_key in sorted(grouped.keys(), key=lambda item: section_labels[item].lower()):
        settings_list = sorted(
            grouped[section_key],
            key=lambda item: (item.title.lower(), item.key),
        )
        if settings_list:
            sections.append((section_labels[section_key], settings_list))
    return sections

