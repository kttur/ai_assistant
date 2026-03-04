from __future__ import annotations

from ai_assistant.config.settings import Settings
from ai_assistant.providers.remote import (
    InMemoryRemoteDeviceStore,
    PostgresRemoteDeviceStore,
    RemoteDeviceService,
)


def build_remote_device_service(settings: Settings) -> RemoteDeviceService | None:
    if not settings.remote_enabled:
        return None

    backend = settings.remote_backend.strip().lower()
    if backend in {"", "auto", "postgres"}:
        store = PostgresRemoteDeviceStore(dsn=settings.postgres_dsn)
    elif backend == "memory":
        store = InMemoryRemoteDeviceStore()
    else:
        raise ValueError(f"Unsupported remote backend: {settings.remote_backend}")

    return RemoteDeviceService(
        store=store,
        link_code_ttl_seconds=settings.remote_link_code_ttl_seconds,
    )
