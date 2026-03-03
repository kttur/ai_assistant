from __future__ import annotations

import asyncio

from ai_assistant.providers.permissions.postgres_permission_checker_helpers import (
    ALLOWED_PERMISSION_TYPES,
    build_permission_report,
    normalize_permission_parts,
    normalize_role_name,
)
from ai_assistant.providers.permissions.postgres_permission_checker_sql import (
    ASSIGN_ROLE_SQL,
    CREATE_ROLE_SQL,
    CREATE_TABLES_SQL,
    GET_PERMISSION_ID_SQL,
    GET_ROLE_ID_SQL,
    GET_USER_OVERRIDES_SQL,
    GET_USER_ROLE_PERMISSIONS_SQL,
    GET_USER_ROLES_SQL,
    GRANT_ROLE_PERMISSION_SQL,
    HAS_PERMISSION_SQL,
    REVOKE_ROLE_PERMISSION_SQL,
    UPSERT_PERMISSION_SQL,
    UPSERT_USER_PERMISSION_SQL,
)


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
        if normalized_type not in ALLOWED_PERMISSION_TYPES:
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
        return build_permission_report(override_rows=override_rows, role_rows=role_rows)

    @staticmethod
    def _normalize_role_name(role_name: str) -> str:
        return normalize_role_name(role_name)

    @staticmethod
    def _normalize_permission_parts(permission_type: str, name: str) -> tuple[str, str]:
        return normalize_permission_parts(permission_type, name)
