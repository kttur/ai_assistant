from __future__ import annotations

from ai_assistant.config.settings import Settings
from ai_assistant.core.interfaces import LLMProvider
from ai_assistant.bootstrap_llm.build_single_llm_provider import build_single_llm_provider


def build_llm_provider_instances(
    settings: Settings,
    provider_names: tuple[str, ...],
) -> dict[str, LLMProvider]:
    instances: dict[str, LLMProvider] = {}
    default_provider = settings.llm_provider.strip().lower()

    for provider in provider_names:
        try:
            instances[provider] = build_single_llm_provider(provider, settings)
        except Exception:
            if provider == default_provider:
                raise
            continue

    if not instances:
        raise RuntimeError("No available LLM providers are configured.")
    return instances
