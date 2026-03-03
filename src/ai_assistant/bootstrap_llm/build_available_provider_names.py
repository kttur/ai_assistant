from __future__ import annotations

from ai_assistant.config.settings import Settings
from ai_assistant.bootstrap_llm.constants import SUPPORTED_LLM_PROVIDERS
from ai_assistant.bootstrap_llm.dedupe_keep_order import dedupe_keep_order
from ai_assistant.bootstrap_llm.is_llm_provider_configured import is_llm_provider_configured


def build_available_provider_names(settings: Settings) -> tuple[str, ...]:
    requested = [item.strip().lower() for item in settings.llm_available_providers]
    default_provider = settings.llm_provider.strip().lower()
    if default_provider not in SUPPORTED_LLM_PROVIDERS:
        raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")
    if not is_llm_provider_configured(default_provider, settings):
        raise ValueError(f"Default LLM provider is not configured: {settings.llm_provider}")
    requested.append(default_provider)

    filtered: list[str] = []
    for provider in requested:
        if provider not in SUPPORTED_LLM_PROVIDERS:
            continue
        if not is_llm_provider_configured(provider, settings):
            continue
        filtered.append(provider)

    if not filtered:
        return ("mock",)
    return dedupe_keep_order(filtered)
