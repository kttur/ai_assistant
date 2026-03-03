from __future__ import annotations

from ai_assistant.config.settings import Settings
from ai_assistant.core.interfaces import UserSettingsStore
from ai_assistant.core.models import SettingChoiceOption, SettingDefinition
from ai_assistant.providers.settings.in_memory_user_settings_store import InMemoryUserSettingsStore
from ai_assistant.providers.settings.postgres_user_settings_store import PostgresUserSettingsStore


def build_user_settings_store(
    settings: Settings,
    extra_definitions: tuple[SettingDefinition, ...],
    extra_choice_options: tuple[SettingChoiceOption, ...],
    extra_translations: dict[str, dict[str, dict[str, str]]],
    extra_choice_translations: dict[str, dict[tuple[str, str], dict[str, str]]],
) -> UserSettingsStore:
    backend = settings.user_settings_backend.lower()
    if backend == "memory":
        return InMemoryUserSettingsStore(
            extra_definitions=extra_definitions,
            extra_choice_options=extra_choice_options,
            extra_translations=extra_translations,
            extra_choice_translations=extra_choice_translations,
        )
    if backend == "postgres":
        return PostgresUserSettingsStore(
            dsn=settings.postgres_dsn,
            fallback_locale=settings.default_locale,
            extra_definitions=extra_definitions,
            extra_choice_options=extra_choice_options,
            extra_translations=extra_translations,
            extra_choice_translations=extra_choice_translations,
        )
    raise ValueError(f"Unsupported user settings backend: {settings.user_settings_backend}")
