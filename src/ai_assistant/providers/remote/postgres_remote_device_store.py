from __future__ import annotations

import asyncio
from datetime import datetime

from ai_assistant.providers.remote.interfaces import RemoteDeviceStore
from ai_assistant.providers.remote.postgres_remote_device_store_sql import (
    AUTHENTICATE_CLIENT_SQL,
    CONSUME_LINK_CODE_SQL,
    CREATE_TABLES_SQL,
    DELETE_EXPIRED_LINK_CODES_SQL,
    DELETE_USER_DEFAULT_CLIENT_SQL,
    GET_CLIENT_SQL,
    GET_USER_DEFAULT_CLIENT_SQL,
    GRANT_CLIENT_ACCESS_SQL,
    HAS_USER_ACCESS_SQL,
    LIST_USER_CLIENTS_SQL,
    PUT_LINK_CODE_SQL,
    REMOVE_CLIENT_SQL,
    REVOKE_CLIENT_ACCESS_SQL,
    SET_USER_DEFAULT_CLIENT_SQL,
    TOUCH_CLIENT_LAST_SEEN_SQL,
    UPSERT_CLIENT_SQL,
)
from ai_assistant.providers.remote.types import PendingLinkCode, RemoteClientRecord, UserRemoteClient


class PostgresRemoteDeviceStore(RemoteDeviceStore):
    def __init__(self, dsn: str) -> None:
        if not dsn.strip():
            raise ValueError("POSTGRES_DSN is required for postgres remote device store.")
        self._dsn = dsn
        try:
            import psycopg  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "psycopg is not installed. Install project with postgres extra: pip install -e .[postgres]"
            ) from exc
        self._psycopg = psycopg
        self._ensure_schema_sync()

    async def put_link_code(self, link: PendingLinkCode) -> None:
        await asyncio.to_thread(self._put_link_code_sync, link)

    async def consume_link_code(self, code: str, now: datetime) -> PendingLinkCode | None:
        return await asyncio.to_thread(self._consume_link_code_sync, code, now)

    async def delete_expired_link_codes(self, now: datetime) -> int:
        return await asyncio.to_thread(self._delete_expired_link_codes_sync, now)

    async def get_client(self, client_id: str) -> RemoteClientRecord | None:
        return await asyncio.to_thread(self._get_client_sync, client_id)

    async def upsert_client(
        self,
        *,
        client_id: str,
        owner_user_id: int,
        display_name: str,
        platform: str,
        server_id: str,
        token_hash: str,
        now: datetime,
    ) -> RemoteClientRecord:
        return await asyncio.to_thread(
            self._upsert_client_sync,
            client_id,
            owner_user_id,
            display_name,
            platform,
            server_id,
            token_hash,
            now,
        )

    async def authenticate_client(
        self,
        *,
        client_id: str,
        server_id: str,
        token_hash: str,
    ) -> RemoteClientRecord | None:
        return await asyncio.to_thread(
            self._authenticate_client_sync,
            client_id,
            server_id,
            token_hash,
        )

    async def touch_client_last_seen(self, client_id: str, now: datetime) -> None:
        await asyncio.to_thread(self._touch_client_last_seen_sync, client_id, now)

    async def list_user_clients(self, user_id: int) -> list[UserRemoteClient]:
        return await asyncio.to_thread(self._list_user_clients_sync, user_id)

    async def get_user_default_client_id(self, user_id: int) -> str | None:
        return await asyncio.to_thread(self._get_user_default_client_id_sync, user_id)

    async def set_user_default_client_id(self, user_id: int, client_id: str | None) -> None:
        await asyncio.to_thread(self._set_user_default_client_id_sync, user_id, client_id)

    async def has_user_access(self, user_id: int, client_id: str) -> bool:
        return await asyncio.to_thread(self._has_user_access_sync, user_id, client_id)

    async def grant_client_access(
        self,
        *,
        client_id: str,
        user_id: int,
        granted_by: int,
        now: datetime,
    ) -> None:
        await asyncio.to_thread(
            self._grant_client_access_sync,
            client_id,
            user_id,
            granted_by,
            now,
        )

    async def revoke_client_access(self, *, client_id: str, user_id: int) -> None:
        await asyncio.to_thread(self._revoke_client_access_sync, client_id, user_id)

    async def remove_client(self, client_id: str) -> None:
        await asyncio.to_thread(self._remove_client_sync, client_id)

    def _ensure_schema_sync(self) -> None:
        with self._psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(CREATE_TABLES_SQL)
            conn.commit()

    def _put_link_code_sync(self, link: PendingLinkCode) -> None:
        with self._psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    PUT_LINK_CODE_SQL,
                    (
                        link.code,
                        link.session_id,
                        link.client_id,
                        link.display_name,
                        link.platform,
                        link.server_id,
                        link.expires_at,
                    ),
                )
            conn.commit()

    def _consume_link_code_sync(self, code: str, now: datetime) -> PendingLinkCode | None:
        with self._psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(CONSUME_LINK_CODE_SQL, (code, now))
                row = cur.fetchone()
            conn.commit()

        if not row:
            return None

        return PendingLinkCode(
            code=str(row[0]),
            session_id=str(row[1]),
            client_id=str(row[2]),
            display_name=str(row[3]),
            platform=str(row[4]),
            server_id=str(row[5]),
            expires_at=row[6],
        )

    def _delete_expired_link_codes_sync(self, now: datetime) -> int:
        with self._psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(DELETE_EXPIRED_LINK_CODES_SQL, (now,))
                removed = int(cur.rowcount or 0)
            conn.commit()
        return removed

    def _get_client_sync(self, client_id: str) -> RemoteClientRecord | None:
        with self._psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(GET_CLIENT_SQL, (client_id,))
                row = cur.fetchone()
        if not row:
            return None
        return self._client_from_row(row)

    def _upsert_client_sync(
        self,
        client_id: str,
        owner_user_id: int,
        display_name: str,
        platform: str,
        server_id: str,
        token_hash: str,
        now: datetime,
    ) -> RemoteClientRecord:
        with self._psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    UPSERT_CLIENT_SQL,
                    (
                        client_id,
                        owner_user_id,
                        display_name,
                        platform,
                        server_id,
                        token_hash,
                        now,
                        now,
                    ),
                )
                row = cur.fetchone()
                if not row:
                    raise RuntimeError("Failed to upsert remote client.")
            conn.commit()

        return self._client_from_row(row)

    def _authenticate_client_sync(
        self,
        client_id: str,
        server_id: str,
        token_hash: str,
    ) -> RemoteClientRecord | None:
        with self._psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(AUTHENTICATE_CLIENT_SQL, (client_id, server_id, token_hash))
                row = cur.fetchone()
        if not row:
            return None
        return self._client_from_row(row)

    def _touch_client_last_seen_sync(self, client_id: str, now: datetime) -> None:
        with self._psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(TOUCH_CLIENT_LAST_SEEN_SQL, (now, now, client_id))
            conn.commit()

    def _list_user_clients_sync(self, user_id: int) -> list[UserRemoteClient]:
        with self._psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(LIST_USER_CLIENTS_SQL, (user_id, user_id, user_id, user_id, user_id))
                rows = cur.fetchall()

        return [
            UserRemoteClient(
                client_id=str(row[0]),
                display_name=str(row[1]),
                platform=str(row[2]),
                server_id=str(row[3]),
                is_owner=bool(row[4]),
                is_default=bool(row[5]),
                last_seen_at=row[6],
            )
            for row in rows
        ]

    def _get_user_default_client_id_sync(self, user_id: int) -> str | None:
        with self._psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(GET_USER_DEFAULT_CLIENT_SQL, (user_id,))
                row = cur.fetchone()
        if not row:
            return None
        return str(row[0])

    def _set_user_default_client_id_sync(self, user_id: int, client_id: str | None) -> None:
        with self._psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                if client_id is None:
                    cur.execute(DELETE_USER_DEFAULT_CLIENT_SQL, (user_id,))
                else:
                    cur.execute(SET_USER_DEFAULT_CLIENT_SQL, (user_id, client_id))
            conn.commit()

    def _has_user_access_sync(self, user_id: int, client_id: str) -> bool:
        with self._psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(HAS_USER_ACCESS_SQL, (user_id, client_id, user_id, user_id))
                row = cur.fetchone()
        if not row:
            return False
        return bool(row[0])

    def _grant_client_access_sync(
        self,
        client_id: str,
        user_id: int,
        granted_by: int,
        now: datetime,
    ) -> None:
        with self._psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(GRANT_CLIENT_ACCESS_SQL, (client_id, user_id, granted_by, now))
            conn.commit()

    def _revoke_client_access_sync(self, client_id: str, user_id: int) -> None:
        with self._psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(REVOKE_CLIENT_ACCESS_SQL, (client_id, user_id))
                cur.execute(GET_USER_DEFAULT_CLIENT_SQL, (user_id,))
                default_row = cur.fetchone()
                if default_row and str(default_row[0]) == client_id:
                    cur.execute(DELETE_USER_DEFAULT_CLIENT_SQL, (user_id,))
            conn.commit()

    def _remove_client_sync(self, client_id: str) -> None:
        with self._psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(REMOVE_CLIENT_SQL, (client_id,))
            conn.commit()

    @staticmethod
    def _client_from_row(row: tuple[object, ...]) -> RemoteClientRecord:
        return RemoteClientRecord(
            client_id=str(row[0]),
            owner_user_id=int(row[1]),
            display_name=str(row[2]),
            platform=str(row[3]),
            server_id=str(row[4]),
            created_at=row[5],
            updated_at=row[6],
            last_seen_at=row[7],
        )
