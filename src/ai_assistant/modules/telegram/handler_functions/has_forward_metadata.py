from __future__ import annotations


def has_forward_metadata(message) -> bool:
    return any(
        getattr(message, attr, None) is not None
        for attr in ("forward_origin", "forward_from", "forward_sender_name")
    )
