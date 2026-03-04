from __future__ import annotations

from datetime import datetime

from ai_assistant.providers.remote.interfaces import RemoteDeviceStore
from ai_assistant.providers.remote.types import PendingLinkCode, RemoteClientRecord, UserRemoteClient


class InMemoryRemoteDeviceStore(RemoteDeviceStore):
    def __init__(self) -> None:
        self._link_codes: dict[str, PendingLinkCode] = {}
        self._clients: dict[str, RemoteClientRecord] = {}
        self._client_tokens: dict[str, str] = {}
        self._client_shares: dict[str, dict[int, int]] = {}
        self._user_defaults: dict[int, str] = {}

    async def put_link_code(self, link: PendingLinkCode) -> None:
        self._link_codes[link.code] = link

    async def consume_link_code(self, code: str, now: datetime) -> PendingLinkCode | None:
        link = self._link_codes.get(code)
        if link is None:
            return None
        if link.expires_at <= now:
            self._link_codes.pop(code, None)
            return None
        self._link_codes.pop(code, None)
        return link

    async def delete_expired_link_codes(self, now: datetime) -> int:
        expired = [code for code, link in self._link_codes.items() if link.expires_at <= now]
        for code in expired:
            self._link_codes.pop(code, None)
        return len(expired)

    async def get_client(self, client_id: str) -> RemoteClientRecord | None:
        return self._clients.get(client_id)

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
        existing = self._clients.get(client_id)
        created_at = existing.created_at if existing is not None else now
        last_seen_at = existing.last_seen_at if existing is not None else None
        record = RemoteClientRecord(
            client_id=client_id,
            owner_user_id=owner_user_id,
            display_name=display_name,
            platform=platform,
            server_id=server_id,
            created_at=created_at,
            updated_at=now,
            last_seen_at=last_seen_at,
        )
        self._clients[client_id] = record
        self._client_tokens[client_id] = token_hash
        self._client_shares.setdefault(client_id, {})
        return record

    async def authenticate_client(
        self,
        *,
        client_id: str,
        server_id: str,
        token_hash: str,
    ) -> RemoteClientRecord | None:
        client = self._clients.get(client_id)
        if client is None:
            return None
        if client.server_id != server_id:
            return None
        if self._client_tokens.get(client_id) != token_hash:
            return None
        return client

    async def touch_client_last_seen(self, client_id: str, now: datetime) -> None:
        client = self._clients.get(client_id)
        if client is None:
            return
        self._clients[client_id] = RemoteClientRecord(
            client_id=client.client_id,
            owner_user_id=client.owner_user_id,
            display_name=client.display_name,
            platform=client.platform,
            server_id=client.server_id,
            created_at=client.created_at,
            updated_at=now,
            last_seen_at=now,
        )

    async def list_user_clients(self, user_id: int) -> list[UserRemoteClient]:
        default_client_id = self._user_defaults.get(user_id)
        result: list[UserRemoteClient] = []
        for client in self._clients.values():
            is_owner = client.owner_user_id == user_id
            is_shared = user_id in self._client_shares.get(client.client_id, {})
            if not is_owner and not is_shared:
                continue
            result.append(
                UserRemoteClient(
                    client_id=client.client_id,
                    display_name=client.display_name,
                    platform=client.platform,
                    server_id=client.server_id,
                    is_owner=is_owner,
                    is_default=default_client_id == client.client_id,
                    last_seen_at=client.last_seen_at,
                )
            )

        result.sort(key=lambda item: (not item.is_default, item.display_name, item.client_id))
        return result

    async def get_user_default_client_id(self, user_id: int) -> str | None:
        return self._user_defaults.get(user_id)

    async def set_user_default_client_id(self, user_id: int, client_id: str | None) -> None:
        if not client_id:
            self._user_defaults.pop(user_id, None)
            return
        self._user_defaults[user_id] = client_id

    async def has_user_access(self, user_id: int, client_id: str) -> bool:
        client = self._clients.get(client_id)
        if client is None:
            return False
        if client.owner_user_id == user_id:
            return True
        return user_id in self._client_shares.get(client_id, {})

    async def grant_client_access(
        self,
        *,
        client_id: str,
        user_id: int,
        granted_by: int,
        now: datetime,
    ) -> None:
        del now
        self._client_shares.setdefault(client_id, {})[user_id] = granted_by

    async def revoke_client_access(self, *, client_id: str, user_id: int) -> None:
        shares = self._client_shares.get(client_id)
        if shares is None:
            return
        shares.pop(user_id, None)
        if self._user_defaults.get(user_id) == client_id:
            self._user_defaults.pop(user_id, None)

    async def remove_client(self, client_id: str) -> None:
        self._clients.pop(client_id, None)
        self._client_tokens.pop(client_id, None)
        self._client_shares.pop(client_id, None)
        self._link_codes = {
            code: link for code, link in self._link_codes.items() if link.client_id != client_id
        }
        users_to_clear = [
            user_id
            for user_id, default_client_id in self._user_defaults.items()
            if default_client_id == client_id
        ]
        for user_id in users_to_clear:
            self._user_defaults.pop(user_id, None)
