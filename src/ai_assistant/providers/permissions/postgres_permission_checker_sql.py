from __future__ import annotations

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS permissions (
    id BIGSERIAL PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN ('general', 'command', 'assistant')),
    name TEXT NOT NULL,
    UNIQUE (type, name)
);

CREATE TABLE IF NOT EXISTS user_permissions (
    user_id BIGINT NOT NULL,
    permission_id BIGINT NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    is_active BOOLEAN NOT NULL,
    PRIMARY KEY (user_id, permission_id)
);

CREATE TABLE IF NOT EXISTS roles (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS role_permissions (
    role_id BIGINT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id BIGINT NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE IF NOT EXISTS user_roles (
    user_id BIGINT NOT NULL,
    role_id BIGINT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);
"""

HAS_PERMISSION_SQL = """
WITH target_permission AS (
    SELECT id
    FROM permissions
    WHERE type = %s AND name = %s
    LIMIT 1
),
user_override AS (
    SELECT up.is_active
    FROM user_permissions up
    JOIN target_permission tp ON tp.id = up.permission_id
    WHERE up.user_id = %s
    LIMIT 1
),
has_role_permission AS (
    SELECT EXISTS (
        SELECT 1
        FROM user_roles ur
        JOIN role_permissions rp ON rp.role_id = ur.role_id
        JOIN target_permission tp ON tp.id = rp.permission_id
        WHERE ur.user_id = %s
    ) AS value
)
SELECT COALESCE(
    (SELECT is_active FROM user_override),
    (SELECT value FROM has_role_permission),
    FALSE
);
"""

CREATE_ROLE_SQL = """
INSERT INTO roles (name)
VALUES (%s)
ON CONFLICT (name) DO NOTHING;
"""

GET_ROLE_ID_SQL = """
SELECT id FROM roles WHERE name = %s LIMIT 1;
"""

GET_PERMISSION_ID_SQL = """
SELECT id FROM permissions WHERE type = %s AND name = %s LIMIT 1;
"""

UPSERT_PERMISSION_SQL = """
INSERT INTO permissions (type, name)
VALUES (%s, %s)
ON CONFLICT (type, name)
DO UPDATE SET name = EXCLUDED.name
RETURNING id;
"""

UPSERT_USER_PERMISSION_SQL = """
INSERT INTO user_permissions (user_id, permission_id, is_active)
VALUES (%s, %s, %s)
ON CONFLICT (user_id, permission_id)
DO UPDATE SET is_active = EXCLUDED.is_active;
"""

ASSIGN_ROLE_SQL = """
INSERT INTO user_roles (user_id, role_id)
VALUES (%s, %s)
ON CONFLICT (user_id, role_id) DO NOTHING;
"""

GRANT_ROLE_PERMISSION_SQL = """
INSERT INTO role_permissions (role_id, permission_id)
VALUES (%s, %s)
ON CONFLICT (role_id, permission_id) DO NOTHING;
"""

REVOKE_ROLE_PERMISSION_SQL = """
DELETE FROM role_permissions
WHERE role_id = %s AND permission_id = %s;
"""

GET_USER_ROLES_SQL = """
SELECT r.name
FROM user_roles ur
JOIN roles r ON r.id = ur.role_id
WHERE ur.user_id = %s
ORDER BY r.name;
"""

GET_USER_OVERRIDES_SQL = """
SELECT p.type, p.name, up.is_active
FROM user_permissions up
JOIN permissions p ON p.id = up.permission_id
WHERE up.user_id = %s
ORDER BY p.type, p.name;
"""

GET_USER_ROLE_PERMISSIONS_SQL = """
SELECT r.name, p.type, p.name
FROM user_roles ur
JOIN roles r ON r.id = ur.role_id
JOIN role_permissions rp ON rp.role_id = ur.role_id
JOIN permissions p ON p.id = rp.permission_id
WHERE ur.user_id = %s
ORDER BY r.name, p.type, p.name;
"""
