from __future__ import annotations

from ai_assistant.modules.telegram.handler_functions.format_username import format_username


def render_user_section(title: str, user) -> str:
    user_id = getattr(user, "id", None)
    username = getattr(user, "username", None)
    first_name = getattr(user, "first_name", None)
    last_name = getattr(user, "last_name", None)
    full_name = " ".join(part for part in [first_name, last_name] if part).strip()

    lines = [title]
    if user_id is None:
        lines.append("ID: (unknown)")
    else:
        lines.append(f"ID: {user_id}")
    lines.append(f"Username: {format_username(username)}")
    if full_name:
        lines.append(f"Name: {full_name}")
    return "\n".join(lines)
