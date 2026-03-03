from __future__ import annotations


def extract_model_provider(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized or ":" not in normalized:
        return None
    provider, _ = normalized.split(":", 1)
    normalized_provider = provider.strip().lower()
    return normalized_provider or None
