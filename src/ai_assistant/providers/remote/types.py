from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, frozen=True)
class PendingLinkCode:
    code: str
    session_id: str
    client_id: str
    display_name: str
    platform: str
    server_id: str
    expires_at: datetime


@dataclass(slots=True, frozen=True)
class RemoteClientRecord:
    client_id: str
    owner_user_id: int
    display_name: str
    platform: str
    server_id: str
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime | None


@dataclass(slots=True, frozen=True)
class UserRemoteClient:
    client_id: str
    display_name: str
    platform: str
    server_id: str
    is_owner: bool
    is_default: bool
    last_seen_at: datetime | None


@dataclass(slots=True, frozen=True)
class LinkDeviceResult:
    session_id: str
    client: RemoteClientRecord
    auth_token: str
    default_assigned: bool
