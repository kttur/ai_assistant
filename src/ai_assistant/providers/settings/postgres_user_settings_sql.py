from __future__ import annotations

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
