from __future__ import annotations


def extract_model_provider_from_permission(permission_name: str | None) -> str | None:
    if permission_name is None:
        return None
    normalized = permission_name.strip().lower()
    prefix = "llm.model."
    if not normalized.startswith(prefix):
        return None
    tail = normalized[len(prefix) :]
    if ":" not in tail:
        return None
    provider, _ = tail.split(":", 1)
    provider_name = provider.strip()
    return provider_name or None
