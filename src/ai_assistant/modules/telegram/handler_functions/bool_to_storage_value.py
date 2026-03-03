from __future__ import annotations


def bool_to_storage_value(enabled: bool) -> str:
    return "on" if enabled else "off"
