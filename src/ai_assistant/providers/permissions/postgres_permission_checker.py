from __future__ import annotations

import asyncio

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


class PostgresPermissionChecker:
    def __init__(self, dsn: str) -> None:
        if not dsn.strip():
            raise ValueError("POSTGRES_DSN is required for postgres permissions backend.")
        self._dsn = dsn
        try:
            import psycopg  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "psycopg is not installed. Install project with postgres extra: pip install -e .[postgres]"
            ) from exc
        self._psycopg = psycopg
        self._ensure_schema_sync()

    async def has_permission(self, user_id: int, permission_type: str, name: str) -> bool:
        normalized_type = permission_type.strip().lower()
        normalized_name = name.strip().lower()
        if normalized_type not in {"general", "command", "assistant"}:
            return False
        if not normalized_name:
            return False
        return await asyncio.to_thread(
            self._has_permission_sync,
            user_id,
            normalized_type,
            normalized_name,
        )

    async def set_user_permission(
        self,
        user_id: int,
        permission_type: str,
        name: str,
        is_active: bool,
    ) -> None:
        normalized_type, normalized_name = self._normalize_permission_parts(permission_type, name)
        await asyncio.to_thread(
            self._set_user_permission_sync,
            user_id,
            normalized_type,
            normalized_name,
            bool(is_active),
        )

    async def create_role(self, role_name: str) -> None:
        normalized = self._normalize_role_name(role_name)
        await asyncio.to_thread(self._create_role_sync, normalized)

    async def assign_role(self, user_id: int, role_name: str) -> None:
        normalized = self._normalize_role_name(role_name)
        await asyncio.to_thread(self._assign_role_sync, user_id, normalized)

    async def grant_role_permission(
        self,
        role_name: str,
        permission_type: str,
        name: str,
    ) -> None:
        normalized_role = self._normalize_role_name(role_name)
        normalized_type, normalized_name = self._normalize_permission_parts(permission_type, name)
        await asyncio.to_thread(
            self._grant_role_permission_sync,
            normalized_role,
            normalized_type,
            normalized_name,
        )

    async def revoke_role_permission(
        self,
        role_name: str,
        permission_type: str,
        name: str,
    ) -> None:
        normalized_role = self._normalize_role_name(role_name)
        normalized_type, normalized_name = self._normalize_permission_parts(permission_type, name)
        await asyncio.to_thread(
            self._revoke_role_permission_sync,
            normalized_role,
            normalized_type,
            normalized_name,
        )

    async def get_user_roles(self, user_id: int) -> list[str]:
        return await asyncio.to_thread(self._get_user_roles_sync, user_id)

    async def get_user_permission_report(
        self,
        user_id: int,
    ) -> dict[str, list[dict[str, object]]]:
        return await asyncio.to_thread(self._get_user_permission_report_sync, user_id)

    def _ensure_schema_sync(self) -> None:
        with self._psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(CREATE_TABLES_SQL)
            conn.commit()

    def _has_permission_sync(
        self,
        user_id: int,
        permission_type: str,
        name: str,
    ) -> bool:
        with self._psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    HAS_PERMISSION_SQL,
                    (permission_type, name, user_id, user_id),
                )
                row = cur.fetchone()
                if not row:
                    return False
                return bool(row[0])

    @staticmethod
    def _normalize_role_name(role_name: str) -> str:
        normalized = role_name.strip().lower()
        if not normalized:
            raise ValueError("Role name must not be empty.")
        return normalized

    @staticmethod
    def _normalize_permission_parts(permission_type: str, name: str) -> tuple[str, str]:
        normalized_type = permission_type.strip().lower()
        normalized_name = name.strip().lower()
        if normalized_type not in {"general", "command", "assistant"}:
            raise ValueError("permission_type must be one of: general, command, assistant.")
        if not normalized_name:
            raise ValueError("permission name must not be empty.")
        return normalized_type, normalized_name

    def _ensure_permission_id_sync(self, permission_type: str, name: str) -> int:
        with self._psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(UPSERT_PERMISSION_SQL, (permission_type, name))
                row = cur.fetchone()
                if not row:
                    raise RuntimeError("Failed to upsert permission.")
                permission_id = int(row[0])
            conn.commit()
            return permission_id

    def _get_permission_id_sync(self, permission_type: str, name: str) -> int | None:
        with self._psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(GET_PERMISSION_ID_SQL, (permission_type, name))
                row = cur.fetchone()
                if not row:
                    return None
                return int(row[0])

    def _ensure_role_id_sync(self, role_name: str) -> int:
        with self._psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(CREATE_ROLE_SQL, (role_name,))
                cur.execute(GET_ROLE_ID_SQL, (role_name,))
                row = cur.fetchone()
                if not row:
                    raise RuntimeError(f"Failed to resolve role id for: {role_name}")
                role_id = int(row[0])
            conn.commit()
            return role_id

    def _set_user_permission_sync(
        self,
        user_id: int,
        permission_type: str,
        name: str,
        is_active: bool,
    ) -> None:
        permission_id = self._ensure_permission_id_sync(permission_type, name)
        with self._psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    UPSERT_USER_PERMISSION_SQL,
                    (user_id, permission_id, is_active),
                )
            conn.commit()

    def _create_role_sync(self, role_name: str) -> None:
        self._ensure_role_id_sync(role_name)

    def _assign_role_sync(self, user_id: int, role_name: str) -> None:
        role_id = self._ensure_role_id_sync(role_name)
        with self._psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(ASSIGN_ROLE_SQL, (user_id, role_id))
            conn.commit()

    def _grant_role_permission_sync(
        self,
        role_name: str,
        permission_type: str,
        name: str,
    ) -> None:
        role_id = self._ensure_role_id_sync(role_name)
        permission_id = self._ensure_permission_id_sync(permission_type, name)
        with self._psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(GRANT_ROLE_PERMISSION_SQL, (role_id, permission_id))
            conn.commit()

    def _revoke_role_permission_sync(
        self,
        role_name: str,
        permission_type: str,
        name: str,
    ) -> None:
        role_id = self._ensure_role_id_sync(role_name)
        permission_id = self._get_permission_id_sync(permission_type, name)
        if permission_id is None:
            return
        with self._psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(REVOKE_ROLE_PERMISSION_SQL, (role_id, permission_id))
            conn.commit()

    def _get_user_roles_sync(self, user_id: int) -> list[str]:
        with self._psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(GET_USER_ROLES_SQL, (user_id,))
                rows = cur.fetchall()
                return [str(row[0]) for row in rows]

    def _get_user_permission_report_sync(
        self,
        user_id: int,
    ) -> dict[str, list[dict[str, object]]]:
        with self._psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(GET_USER_OVERRIDES_SQL, (user_id,))
                override_rows = cur.fetchall()
                cur.execute(GET_USER_ROLE_PERMISSIONS_SQL, (user_id,))
                role_rows = cur.fetchall()

        user_overrides: list[dict[str, object]] = [
            {
                "type": str(row[0]),
                "name": str(row[1]),
                "is_active": bool(row[2]),
            }
            for row in override_rows
        ]
        role_permissions: list[dict[str, object]] = [
            {
                "role": str(row[0]),
                "type": str(row[1]),
                "name": str(row[2]),
            }
            for row in role_rows
        ]

        override_map: dict[tuple[str, str], bool] = {
            (str(item["type"]), str(item["name"])): bool(item["is_active"])
            for item in user_overrides
        }
        role_map: dict[tuple[str, str], set[str]] = {}
        for item in role_permissions:
            key = (str(item["type"]), str(item["name"]))
            role_map.setdefault(key, set()).add(str(item["role"]))

        all_keys = sorted(set(override_map.keys()) | set(role_map.keys()))
        effective: list[dict[str, object]] = []
        for perm_type, perm_name in all_keys:
            if (perm_type, perm_name) in override_map:
                is_active = override_map[(perm_type, perm_name)]
                source = "user_override"
            else:
                is_active = True
                source = "role"
            roles = sorted(role_map.get((perm_type, perm_name), set()))
            effective.append(
                {
                    "type": perm_type,
                    "name": perm_name,
                    "is_active": is_active,
                    "source": source,
                    "roles": roles,
                }
            )

        return {
            "user_overrides": user_overrides,
            "role_permissions": role_permissions,
            "effective": effective,
        }
