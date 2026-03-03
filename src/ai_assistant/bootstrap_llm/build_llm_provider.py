from __future__ import annotations

from ai_assistant.config.settings import Settings
from ai_assistant.bootstrap_llm.build_auto_router import build_auto_router
from ai_assistant.bootstrap_llm.constants import AUTO_LLM_PROVIDER
from ai_assistant.core.interfaces import LLMProvider, PermissionAdminStore, UserSettingsStore
from ai_assistant.providers.llm.model_health_registry import ModelHealthRegistry
from ai_assistant.providers.llm.user_selectable_provider import UserSelectableLLMProvider
from ai_assistant.bootstrap_llm.build_models_for_provider import build_models_for_provider


def build_llm_provider(
    settings: Settings,
    user_settings_store: UserSettingsStore,
    provider_instances: dict[str, LLMProvider],
    permission_checker: PermissionAdminStore | None,
) -> LLMProvider:
    configured_default_provider = settings.llm_provider.strip().lower()
    default_provider = configured_default_provider
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
    health_registry = ModelHealthRegistry(
        base_cooldown_seconds=settings.llm_health_base_cooldown_seconds,
        max_cooldown_seconds=settings.llm_health_max_cooldown_seconds,
    )
    auto_router = build_auto_router(
        settings=settings,
        provider_instances=provider_instances,
        default_models=default_models,
        health_registry=health_registry,
    )

    return UserSelectableLLMProvider(
        providers=provider_instances,
        default_provider=default_provider,
        default_models=default_models,
        available_models=available_models,
        user_settings_store=user_settings_store,
        permission_checker=permission_checker,
        admin_telegram_id=settings.admin_telegram_id,
        auto_router=auto_router,
        health_registry=health_registry,
        default_selection_mode=(
            "auto" if configured_default_provider == AUTO_LLM_PROVIDER else "manual"
        ),
    )
