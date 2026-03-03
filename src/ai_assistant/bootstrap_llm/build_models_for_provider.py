from __future__ import annotations

from ai_assistant.config.settings import Settings
from ai_assistant.bootstrap_llm.dedupe_keep_order import dedupe_keep_order


def build_models_for_provider(settings: Settings, provider: str) -> tuple[str, ...]:
    if provider == "openai":
        models = [settings.openai_model.strip()]
        models.extend(item.strip() for item in settings.openai_available_models)
        return dedupe_keep_order(models)
    if provider == "anthropic":
        models = [settings.anthropic_model.strip()]
        models.extend(item.strip() for item in settings.anthropic_available_models)
        return dedupe_keep_order(models)
    if provider == "ollama":
        models = [settings.ollama_model.strip()]
        models.extend(item.strip() for item in settings.ollama_available_models)
        return dedupe_keep_order(models)
    return ()
