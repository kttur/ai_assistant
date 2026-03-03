from __future__ import annotations


def format_username(username: str | None) -> str:
    if username:
        return f"@{username}"
    return "(no username)"
