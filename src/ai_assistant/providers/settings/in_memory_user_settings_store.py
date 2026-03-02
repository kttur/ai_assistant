from __future__ import annotations

from collections import defaultdict

from ai_assistant.core.models import SettingChoiceOption, SettingDefinition


DEFAULT_SETTING_DEFINITIONS: tuple[SettingDefinition, ...] = (
    SettingDefinition(
        key="language",
        value_type="choice",
        section="Assistant",
        title="Language",
        description="Preferred language for assistant replies.",
    ),
    SettingDefinition(
        key="tts",
        value_type="bool",
        section="Assistant",
        title="Voice replies (TTS)",
        description="Enable or disable text-to-speech replies.",
    ),
    SettingDefinition(
        key="signature",
        value_type="text",
        section="Assistant",
        title="Reply signature",
        description="Optional text signature appended to assistant messages.",
    ),
)

DEFAULT_SETTING_TRANSLATIONS: dict[str, dict[str, dict[str, str]]] = {
    "ru": {
        "language": {
            "section": "Ассистент",
            "title": "Язык",
            "description": "Предпочитаемый язык ответов ассистента.",
        },
        "tts": {
            "section": "Ассистент",
            "title": "Голосовые ответы (TTS)",
            "description": "Включить или отключить озвучивание ответов.",
        },
        "signature": {
            "section": "Ассистент",
            "title": "Подпись ответа",
            "description": "Необязательная подпись, добавляемая к сообщениям ассистента.",
        },
    }
}

DEFAULT_SETTING_CHOICE_OPTIONS: tuple[SettingChoiceOption, ...] = (
    SettingChoiceOption(
        setting_id="language",
        name="ru",
        display_name="Russian",
        description="Russian",
    ),
    SettingChoiceOption(
        setting_id="language",
        name="en",
        display_name="English",
        description="English",
    ),
)

DEFAULT_SETTING_CHOICE_TRANSLATIONS: dict[str, dict[tuple[str, str], dict[str, str]]] = {
    "ru": {
        ("language", "ru"): {"display_name": "Русский", "description": "Русский"},
        ("language", "en"): {"display_name": "Английский", "description": "English"},
    }
}


def _normalize_locale(locale: str | None) -> str:
    if not locale:
        return "en"
    normalized = locale.strip().lower().replace("_", "-")
    return normalized.split("-", 1)[0] or "en"


def _normalize_choice_name(name: str) -> str:
    return name.strip().lower()


class InMemoryUserSettingsStore:
    def __init__(
        self,
        extra_definitions: tuple[SettingDefinition, ...] | None = None,
        extra_choice_options: tuple[SettingChoiceOption, ...] | None = None,
        extra_translations: dict[str, dict[str, dict[str, str]]] | None = None,
        extra_choice_translations: dict[str, dict[tuple[str, str], dict[str, str]]] | None = None,
    ) -> None:
        self._data: dict[int, dict[str, str]] = defaultdict(dict)
        self._definitions: dict[str, SettingDefinition] = {
            item.key: item for item in DEFAULT_SETTING_DEFINITIONS
        }
        for item in extra_definitions or ():
            self._definitions[item.key] = item
        self._choice_options: dict[str, list[SettingChoiceOption]] = defaultdict(list)
        normalized_option_index: dict[tuple[str, str], int] = {}
        for option in DEFAULT_SETTING_CHOICE_OPTIONS:
            setting_key = option.setting_id.strip().lower()
            self._choice_options[setting_key].append(option)
            normalized_option_index[(setting_key, _normalize_choice_name(option.name))] = (
                len(self._choice_options[setting_key]) - 1
            )
        for option in extra_choice_options or ():
            setting_key = option.setting_id.strip().lower()
            key = (setting_key, _normalize_choice_name(option.name))
            existing_index = normalized_option_index.get(key)
            if existing_index is not None:
                existing = self._choice_options[setting_key][existing_index]
                merged = SettingChoiceOption(
                    setting_id=existing.setting_id,
                    name=existing.name,
                    display_name=existing.display_name or option.display_name,
                    description=existing.description or option.description,
                    permission_type=existing.permission_type or option.permission_type,
                    permission_name=existing.permission_name or option.permission_name,
                )
                if merged != existing:
                    self._choice_options[setting_key][existing_index] = merged
                continue
            self._choice_options[setting_key].append(
                SettingChoiceOption(
                    setting_id=setting_key,
                    name=option.name,
                    display_name=option.display_name,
                    description=option.description,
                    permission_type=option.permission_type,
                    permission_name=option.permission_name,
                )
            )
            normalized_option_index[key] = len(self._choice_options[setting_key]) - 1

        self._translations = self._merge_nested_translation_maps(
            base=DEFAULT_SETTING_TRANSLATIONS,
            extra=extra_translations or {},
        )
        self._choice_translations = self._merge_choice_translation_maps(
            base=DEFAULT_SETTING_CHOICE_TRANSLATIONS,
            extra=extra_choice_translations or {},
        )

    @staticmethod
    def _merge_nested_translation_maps(
        base: dict[str, dict[str, dict[str, str]]],
        extra: dict[str, dict[str, dict[str, str]]],
    ) -> dict[str, dict[str, dict[str, str]]]:
        merged: dict[str, dict[str, dict[str, str]]] = {}
        for locale, values in base.items():
            merged[locale] = {setting_key: dict(item) for setting_key, item in values.items()}
        for locale, values in extra.items():
            locale_bucket = merged.setdefault(locale, {})
            for setting_key, item in values.items():
                current = locale_bucket.setdefault(setting_key, {})
                current.update(item)
        return merged

    @staticmethod
    def _merge_choice_translation_maps(
        base: dict[str, dict[tuple[str, str], dict[str, str]]],
        extra: dict[str, dict[tuple[str, str], dict[str, str]]],
    ) -> dict[str, dict[tuple[str, str], dict[str, str]]]:
        merged: dict[str, dict[tuple[str, str], dict[str, str]]] = {}
        for locale, values in base.items():
            merged[locale] = {choice_key: dict(item) for choice_key, item in values.items()}
        for locale, values in extra.items():
            locale_bucket = merged.setdefault(locale, {})
            for choice_key, item in values.items():
                current = locale_bucket.setdefault(choice_key, {})
                current.update(item)
        return merged

    async def set_setting(self, user_id: int, key: str, value: str) -> None:
        self._data[user_id][key] = value

    async def get_setting(self, user_id: int, key: str) -> str | None:
        return self._data.get(user_id, {}).get(key)

    async def get_all_settings(self, user_id: int) -> dict[str, str]:
        return dict(self._data.get(user_id, {}))

    async def get_setting_definitions(self, locale: str | None = None) -> list[SettingDefinition]:
        language = _normalize_locale(locale)
        localized = self._translations.get(language, {})
        result: list[SettingDefinition] = []
        for item in self._definitions.values():
            localized_item = localized.get(item.key, {})
            result.append(
                SettingDefinition(
                    key=item.key,
                    value_type=item.value_type,
                    section=localized_item.get("section", item.section),
                    title=localized_item.get("title", item.title),
                    description=localized_item.get("description", item.description),
                    is_shown_in_ui=item.is_shown_in_ui,
                    read_permission_type=item.read_permission_type,
                    read_permission_name=item.read_permission_name,
                    write_permission_type=item.write_permission_type,
                    write_permission_name=item.write_permission_name,
                )
            )
        return sorted(
            result,
            key=lambda item: (item.section.lower(), item.title.lower(), item.key),
        )

    async def get_setting_choice_options(
        self,
        setting_id: str,
        locale: str | None = None,
    ) -> list[SettingChoiceOption]:
        normalized = setting_id.strip().lower()
        language = _normalize_locale(locale)
        localized = self._choice_translations.get(language, {})

        items: list[SettingChoiceOption] = []
        for option in self._choice_options.get(normalized, []):
            localized_item = localized.get((option.setting_id, option.name), {})
            items.append(
                SettingChoiceOption(
                    setting_id=option.setting_id,
                    name=option.name,
                    display_name=localized_item.get("display_name", option.display_name),
                    description=localized_item.get("description", option.description),
                    permission_type=option.permission_type,
                    permission_name=option.permission_name,
                )
            )
        return items
