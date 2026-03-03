from __future__ import annotations

from ai_assistant.config.settings import Settings
from ai_assistant.core.interfaces import LLMProvider, PermissionAdminStore, UserSettingsStore
from ai_assistant.providers.llm.user_selectable_provider import UserSelectableLLMProvider
from ai_assistant.bootstrap_llm.build_models_for_provider import build_models_for_provider


def build_llm_provider(
    settings: Settings,
    user_settings_store: UserSettingsStore,
    provider_instances: dict[str, LLMProvider],
    permission_checker: PermissionAdminStore | None,
) -> LLMProvider:
    default_provider = settings.llm_provider.strip().lower()
    if default_provider not in provider_instances:
        default_provider = next(iter(provider_instances.keys()))

    available_models = {
        provider: build_models_for_provider(settings, provider)
        for provider in provider_instances.keys()
    }
    default_models = {
        "openai": settings.openai_model,
        "anthropic": settings.anthropic_model,
        "ollama": settings.ollama_model,
    }

    return UserSelectableLLMProvider(
        providers=provider_instances,
        default_provider=default_provider,
        default_models=default_models,
        available_models=available_models,
        user_settings_store=user_settings_store,
        permission_checker=permission_checker,
        admin_telegram_id=settings.admin_telegram_id,
    )
