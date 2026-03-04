from __future__ import annotations

from datetime import datetime
from typing import Protocol

from ai_assistant.providers.remote.types import PendingLinkCode, RemoteClientRecord, UserRemoteClient


class RemoteDeviceStore(Protocol):
    async def put_link_code(self, link: PendingLinkCode) -> None:
        ...

    async def consume_link_code(self, code: str, now: datetime) -> PendingLinkCode | None:
        ...

    async def delete_expired_link_codes(self, now: datetime) -> int:
        ...

    async def get_client(self, client_id: str) -> RemoteClientRecord | None:
        ...

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
        ...

    async def authenticate_client(
        self,
        *,
        client_id: str,
        server_id: str,
        token_hash: str,
    ) -> RemoteClientRecord | None:
        ...

    async def touch_client_last_seen(self, client_id: str, now: datetime) -> None:
        ...

    async def list_user_clients(self, user_id: int) -> list[UserRemoteClient]:
        ...

    async def get_user_default_client_id(self, user_id: int) -> str | None:
        ...

    async def set_user_default_client_id(self, user_id: int, client_id: str | None) -> None:
        ...

    async def has_user_access(self, user_id: int, client_id: str) -> bool:
        ...

    async def grant_client_access(
        self,
        *,
        client_id: str,
        user_id: int,
        granted_by: int,
        now: datetime,
    ) -> None:
        ...

    async def revoke_client_access(self, *, client_id: str, user_id: int) -> None:
        ...

    async def remove_client(self, client_id: str) -> None:
        ...
