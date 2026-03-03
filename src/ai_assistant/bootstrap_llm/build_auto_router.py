from __future__ import annotations

from ai_assistant.config.settings import Settings
from ai_assistant.core.interfaces import LLMProvider
from ai_assistant.providers.llm.auto_router import PolicyBasedAutoRouter, RouterBackend
from ai_assistant.providers.llm.model_health_registry import ModelHealthRegistry


def build_auto_router(
    settings: Settings,
    provider_instances: dict[str, LLMProvider],
    default_models: dict[str, str],
    health_registry: ModelHealthRegistry | None = None,
) -> PolicyBasedAutoRouter | None:
    backends: list[RouterBackend] = []
    local_backend = _build_backend(
        name="local",
        provider_name=settings.auto_router_local_provider,
        configured_model=settings.auto_router_local_model,
        provider_instances=provider_instances,
        default_models=default_models,
    )
    if local_backend is not None:
        backends.append(local_backend)

    cloud_backend = _build_backend(
        name="cloud",
        provider_name=settings.auto_router_cloud_provider,
        configured_model=settings.auto_router_cloud_model,
        provider_instances=provider_instances,
        default_models=default_models,
    )
    if cloud_backend is not None:
        cloud_key = (cloud_backend.provider_name, cloud_backend.model)
        existing_keys = {(item.provider_name, item.model) for item in backends}
        if cloud_key not in existing_keys:
            backends.append(cloud_backend)

    if not backends:
        return None

    return PolicyBasedAutoRouter(
        backends=tuple(backends),
        timeout_seconds=settings.auto_router_timeout_seconds,
        health_registry=health_registry,
    )


def _build_backend(
    *,
    name: str,
    provider_name: str,
    configured_model: str,
    provider_instances: dict[str, LLMProvider],
    default_models: dict[str, str],
) -> RouterBackend | None:
    normalized_provider = provider_name.strip().lower()
    if not normalized_provider:
        return None
    provider_instance = provider_instances.get(normalized_provider)
    if provider_instance is None:
        return None

    model = configured_model.strip() or default_models.get(normalized_provider, "").strip()
    if not model:
        return None

    return RouterBackend(
        name=name,
        provider_name=normalized_provider,
        model=model,
        provider=provider_instance,
    )

