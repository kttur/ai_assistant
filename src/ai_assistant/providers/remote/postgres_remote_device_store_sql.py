from __future__ import annotations

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS remote_clients (
    client_id TEXT PRIMARY KEY,
    owner_user_id BIGINT NOT NULL,
    display_name TEXT NOT NULL,
    platform TEXT NOT NULL,
    server_id TEXT NOT NULL,
    token_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS idx_remote_clients_owner ON remote_clients(owner_user_id);
CREATE INDEX IF NOT EXISTS idx_remote_clients_server ON remote_clients(server_id);

CREATE TABLE IF NOT EXISTS remote_client_access (
    client_id TEXT NOT NULL REFERENCES remote_clients(client_id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    granted_by BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (client_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_remote_client_access_user ON remote_client_access(user_id);

CREATE TABLE IF NOT EXISTS remote_user_defaults (
    user_id BIGINT PRIMARY KEY,
    client_id TEXT NOT NULL REFERENCES remote_clients(client_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS remote_link_codes (
    code TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    platform TEXT NOT NULL,
    server_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_remote_link_codes_expiry ON remote_link_codes(expires_at);
"""

PUT_LINK_CODE_SQL = """
INSERT INTO remote_link_codes (
    code,
    session_id,
    client_id,
    display_name,
    platform,
    server_id,
    expires_at
)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (code)
DO UPDATE SET
    session_id = EXCLUDED.session_id,
    client_id = EXCLUDED.client_id,
    display_name = EXCLUDED.display_name,
    platform = EXCLUDED.platform,
    server_id = EXCLUDED.server_id,
    expires_at = EXCLUDED.expires_at,
    created_at = NOW();
"""

CONSUME_LINK_CODE_SQL = """
DELETE FROM remote_link_codes
WHERE code = %s AND expires_at > %s
RETURNING code, session_id, client_id, display_name, platform, server_id, expires_at;
"""

DELETE_EXPIRED_LINK_CODES_SQL = """
DELETE FROM remote_link_codes
WHERE expires_at <= %s;
"""

GET_CLIENT_SQL = """
SELECT
    client_id,
    owner_user_id,
    display_name,
    platform,
    server_id,
    created_at,
    updated_at,
    last_seen_at
FROM remote_clients
WHERE client_id = %s
LIMIT 1;
"""

UPSERT_CLIENT_SQL = """
INSERT INTO remote_clients (
    client_id,
    owner_user_id,
    display_name,
    platform,
    server_id,
    token_hash,
    created_at,
    updated_at,
    last_seen_at
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NULL)
ON CONFLICT (client_id)
DO UPDATE SET
    owner_user_id = EXCLUDED.owner_user_id,
    display_name = EXCLUDED.display_name,
    platform = EXCLUDED.platform,
    server_id = EXCLUDED.server_id,
    token_hash = EXCLUDED.token_hash,
    updated_at = EXCLUDED.updated_at
RETURNING
    client_id,
    owner_user_id,
    display_name,
    platform,
    server_id,
    created_at,
    updated_at,
    last_seen_at;
"""

AUTHENTICATE_CLIENT_SQL = """
SELECT
    client_id,
    owner_user_id,
    display_name,
    platform,
    server_id,
    created_at,
    updated_at,
    last_seen_at
FROM remote_clients
WHERE client_id = %s AND server_id = %s AND token_hash = %s
LIMIT 1;
"""

TOUCH_CLIENT_LAST_SEEN_SQL = """
UPDATE remote_clients
SET updated_at = %s, last_seen_at = %s
WHERE client_id = %s;
"""

LIST_USER_CLIENTS_SQL = """
SELECT
    c.client_id,
    c.display_name,
    c.platform,
    c.server_id,
    (c.owner_user_id = %s) AS is_owner,
    (d.client_id IS NOT NULL) AS is_default,
    c.last_seen_at
FROM remote_clients c
LEFT JOIN remote_client_access a
    ON a.client_id = c.client_id AND a.user_id = %s
LEFT JOIN remote_user_defaults d
    ON d.user_id = %s AND d.client_id = c.client_id
WHERE c.owner_user_id = %s OR a.user_id = %s
ORDER BY (d.client_id IS NOT NULL) DESC, c.display_name, c.client_id;
"""

GET_USER_DEFAULT_CLIENT_SQL = """
SELECT client_id
FROM remote_user_defaults
WHERE user_id = %s
LIMIT 1;
"""

SET_USER_DEFAULT_CLIENT_SQL = """
INSERT INTO remote_user_defaults (user_id, client_id)
VALUES (%s, %s)
ON CONFLICT (user_id)
DO UPDATE SET client_id = EXCLUDED.client_id;
"""

DELETE_USER_DEFAULT_CLIENT_SQL = """
DELETE FROM remote_user_defaults
WHERE user_id = %s;
"""

HAS_USER_ACCESS_SQL = """
SELECT EXISTS(
    SELECT 1
    FROM remote_clients c
    LEFT JOIN remote_client_access a
        ON a.client_id = c.client_id AND a.user_id = %s
    WHERE c.client_id = %s
      AND (c.owner_user_id = %s OR a.user_id = %s)
);
"""

GRANT_CLIENT_ACCESS_SQL = """
INSERT INTO remote_client_access (client_id, user_id, granted_by, created_at)
VALUES (%s, %s, %s, %s)
ON CONFLICT (client_id, user_id)
DO UPDATE SET
    granted_by = EXCLUDED.granted_by,
    created_at = EXCLUDED.created_at;
"""

REVOKE_CLIENT_ACCESS_SQL = """
DELETE FROM remote_client_access
WHERE client_id = %s AND user_id = %s;
"""

REMOVE_CLIENT_SQL = """
DELETE FROM remote_clients
WHERE client_id = %s;
"""
