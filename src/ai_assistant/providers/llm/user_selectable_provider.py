from __future__ import annotations

from ai_assistant.core.interfaces import LLMProvider, PermissionChecker, UserSettingsStore
from ai_assistant.core.models import UserMessage


class UserSelectableLLMProvider:
    def __init__(
        self,
        providers: dict[str, LLMProvider],
        default_provider: str,
        default_models: dict[str, str],
        available_models: dict[str, tuple[str, ...]],
        user_settings_store: UserSettingsStore | None = None,
        permission_checker: PermissionChecker | None = None,
        admin_telegram_id: int | None = None,
    ) -> None:
        normalized_providers = {
            key.strip().lower(): value
            for key, value in providers.items()
            if key.strip()
        }
        if not normalized_providers:
            raise ValueError("At least one LLM provider must be configured.")

        normalized_default_provider = default_provider.strip().lower()
        if normalized_default_provider not in normalized_providers:
            normalized_default_provider = next(iter(normalized_providers.keys()))

        self._providers = normalized_providers
        self._default_provider = normalized_default_provider
        self._default_models = {
            key.strip().lower(): value.strip()
            for key, value in default_models.items()
            if key.strip() and value.strip()
        }
        self._available_models = {
            key.strip().lower(): tuple(model.strip() for model in value if model.strip())
            for key, value in available_models.items()
            if key.strip()
        }
        self._user_settings_store = user_settings_store
        self._permission_checker = permission_checker
        self._admin_telegram_id = admin_telegram_id

    async def generate_reply(self, message: UserMessage) -> str:
        provider_name, model = await self._resolve_provider_and_model(user_id=message.user_id)
        provider = self._providers.get(provider_name)
        if provider is None:
            raise RuntimeError("No permitted LLM provider is available.")

        if hasattr(provider, "generate_reply_for_model"):
            return await provider.generate_reply_for_model(message=message, model=model)  # type: ignore[attr-defined]

        return await provider.generate_reply(message)

    async def _resolve_provider_and_model(self, user_id: int) -> tuple[str, str | None]:
        selected_provider, candidate_model = await self._read_user_preferences(user_id=user_id)
        allowed_providers = await self._get_allowed_providers(user_id=user_id)
        if not allowed_providers:
            raise RuntimeError("No permitted LLM providers configured for this user.")

        # If user explicitly selected provider:model, do not silently fall back to another provider.
        if selected_provider and candidate_model:
            if selected_provider not in allowed_providers:
                raise RuntimeError(
                    f"Selected LLM provider is not permitted: {selected_provider}"
                )
            resolved_model = await self._resolve_model_for_provider(
                user_id=user_id,
                provider=selected_provider,
                candidate_model=candidate_model,
            )
            if resolved_model is None and self._provider_requires_model(selected_provider):
                raise RuntimeError(
                    f"No permitted LLM model for selected provider: {selected_provider}"
                )
            return selected_provider, resolved_model

        provider_order: list[str] = []
        if selected_provider and selected_provider in allowed_providers:
            provider_order.append(selected_provider)
        if self._default_provider in allowed_providers and self._default_provider not in provider_order:
            provider_order.append(self._default_provider)
        for provider in allowed_providers:
            if provider not in provider_order:
                provider_order.append(provider)

        for provider in provider_order:
            provider_candidate_model = candidate_model if provider == selected_provider else None
            resolved_model = await self._resolve_model_for_provider(
                user_id=user_id,
                provider=provider,
                candidate_model=provider_candidate_model,
            )
            if resolved_model is None and self._provider_requires_model(provider):
                continue
            return provider, resolved_model

        raise RuntimeError("No permitted LLM models configured for this user.")

    async def _read_user_preferences(self, user_id: int) -> tuple[str | None, str | None]:
        selected_provider: str | None = None
        selected_model: str | None = None

        if self._user_settings_store is None:
            return selected_provider, selected_model

        try:
            raw_provider = await self._user_settings_store.get_setting(user_id=user_id, key="llm_provider")
            raw_model = await self._user_settings_store.get_setting(user_id=user_id, key="llm_model")
        except Exception:
            return selected_provider, selected_model

        normalized_provider = self._normalize_provider(raw_provider)
        explicit_provider, parsed_model = self._parse_model_value(raw_model)

        # Explicit llm_provider setting has higher priority than provider prefix in llm_model.
        if normalized_provider:
            selected_provider = normalized_provider
        elif explicit_provider:
            selected_provider = explicit_provider

        selected_model = parsed_model
        return selected_provider, selected_model

    async def _get_allowed_providers(self, user_id: int) -> list[str]:
        allowed: list[str] = []
        for provider in self._providers.keys():
            permission_name = self._provider_permission_name(provider)
            if await self._has_assistant_permission(user_id=user_id, permission_name=permission_name):
                allowed.append(provider)
        return allowed

    async def _resolve_model_for_provider(
        self,
        user_id: int,
        provider: str,
        candidate_model: str | None,
    ) -> str | None:
        if not self._provider_requires_model(provider):
            return None

        available = self._available_models.get(provider, ())
        default_model = self._default_models.get(provider)

        candidates: list[str] = []
        if candidate_model:
            candidates.append(candidate_model)
        if default_model:
            candidates.append(default_model)
        candidates.extend(available)

        seen: set[str] = set()
        ordered_candidates: list[str] = []
        for candidate in candidates:
            normalized = candidate.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            ordered_candidates.append(normalized)

        for model in ordered_candidates:
            if available and model not in available:
                continue
            permission_name = self._model_permission_name(provider=provider, model=model)
            if await self._has_assistant_permission(user_id=user_id, permission_name=permission_name):
                return model

        return None

    def _provider_requires_model(self, provider: str) -> bool:
        if self._default_models.get(provider):
            return True
        if self._available_models.get(provider):
            return True
        return False

    async def _has_assistant_permission(self, user_id: int, permission_name: str) -> bool:
        if self._admin_telegram_id is not None and user_id == self._admin_telegram_id:
            return True
        if self._permission_checker is None:
            return True
        return await self._permission_checker.has_permission(
            user_id=user_id,
            permission_type="assistant",
            name=permission_name,
        )

    @staticmethod
    def _provider_permission_name(provider: str) -> str:
        return f"llm.provider.{provider.strip().lower()}"

    @staticmethod
    def _model_permission_name(provider: str, model: str) -> str:
        return f"llm.model.{provider.strip().lower()}:{model.strip().lower()}"

    @staticmethod
    def _normalize_provider(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not normalized:
            return None
        return normalized

    @staticmethod
    def _parse_model_value(value: str | None) -> tuple[str | None, str | None]:
        if value is None:
            return None, None
        normalized = value.strip()
        if not normalized:
            return None, None

        if ":" in normalized:
            provider, model = normalized.split(":", 1)
            provider_name = provider.strip().lower()
            model_name = model.strip()
            if model_name:
                return provider_name or None, model_name
            return provider_name or None, None

        return None, normalized
