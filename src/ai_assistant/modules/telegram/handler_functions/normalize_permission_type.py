from __future__ import annotations


def normalize_permission_type(value: str, valid_types: set[str]) -> str | None:
    normalized = value.strip().lower()
    if normalized in valid_types:
        return normalized
    return None
