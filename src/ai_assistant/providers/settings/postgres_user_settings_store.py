from __future__ import annotations

import asyncio

from ai_assistant.core.models import SettingChoiceOption, SettingDefinition
from ai_assistant.providers.settings.postgres_user_settings_defaults import (
    DEFAULT_SETTING_CHOICE_OPTIONS,
    DEFAULT_SETTING_CHOICE_TRANSLATIONS,
    DEFAULT_SETTING_DEFINITIONS,
    DEFAULT_SETTING_TRANSLATIONS,
)
from ai_assistant.providers.settings.postgres_user_settings_helpers import (
    build_setting_choice_options,
    build_setting_definitions,
    normalize_locale,
)
from ai_assistant.providers.settings.postgres_user_settings_sql import (
    CREATE_PERMISSION_TABLE_SQL,
    CREATE_SETTING_CHOICES_TABLE_SQL,
    CREATE_SETTING_CHOICE_TRANSLATIONS_TABLE_SQL,
    CREATE_SETTINGS_TABLE_SQL,
    CREATE_SETTING_TRANSLATIONS_TABLE_SQL,
    CREATE_USER_SETTINGS_TABLE_SQL,
    GET_ALL_USER_SETTINGS_SQL,
    GET_SETTING_CHOICE_OPTIONS_SQL,
    GET_SETTING_DEFINITIONS_SQL,
    GET_USER_SETTING_SQL,
    INSERT_SETTING_CHOICE_OPTION_SQL,
    INSERT_SETTING_CHOICE_TRANSLATION_SQL,
    INSERT_SETTING_DEFINITION_SQL,
    INSERT_SETTING_TRANSLATION_SQL,
    UPSERT_USER_SETTING_SQL,
)


class PostgresUserSettingsStore:
    def __init__(
        self,
        dsn: str,
        fallback_locale: str = "en",
        extra_definitions: tuple[SettingDefinition, ...] | None = None,
        extra_choice_options: tuple[SettingChoiceOption, ...] | None = None,
        extra_translations: dict[str, dict[str, dict[str, str]]] | None = None,
        extra_choice_translations: dict[str, dict[tuple[str, str], dict[str, str]]] | None = None,
    ) -> None:
        if not dsn.strip():
            raise ValueError("POSTGRES_DSN is required for postgres user settings backend.")
        self._dsn = dsn
        self._fallback_locale = normalize_locale(fallback_locale)
        self._extra_definitions = {item.key: item for item in (extra_definitions or ())}
        self._extra_choice_options: dict[str, list[SettingChoiceOption]] = {}
        for item in extra_choice_options or ():
            key = item.setting_id.strip().lower()
            self._extra_choice_options.setdefault(key, []).append(item)
        self._extra_translations = extra_translations or {}
        self._extra_choice_translations = extra_choice_translations or {}
        try:
            import psycopg  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "psycopg is not installed. Install project with postgres extra: pip install -e .[postgres]"
            ) from exc
        self._psycopg = psycopg
        self._ensure_schema_sync()
        self._seed_defaults_sync()

    async def set_setting(self, user_id: int, key: str, value: str) -> None:
        normalized_key = key.strip().lower()
        await asyncio.to_thread(self._set_setting_sync, user_id, normalized_key, value)

    async def get_setting(self, user_id: int, key: str) -> str | None:
        normalized_key = key.strip().lower()
        return await asyncio.to_thread(self._get_setting_sync, user_id, normalized_key)

    async def get_all_settings(self, user_id: int) -> dict[str, str]:
        return await asyncio.to_thread(self._get_all_settings_sync, user_id)

    async def get_setting_definitions(self, locale: str | None = None) -> list[SettingDefinition]:
        requested_locale = normalize_locale(locale)
        return await asyncio.to_thread(self._get_setting_definitions_sync, requested_locale)

    async def get_setting_choice_options(
        self,
        setting_id: str,
        locale: str | None = None,
    ) -> list[SettingChoiceOption]:
        normalized_setting_id = setting_id.strip().lower()
        requested_locale = normalize_locale(locale)
        return await asyncio.to_thread(
            self._get_setting_choice_options_sync,
            normalized_setting_id,
            requested_locale,
        )

    def _ensure_schema_sync(self) -> None:
        with self._psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(CREATE_PERMISSION_TABLE_SQL)
                cur.execute(CREATE_USER_SETTINGS_TABLE_SQL)
                cur.execute(CREATE_SETTINGS_TABLE_SQL)
                cur.execute(CREATE_SETTING_CHOICES_TABLE_SQL)
                cur.execute(CREATE_SETTING_TRANSLATIONS_TABLE_SQL)
                cur.execute(CREATE_SETTING_CHOICE_TRANSLATIONS_TABLE_SQL)
            conn.commit()

    def _seed_defaults_sync(self) -> None:
        with self._psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                for item in DEFAULT_SETTING_DEFINITIONS:
                    cur.execute(INSERT_SETTING_DEFINITION_SQL, item)
                for item in DEFAULT_SETTING_TRANSLATIONS:
                    cur.execute(INSERT_SETTING_TRANSLATION_SQL, item)
                for item in DEFAULT_SETTING_CHOICE_OPTIONS:
                    cur.execute(INSERT_SETTING_CHOICE_OPTION_SQL, item)
                for item in DEFAULT_SETTING_CHOICE_TRANSLATIONS:
                    cur.execute(INSERT_SETTING_CHOICE_TRANSLATION_SQL, item)
            conn.commit()

    def _set_setting_sync(self, user_id: int, key: str, value: str) -> None:
        with self._psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(UPSERT_USER_SETTING_SQL, (user_id, key, value))
            conn.commit()

    def _get_setting_sync(self, user_id: int, key: str) -> str | None:
        with self._psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(GET_USER_SETTING_SQL, (user_id, key))
                row = cur.fetchone()
                return str(row[0]) if row else None

    def _get_all_settings_sync(self, user_id: int) -> dict[str, str]:
        with self._psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(GET_ALL_USER_SETTINGS_SQL, (user_id,))
                rows = cur.fetchall()
                return {str(row[0]): str(row[1]) for row in rows}

    def _get_setting_definitions_sync(self, locale: str) -> list[SettingDefinition]:
        with self._psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(GET_SETTING_DEFINITIONS_SQL, (locale, self._fallback_locale))
                rows = cur.fetchall()
        return build_setting_definitions(
            rows=rows,
            extra_definitions=self._extra_definitions,
            locale=locale,
            resolve_extra_translation=self._resolve_extra_translation,
        )

    def _get_setting_choice_options_sync(
        self,
        setting_id: str,
        locale: str,
    ) -> list[SettingChoiceOption]:
        with self._psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    GET_SETTING_CHOICE_OPTIONS_SQL,
                    (locale, self._fallback_locale, setting_id),
                )
                rows = cur.fetchall()
        return build_setting_choice_options(
            rows=rows,
            extra_choice_options=self._extra_choice_options.get(setting_id, []),
            locale=locale,
            resolve_extra_choice_translation=self._resolve_extra_choice_translation,
        )

    def _resolve_extra_translation(self, locale: str, setting_key: str) -> dict[str, str]:
        for candidate in (locale, self._fallback_locale):
            item = self._extra_translations.get(candidate, {}).get(setting_key)
            if item:
                return item
        return {}

    def _resolve_extra_choice_translation(
        self,
        locale: str,
        setting_id: str,
        option_name: str,
    ) -> dict[str, str]:
        key = (setting_id, option_name)
        for candidate in (locale, self._fallback_locale):
            item = self._extra_choice_translations.get(candidate, {}).get(key)
            if item:
                return item
        return {}
