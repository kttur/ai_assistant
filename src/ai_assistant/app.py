from __future__ import annotations

import logging

from ai_assistant.bootstrap import build_channel_module
from ai_assistant.config.settings import Settings
from ai_assistant.logging_utils import configure_logging

logger = logging.getLogger(__name__)


def run() -> None:
    settings = Settings.from_env()
    log_level = configure_logging()
    logger.info(
        "Starting AI assistant: channel=%s llm_provider=%s log_level=%s",
        settings.assistant_channel,
        settings.llm_provider,
        log_level,
    )
    module = build_channel_module(settings)
    module.run()
