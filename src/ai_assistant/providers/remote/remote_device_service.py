from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from ai_assistant.providers.remote.interfaces import RemoteDeviceStore
from ai_assistant.providers.remote.types import LinkDeviceResult, PendingLinkCode, RemoteClientRecord, UserRemoteClient


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RemoteDeviceError(RuntimeError):
    pass


class LinkCodeNotFoundError(RemoteDeviceError):
    pass


class OwnershipError(RemoteDeviceError):
    pass


class AccessDeniedError(RemoteDeviceError):
    pass


class RemoteDeviceService:
    def __init__(
        self,
        store: RemoteDeviceStore,
        *,
        link_code_ttl_seconds: int = 300,
    ) -> None:
        if link_code_ttl_seconds <= 0:
            raise ValueError("link_code_ttl_seconds must be > 0")
        self._store = store
        self._link_code_ttl_seconds = link_code_ttl_seconds

    async def issue_link_code(
        self,
        *,
        session_id: str,
        client_id: str,
        display_name: str,
        platform: str,
        server_id: str,
    ) -> PendingLinkCode:
        await self._store.delete_expired_link_codes(_utc_now())
        code = self._generate_link_code()
        now = _utc_now()
        expires_at = now + timedelta(seconds=self._link_code_ttl_seconds)
        link = PendingLinkCode(
            code=code,
            session_id=session_id,
            client_id=self._normalize_client_id(client_id),
            display_name=self._normalize_display_name(display_name, client_id),
            platform=self._normalize_platform(platform),
            server_id=self._normalize_server_id(server_id),
            expires_at=expires_at,
        )
        await self._store.put_link_code(link)
        return link

    async def link_device(self, *, user_id: int, code: str) -> LinkDeviceResult:
        normalized_code = self._normalize_code(code)
        link = await self._store.consume_link_code(normalized_code, _utc_now())
        if link is None:
            raise LinkCodeNotFoundError("Invalid or expired link code.")

        existing = await self._store.get_client(link.client_id)
        if existing is not None and existing.owner_user_id != user_id:
            raise OwnershipError("Device is already linked to another owner.")

        now = _utc_now()
        auth_token = self._generate_auth_token()
        token_hash = self._hash_token(auth_token)
        client = await self._store.upsert_client(
            client_id=link.client_id,
            owner_user_id=user_id,
            display_name=link.display_name,
            platform=link.platform,
            server_id=link.server_id,
            token_hash=token_hash,
            now=now,
        )

        default_client_id = await self._store.get_user_default_client_id(user_id)
        default_assigned = False
        if not default_client_id:
            await self._store.set_user_default_client_id(user_id, client.client_id)
            default_assigned = True

        return LinkDeviceResult(
            session_id=link.session_id,
            client=client,
            auth_token=auth_token,
            default_assigned=default_assigned,
        )

    async def authenticate_client(
        self,
        *,
        client_id: str,
        server_id: str,
        auth_token: str,
    ) -> RemoteClientRecord | None:
        normalized_client_id = self._normalize_client_id(client_id)
        normalized_server_id = self._normalize_server_id(server_id)
        token_hash = self._hash_token(auth_token)
        return await self._store.authenticate_client(
            client_id=normalized_client_id,
            server_id=normalized_server_id,
            token_hash=token_hash,
        )

    async def mark_client_seen(self, client_id: str) -> None:
        await self._store.touch_client_last_seen(self._normalize_client_id(client_id), _utc_now())

    async def list_user_clients(self, user_id: int) -> list[UserRemoteClient]:
        return await self._store.list_user_clients(user_id)

    async def user_has_access(self, *, user_id: int, client_id: str) -> bool:
        normalized_client_id = self._normalize_client_id(client_id)
        return await self._store.has_user_access(user_id, normalized_client_id)

    async def get_user_default_client_id(self, user_id: int) -> str | None:
        return await self._store.get_user_default_client_id(user_id)

    async def set_default_client(self, user_id: int, client_id: str | None) -> None:
        if client_id is None:
            await self._store.set_user_default_client_id(user_id, None)
            return

        normalized_client_id = self._normalize_client_id(client_id)
        if not await self._store.has_user_access(user_id, normalized_client_id):
            raise AccessDeniedError("No access to this client.")
        await self._store.set_user_default_client_id(user_id, normalized_client_id)

    async def share_client(self, *, owner_user_id: int, client_id: str, target_user_id: int) -> None:
        client = await self._require_owner(owner_user_id, client_id)
        if target_user_id == client.owner_user_id:
            return
        await self._store.grant_client_access(
            client_id=client.client_id,
            user_id=target_user_id,
            granted_by=owner_user_id,
            now=_utc_now(),
        )

    async def revoke_client_access(
        self,
        *,
        owner_user_id: int,
        client_id: str,
        target_user_id: int,
    ) -> None:
        client = await self._require_owner(owner_user_id, client_id)
        if target_user_id == client.owner_user_id:
            raise AccessDeniedError("Owner access cannot be revoked.")
        await self._store.revoke_client_access(client_id=client.client_id, user_id=target_user_id)

    async def unlink_client(self, *, owner_user_id: int, client_id: str) -> None:
        client = await self._require_owner(owner_user_id, client_id)
        await self._store.remove_client(client.client_id)

    async def unlink_client_by_token(self, *, client_id: str, server_id: str, auth_token: str) -> None:
        client = await self.authenticate_client(
            client_id=client_id,
            server_id=server_id,
            auth_token=auth_token,
        )
        if client is None:
            raise AccessDeniedError("Client authentication failed.")
        await self._store.remove_client(client.client_id)

    async def _require_owner(self, user_id: int, client_id: str) -> RemoteClientRecord:
        normalized_client_id = self._normalize_client_id(client_id)
        client = await self._store.get_client(normalized_client_id)
        if client is None:
            raise LinkCodeNotFoundError("Client is not linked.")
        if client.owner_user_id != user_id:
            raise OwnershipError("Only owner can manage this client.")
        return client

    @staticmethod
    def _normalize_code(code: str) -> str:
        normalized = code.strip().upper().replace(" ", "")
        if not normalized:
            raise LinkCodeNotFoundError("Link code is required.")
        return normalized

    @staticmethod
    def _normalize_client_id(client_id: str) -> str:
        normalized = client_id.strip().lower()
        if not normalized:
            raise ValueError("client_id must not be empty")
        return normalized

    @staticmethod
    def _normalize_display_name(display_name: str, client_id: str) -> str:
        normalized = display_name.strip()
        if normalized:
            return normalized
        return client_id.strip() or "device"

    @staticmethod
    def _normalize_platform(platform: str) -> str:
        normalized = platform.strip().lower() or "unknown"
        return normalized

    @staticmethod
    def _normalize_server_id(server_id: str) -> str:
        normalized = server_id.strip().lower()
        if not normalized:
            raise ValueError("server_id must not be empty")
        return normalized

    @staticmethod
    def _generate_link_code() -> str:
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        return "".join(secrets.choice(alphabet) for _ in range(8))

    @staticmethod
    def _generate_auth_token() -> str:
        return secrets.token_urlsafe(32)

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
