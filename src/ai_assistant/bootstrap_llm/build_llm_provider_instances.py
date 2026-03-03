from __future__ import annotations

import logging

from ai_assistant.config.settings import Settings
from ai_assistant.core.interfaces import LLMProvider
from ai_assistant.bootstrap_llm.build_single_llm_provider import build_single_llm_provider

logger = logging.getLogger(__name__)


def build_llm_provider_instances(
    settings: Settings,
    provider_names: tuple[str, ...],
) -> dict[str, LLMProvider]:
    instances: dict[str, LLMProvider] = {}
    default_provider = settings.llm_provider.strip().lower()

    for provider in provider_names:
        try:
            instances[provider] = build_single_llm_provider(provider, settings)
            logger.info("LLM provider initialized: %s", provider)
        except Exception as exc:
            if provider == default_provider:
                logger.exception("Failed to initialize default LLM provider: %s", provider)
                raise
            logger.warning(
                "Skipping unavailable optional LLM provider %s: %s",
                provider,
                exc,
            )
            continue

    if not instances:
        logger.error("No available LLM providers are configured.")
        raise RuntimeError("No available LLM providers are configured.")
    return instances
