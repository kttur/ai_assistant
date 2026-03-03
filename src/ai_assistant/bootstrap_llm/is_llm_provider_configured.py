from __future__ import annotations

from ai_assistant.config.settings import Settings


def is_llm_provider_configured(provider: str, settings: Settings) -> bool:
    if provider == "mock":
        return True
    if provider == "openai":
        return bool(settings.openai_api_key.strip())
    if provider == "anthropic":
        return bool(settings.anthropic_api_key.strip())
    if provider == "ollama":
        return True
    return False
