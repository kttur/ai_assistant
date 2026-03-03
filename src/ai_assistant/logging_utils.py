from __future__ import annotations

import logging
import os
from collections.abc import Iterable

DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
_VALID_LOG_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}


def configure_logging() -> str:
    raw_level = os.getenv("AI_ASSISTANT_LOG_LEVEL", DEFAULT_LOG_LEVEL)
    level_name = raw_level.strip().upper() or DEFAULT_LOG_LEVEL
    if level_name not in _VALID_LOG_LEVELS:
        level_name = DEFAULT_LOG_LEVEL

    log_format = os.getenv("AI_ASSISTANT_LOG_FORMAT", DEFAULT_LOG_FORMAT).strip() or DEFAULT_LOG_FORMAT
    logging.basicConfig(
        level=getattr(logging, level_name, logging.INFO),
        format=log_format,
        force=True,
    )
    return level_name


def text_preview(text: str, *, max_len: int = 160) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_len:
        return normalized
    return f"{normalized[: max_len - 3]}..."


def format_model_chain(items: Iterable[tuple[str, str]]) -> str:
    chain = [f"{provider}:{model}" for provider, model in items]
    if not chain:
        return "(empty)"
    return " -> ".join(chain)
