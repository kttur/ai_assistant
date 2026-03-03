from __future__ import annotations


def is_truthy_value(value: str | None) -> bool:
    if value is None:
        return False
    normalized = value.strip().lower()
    return normalized in {"1", "true", "on", "yes", "enabled"}
