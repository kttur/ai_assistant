from __future__ import annotations

from ai_assistant.modules.telegram.handler_functions.render_user_section import render_user_section


def render_forward_origin_section(message) -> str | None:
    forward_origin = getattr(message, "forward_origin", None)
    if forward_origin is not None:
        origin_user = getattr(forward_origin, "user", None)
        if origin_user is not None:
            return render_user_section("Original author:", origin_user)

        sender_name = getattr(forward_origin, "sender_user_name", None)
        if sender_name:
            return f"Original author:\nID: (hidden)\nName: {sender_name}"

        origin_chat = getattr(forward_origin, "chat", None)
        if origin_chat is not None:
            title = (
                getattr(origin_chat, "title", None)
                or getattr(origin_chat, "username", None)
                or "(unknown)"
            )
            lines = ["Original source chat:", f"Title: {title}"]
            chat_username = getattr(origin_chat, "username", None)
            if chat_username:
                lines.append(f"Username: @{chat_username}")
            chat_id = getattr(origin_chat, "id", None)
            if chat_id is not None:
                lines.append(f"ID: {chat_id}")
            author_signature = getattr(forward_origin, "author_signature", None)
            if author_signature:
                lines.append(f"Author: {author_signature}")
            return "\n".join(lines)

    forward_from = getattr(message, "forward_from", None)
    if forward_from is not None:
        return render_user_section("Original author:", forward_from)

    forward_sender_name = getattr(message, "forward_sender_name", None)
    if forward_sender_name:
        return f"Original author:\nID: (hidden)\nName: {forward_sender_name}"

    return None
