from __future__ import annotations


def split_telegram_text_chunks(text: str, max_chars: int = 4096) -> list[str]:
    if max_chars < 1:
        raise ValueError("max_chars must be greater than zero.")

    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + max_chars, text_len)
        if end < text_len:
            split_at = text.rfind("\n", start + 1, end + 1)
            if split_at <= start:
                split_at = text.rfind(" ", start + 1, end + 1)
            if split_at <= start:
                split_at = end
            else:
                split_at += 1
        else:
            split_at = end

        chunks.append(text[start:split_at])
        start = split_at

    return chunks
