from __future__ import annotations

import asyncio

from ai_assistant.core.models import SettingChoiceOption, SettingDefinition

CREATE_PERMISSION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS permissions (
    id BIGSERIAL PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN ('general', 'command', 'assistant')),
    name TEXT NOT NULL,
    UNIQUE (type, name)
);
"""

CREATE_USER_SETTINGS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS user_settings (
    user_id BIGINT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, key)
);
"""

CREATE_SETTINGS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN ('text', 'bool', 'choice')),
    section TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    is_shown_in_ui BOOLEAN NOT NULL DEFAULT TRUE,
    read_permission_id BIGINT NULL REFERENCES permissions(id) ON DELETE SET NULL,
    write_permission_id BIGINT NULL REFERENCES permissions(id) ON DELETE SET NULL
);
"""

CREATE_SETTING_CHOICES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS setting_choice_options (
    setting_id TEXT NOT NULL REFERENCES settings(key) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    permission_id BIGINT NULL REFERENCES permissions(id) ON DELETE SET NULL,
    PRIMARY KEY (setting_id, name)
);
"""

CREATE_SETTING_TRANSLATIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS setting_translations (
    setting_key TEXT NOT NULL REFERENCES settings(key) ON DELETE CASCADE,
    locale TEXT NOT NULL,
    section TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (setting_key, locale)
);
"""

CREATE_SETTING_CHOICE_TRANSLATIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS setting_choice_translations (
    setting_id TEXT NOT NULL,
    option_name TEXT NOT NULL,
    locale TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (setting_id, option_name, locale),
    FOREIGN KEY (setting_id, option_name)
        REFERENCES setting_choice_options(setting_id, name)
        ON DELETE CASCADE
);
"""

UPSERT_USER_SETTING_SQL = """
INSERT INTO user_settings (user_id, key, value)
VALUES (%s, %s, %s)
ON CONFLICT (user_id, key)
DO UPDATE SET value = EXCLUDED.value, updated_at = NOW();
"""

INSERT_SETTING_DEFINITION_SQL = """
INSERT INTO settings (
    key,
    type,
    section,
    title,
    description,
    is_shown_in_ui,
    read_permission_id,
    write_permission_id
)
VALUES (%s, %s, %s, %s, %s, %s, NULL, NULL)
ON CONFLICT (key) DO NOTHING;
"""

INSERT_SETTING_CHOICE_OPTION_SQL = """
INSERT INTO setting_choice_options (
    setting_id,
    name,
    description,
    permission_id
)
VALUES (%s, %s, %s, NULL)
ON CONFLICT (setting_id, name) DO NOTHING;
"""

INSERT_SETTING_TRANSLATION_SQL = """
INSERT INTO setting_translations (
    setting_key,
    locale,
    section,
    title,
    description
)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (setting_key, locale) DO NOTHING;
"""

INSERT_SETTING_CHOICE_TRANSLATION_SQL = """
INSERT INTO setting_choice_translations (
    setting_id,
    option_name,
    locale,
    name,
    description
)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (setting_id, option_name, locale) DO NOTHING;
"""

GET_USER_SETTING_SQL = """
SELECT value FROM user_settings WHERE user_id = %s AND key = %s;
"""

GET_ALL_USER_SETTINGS_SQL = """
SELECT key, value
FROM user_settings
WHERE user_id = %s
ORDER BY key;
"""

GET_SETTING_DEFINITIONS_SQL = """
SELECT
    s.key,
    s.type,
    s.section AS section,
    COALESCE(st_req.title, st_fallback.title, s.title) AS title,
    COALESCE(st_req.description, st_fallback.description, s.description) AS description,
    s.is_shown_in_ui,
    read_p.type,
    read_p.name,
    write_p.type,
    write_p.name
FROM settings s
LEFT JOIN setting_translations st_req
    ON st_req.setting_key = s.key AND st_req.locale = %s
LEFT JOIN setting_translations st_fallback
    ON st_fallback.setting_key = s.key AND st_fallback.locale = %s
LEFT JOIN permissions read_p ON read_p.id = s.read_permission_id
LEFT JOIN permissions write_p ON write_p.id = s.write_permission_id
ORDER BY s.section, title, s.key;
"""

GET_SETTING_CHOICE_OPTIONS_SQL = """
SELECT
    o.setting_id,
    o.name,
    COALESCE(sct_req.name, sct_fallback.name, o.name) AS display_name,
    COALESCE(sct_req.description, sct_fallback.description, o.description) AS description,
    p.type,
    p.name
FROM setting_choice_options o
LEFT JOIN setting_choice_translations sct_req
    ON sct_req.setting_id = o.setting_id
    AND sct_req.option_name = o.name
    AND sct_req.locale = %s
LEFT JOIN setting_choice_translations sct_fallback
    ON sct_fallback.setting_id = o.setting_id
    AND sct_fallback.option_name = o.name
    AND sct_fallback.locale = %s
LEFT JOIN permissions p ON p.id = o.permission_id
WHERE o.setting_id = %s
ORDER BY o.name;
"""

DEFAULT_SETTING_DEFINITIONS: tuple[tuple[str, str, str, str, str, bool], ...] = (
    (
        "language",
        "choice",
        "Assistant",
        "Language",
        "Preferred language for assistant replies.",
        True,
    ),
    (
        "tts",
        "bool",
        "Assistant",
        "Voice replies (TTS)",
        "Enable or disable text-to-speech replies.",
        True,
    ),
    (
        "signature",
        "text",
        "Assistant",
        "Reply signature",
        "Optional text signature appended to assistant messages.",
        True,
    ),
)

DEFAULT_SETTING_TRANSLATIONS: tuple[tuple[str, str, str, str, str], ...] = (
    (
        "language",
        "en",
        "Assistant",
        "Language",
        "Preferred language for assistant replies.",
    ),
    (
        "tts",
        "en",
        "Assistant",
        "Voice replies (TTS)",
        "Enable or disable text-to-speech replies.",
    ),
    (
        "signature",
        "en",
        "Assistant",
        "Reply signature",
        "Optional text signature appended to assistant messages.",
    ),
    (
        "language",
        "ru",
        "Ассистент",
        "Язык",
        "Предпочитаемый язык ответов ассистента.",
    ),
    (
        "tts",
        "ru",
        "Ассистент",
        "Голосовые ответы (TTS)",
        "Включить или отключить озвучивание ответов.",
    ),
    (
        "signature",
        "ru",
        "Ассистент",
        "Подпись ответа",
        "Необязательная подпись, добавляемая к сообщениям ассистента.",
    ),
)

DEFAULT_SETTING_CHOICE_OPTIONS: tuple[tuple[str, str, str], ...] = (
    ("language", "ru", "Russian"),
    ("language", "en", "English"),
)

DEFAULT_SETTING_CHOICE_TRANSLATIONS: tuple[tuple[str, str, str, str, str], ...] = (
    ("language", "ru", "en", "Russian", "Russian"),
    ("language", "en", "en", "English", "English"),
    ("language", "ru", "ru", "Русский", "Русский"),
    ("language", "en", "ru", "Английский", "English"),
)


def _normalize_locale(locale: str | None) -> str:
    if not locale:
        return "en"
    normalized = locale.strip().lower().replace("_", "-")
    return normalized.split("-", 1)[0] or "en"


def _normalize_choice_name(name: str) -> str:
    return name.strip().lower()


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
        self._fallback_locale = _normalize_locale(fallback_locale)
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
        requested_locale = _normalize_locale(locale)
        return await asyncio.to_thread(self._get_setting_definitions_sync, requested_locale)

    async def get_setting_choice_options(
        self,
        setting_id: str,
        locale: str | None = None,
    ) -> list[SettingChoiceOption]:
        normalized_setting_id = setting_id.strip().lower()
        requested_locale = _normalize_locale(locale)
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

        definitions: list[SettingDefinition] = []
        for row in rows:
            definitions.append(
                SettingDefinition(
                    key=str(row[0]),
                    value_type=str(row[1]),  # type: ignore[arg-type]
                    section=str(row[2]),
                    title=str(row[3]),
                    description=str(row[4] or ""),
                    is_shown_in_ui=bool(row[5]),
                    read_permission_type=str(row[6]) if row[6] else None,
                    read_permission_name=str(row[7]) if row[7] else None,
                    write_permission_type=str(row[8]) if row[8] else None,
                    write_permission_name=str(row[9]) if row[9] else None,
                )
            )
        existing_keys = {item.key for item in definitions}
        for key, item in self._extra_definitions.items():
            if key in existing_keys:
                continue
            translation = self._resolve_extra_translation(locale=locale, setting_key=key)
            definitions.append(
                SettingDefinition(
                    key=item.key,
                    value_type=item.value_type,
                    section=translation.get("section", item.section),
                    title=translation.get("title", item.title),
                    description=translation.get("description", item.description),
                    is_shown_in_ui=item.is_shown_in_ui,
                    read_permission_type=item.read_permission_type,
                    read_permission_name=item.read_permission_name,
                    write_permission_type=item.write_permission_type,
                    write_permission_name=item.write_permission_name,
                )
            )
        definitions.sort(key=lambda item: (item.section.lower(), item.title.lower(), item.key))
        return definitions

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

        options: list[SettingChoiceOption] = []
        for row in rows:
            options.append(
                SettingChoiceOption(
                    setting_id=str(row[0]),
                    name=str(row[1]),
                    display_name=str(row[2]) if row[2] else None,
                    description=str(row[3] or ""),
                    permission_type=str(row[4]) if row[4] else None,
                    permission_name=str(row[5]) if row[5] else None,
                )
            )
        normalized_index: dict[tuple[str, str], int] = {}
        for index, item in enumerate(options):
            key = (item.setting_id.strip().lower(), _normalize_choice_name(item.name))
            normalized_index.setdefault(key, index)

        for item in self._extra_choice_options.get(setting_id, []):
            normalized_key = (
                item.setting_id.strip().lower(),
                _normalize_choice_name(item.name),
            )
            existing_index = normalized_index.get(normalized_key)
            if existing_index is not None:
                existing_item = options[existing_index]
                translation = self._resolve_extra_choice_translation(
                    locale=locale,
                    setting_id=item.setting_id,
                    option_name=item.name,
                )
                merged = SettingChoiceOption(
                    setting_id=existing_item.setting_id,
                    name=existing_item.name,
                    display_name=(
                        existing_item.display_name
                        or translation.get("display_name")
                        or item.display_name
                    ),
                    description=(
                        existing_item.description
                        or translation.get("description")
                        or item.description
                    ),
                    permission_type=existing_item.permission_type or item.permission_type,
                    permission_name=existing_item.permission_name or item.permission_name,
                )
                if merged != existing_item:
                    options[existing_index] = merged
                continue

            translation = self._resolve_extra_choice_translation(
                locale=locale,
                setting_id=item.setting_id,
                option_name=item.name,
            )
            options.append(
                SettingChoiceOption(
                    setting_id=item.setting_id.strip().lower(),
                    name=item.name,
                    display_name=translation.get("display_name", item.display_name),
                    description=translation.get("description", item.description),
                    permission_type=item.permission_type,
                    permission_name=item.permission_name,
                )
            )
            normalized_index[normalized_key] = len(options) - 1

        options.sort(key=lambda item: item.name.lower())
        return options

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
