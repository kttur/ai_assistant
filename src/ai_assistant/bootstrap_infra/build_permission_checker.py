from __future__ import annotations

from ai_assistant.config.settings import Settings
from ai_assistant.core.interfaces import PermissionAdminStore
from ai_assistant.providers.permissions.in_memory_permission_checker import InMemoryPermissionChecker
from ai_assistant.providers.permissions.postgres_permission_checker import PostgresPermissionChecker


def build_permission_checker(settings: Settings) -> PermissionAdminStore | None:
    backend = settings.permissions_backend.strip().lower()
    if backend == "auto":
        if settings.user_settings_backend.strip().lower() == "postgres":
            backend = "postgres"
        else:
            backend = "disabled"
    if backend in {"", "none", "disabled"}:
        return None
    if backend == "memory":
        return InMemoryPermissionChecker(allow_all=False)
    if backend == "postgres":
        return PostgresPermissionChecker(dsn=settings.postgres_dsn)
    raise ValueError(f"Unsupported permissions backend: {settings.permissions_backend}")
