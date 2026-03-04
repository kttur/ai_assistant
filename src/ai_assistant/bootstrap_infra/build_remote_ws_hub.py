from __future__ import annotations

from ai_assistant.config.settings import Settings
from ai_assistant.providers.remote import RemoteDeviceService
from ai_assistant.providers.remote.ws_hub import RemoteWebSocketHub


def build_remote_ws_hub(
    settings: Settings,
    device_service: RemoteDeviceService | None,
) -> RemoteWebSocketHub | None:
    if not settings.remote_enabled:
        return None
    if device_service is None:
        return None

    return RemoteWebSocketHub(
        device_service=device_service,
        host=settings.remote_ws_host,
        port=settings.remote_ws_port,
        path=settings.remote_ws_path,
        server_id=settings.remote_server_id,
        request_timeout_seconds=settings.remote_request_timeout_seconds,
        ping_interval_seconds=settings.remote_ping_interval_seconds,
        ping_timeout_seconds=settings.remote_ping_timeout_seconds,
        tls_cert_path=settings.remote_tls_cert_path,
        tls_key_path=settings.remote_tls_key_path,
    )
