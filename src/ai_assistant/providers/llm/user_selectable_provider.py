from __future__ import annotations

import logging
from datetime import datetime

from ai_assistant.core.interfaces import LLMProvider, PermissionChecker, UserSettingsStore
from ai_assistant.core.models import UserMessage
from ai_assistant.logging_utils import format_model_chain, text_preview
from ai_assistant.providers.llm.arbiter import (
    build_arbiter_prompt,
    build_regeneration_prompt,
    parse_arbiter_decision,
)
from ai_assistant.providers.llm.auto_router import AutoRouterProtocol
from ai_assistant.providers.llm.auto_router_types import (
    RouteCandidate,
    RouteDecision,
    RouterCatalogEntry,
)
from ai_assistant.providers.llm.model_health_registry import ModelHealthRegistry
from ai_assistant.providers.llm.model_manifest import (
    ModelManifestEntry,
    build_manifest_index,
    manifest_entry_key,
)

AUTO_PROVIDER_NAME = "auto"
_LOCAL_PROVIDER_NAMES = {"ollama", "mock"}
LOW_CONFIDENCE_POLICY_SETTING_KEY = "llm_auto_low_confidence_policy"
LOW_CONFIDENCE_POLICY_KEEP_CURRENT = "keep_current"
LOW_CONFIDENCE_POLICY_UPGRADE_TIER = "upgrade_tier"
_LOW_CONFIDENCE_POLICIES = {
    LOW_CONFIDENCE_POLICY_KEEP_CURRENT,
    LOW_CONFIDENCE_POLICY_UPGRADE_TIER,
}
_AUTO_TIER_PRIORITY = {
    "cheap_local": 0,
    "balanced_local": 1,
    "very_cheap_cloud": 2,
    "cheap_cloud": 3,
    "balanced_cloud": 4,
    "premium_cloud": 5,
}
_SPECIALIST_MODEL_ROLE = "specialist"

logger = logging.getLogger(__name__)


def _catalog_item_or_none(
    catalog_map: dict[tuple[str, str], RouterCatalogEntry],
    candidate: RouteCandidate,
) -> RouterCatalogEntry | None:
    return catalog_map.get((candidate.provider.strip().lower(), candidate.model.strip()))


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
        auto_router: AutoRouterProtocol | None = None,
        health_registry: ModelHealthRegistry | None = None,
        model_manifest_entries: tuple[ModelManifestEntry, ...] = (),
        auto_low_confidence_threshold: float = 0.55,
        default_low_confidence_policy: str = LOW_CONFIDENCE_POLICY_KEEP_CURRENT,
        default_selection_mode: str = "manual",
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
        self._auto_router = auto_router
        self._health_registry = health_registry
        self._model_manifest_index = build_manifest_index(model_manifest_entries)
        self._strict_manifest_mode = bool(self._model_manifest_index)
        self._auto_low_confidence_threshold = min(1.0, max(0.0, float(auto_low_confidence_threshold)))
        self._route_decision_cache: dict[datetime, RouteDecision] = {}
        normalized_policy = default_low_confidence_policy.strip().lower()
        if normalized_policy not in _LOW_CONFIDENCE_POLICIES:
            normalized_policy = LOW_CONFIDENCE_POLICY_KEEP_CURRENT
        self._default_low_confidence_policy = normalized_policy
        self._default_selection_mode = (
            "auto" if default_selection_mode.strip().lower() == "auto" else "manual"
        )

    async def generate_reply(self, message: UserMessage) -> str:
        selected_provider, candidate_model = await self._read_user_preferences(user_id=message.user_id)
        allowed_providers = await self._get_allowed_providers(user_id=message.user_id)
        logger.debug(
            "LLM request received: user_id=%s selected_provider=%s selected_model=%s allowed_providers=%s text_preview=%r",
            message.user_id,
            selected_provider,
            candidate_model,
            allowed_providers,
            text_preview(message.text),
        )
        if not allowed_providers:
            logger.error("No permitted LLM providers for user_id=%s", message.user_id)
            raise RuntimeError("No permitted LLM providers configured for this user.")

        if self._is_auto_mode_requested(selected_provider) and self._auto_router is not None:
            auto_reply = await self._try_auto_route(
                user_id=message.user_id,
                message=message,
                candidate_model=candidate_model,
                allowed_providers=allowed_providers,
            )
            if auto_reply is not None:
                return auto_reply
            logger.info(
                "Auto routing did not yield a reply, falling back to manual provider resolution: user_id=%s",
                message.user_id,
            )

        effective_provider = selected_provider
        if effective_provider == AUTO_PROVIDER_NAME:
            effective_provider = None
        provider_name, model = await self._resolve_provider_and_model_from_preferences(
            user_id=message.user_id,
            selected_provider=effective_provider,
            candidate_model=candidate_model,
            allowed_providers=allowed_providers,
        )
        logger.info(
            "Resolved LLM target: user_id=%s provider=%s model=%s",
            message.user_id,
            provider_name,
            model,
        )
        reply = await self._generate_reply_with_provider(
            provider_name=provider_name,
            model=model,
            message=message,
            suppress_errors=False,
        )
        if reply is None:
            logger.error(
                "Failed to generate reply from resolved provider: user_id=%s provider=%s model=%s",
                message.user_id,
                provider_name,
                model,
            )
            raise RuntimeError("No permitted LLM provider is available.")
        return reply

    async def _resolve_provider_and_model(self, user_id: int) -> tuple[str, str | None]:
        selected_provider, candidate_model = await self._read_user_preferences(user_id=user_id)
        allowed_providers = await self._get_allowed_providers(user_id=user_id)
        if not allowed_providers:
            raise RuntimeError("No permitted LLM providers configured for this user.")
        if selected_provider == AUTO_PROVIDER_NAME:
            selected_provider = None
        return await self._resolve_provider_and_model_from_preferences(
            user_id=user_id,
            selected_provider=selected_provider,
            candidate_model=candidate_model,
            allowed_providers=allowed_providers,
        )

    async def _resolve_provider_and_model_from_preferences(
        self,
        user_id: int,
        selected_provider: str | None,
        candidate_model: str | None,
        allowed_providers: list[str],
    ) -> tuple[str, str | None]:
        if selected_provider == AUTO_PROVIDER_NAME:
            selected_provider = None

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
            logger.debug(
                "Resolved explicit provider/model selection: user_id=%s provider=%s model=%s",
                user_id,
                selected_provider,
                resolved_model,
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
        logger.debug(
            "Provider resolution order: user_id=%s order=%s selected_provider=%s default_provider=%s",
            user_id,
            provider_order,
            selected_provider,
            self._default_provider,
        )

        for provider in provider_order:
            provider_candidate_model = candidate_model if provider == selected_provider else None
            resolved_model = await self._resolve_model_for_provider(
                user_id=user_id,
                provider=provider,
                candidate_model=provider_candidate_model,
            )
            if resolved_model is None and self._provider_requires_model(provider):
                continue
            logger.debug(
                "Resolved provider/model from ordered candidates: user_id=%s provider=%s model=%s",
                user_id,
                provider,
                resolved_model,
            )
            return provider, resolved_model

        logger.error("No permitted LLM models configured for user_id=%s", user_id)
        raise RuntimeError("No permitted LLM models configured for this user.")

    async def _try_auto_route(
        self,
        *,
        user_id: int,
        message: UserMessage,
        candidate_model: str | None,
        allowed_providers: list[str],
    ) -> str | None:
        if self._auto_router is None:
            logger.debug("Auto-route skipped: router is not configured.")
            return None

        catalog = await self._build_router_catalog(user_id=user_id, allowed_providers=allowed_providers)
        if not catalog:
            logger.warning("Auto-route skipped: empty router catalog for user_id=%s", user_id)
            return None

        # Check if we have a cached routing decision for this message
        cached_decision = self._get_cached_route_decision(message.timestamp)
        if cached_decision is not None:
            logger.debug(
                "Using cached route decision: message_ts=%s chain=%s",
                message.timestamp.isoformat(),
                format_model_chain((item.provider, item.model) for item in cached_decision.candidates),
            )
            decision = cached_decision
        else:
            logger.debug(
                "Auto-route catalog prepared: user_id=%s entries=%d chain=%s",
                user_id,
                len(catalog),
                format_model_chain((item.provider, item.model) for item in catalog),
            )
            try:
                decision = await self._auto_router.route(
                    message=message,
                    candidate_catalog=catalog,
                )
                # Cache the routing decision for this message
                self._cache_route_decision(message.timestamp, decision)
            except Exception as exc:
                logger.warning("Auto-route failed for user_id=%s: %s", user_id, exc)
                return None

        low_confidence_policy = await self._read_auto_low_confidence_policy(user_id=user_id)
        low_confidence = decision.confidence < self._auto_low_confidence_threshold
        logger.debug(
            "Auto-route decision: user_id=%s confidence=%.2f threshold=%.2f low_confidence=%s policy=%s risk=%s complexity=%s topic=%s capabilities=%s chain=%s",
            user_id,
            decision.confidence,
            self._auto_low_confidence_threshold,
            low_confidence,
            low_confidence_policy,
            decision.risk_level,
            decision.complexity,
            decision.topic,
            ",".join(decision.required_capabilities) or "-",
            format_model_chain((item.provider, item.model) for item in decision.candidates),
        )
        queue = self._build_auto_candidate_queue(
            decision=decision,
            catalog=catalog,
            candidate_model=candidate_model,
            low_confidence=low_confidence,
            low_confidence_policy=low_confidence_policy,
        )
        logger.debug(
            "Auto-route candidate queue: user_id=%s queue=%s",
            user_id,
            ", ".join(
                f"{item.provider}:{item.model}[{item.tier or '-'}|{item.reason or '-'}]"
                for item in queue
            ),
        )
        for item in queue:
            provider = item.provider
            if provider not in allowed_providers:
                logger.debug(
                    "Skipping auto candidate due to provider permissions: user_id=%s provider=%s model=%s",
                    user_id,
                    provider,
                    item.model,
                )
                continue
            resolved_model = await self._resolve_model_for_provider(
                user_id=user_id,
                provider=provider,
                candidate_model=item.model,
                strict_candidate=True,
            )
            if resolved_model is None and self._provider_requires_model(provider):
                logger.debug(
                    "Skipping auto candidate due to model permissions: user_id=%s provider=%s candidate_model=%s",
                    user_id,
                    provider,
                    item.model,
                )
                continue
            logger.debug(
                "Trying auto candidate: user_id=%s provider=%s model=%s reason=%s",
                user_id,
                provider,
                resolved_model,
                item.reason,
            )
            reply = await self._generate_reply_with_provider(
                provider_name=provider,
                model=resolved_model,
                message=message,
                suppress_errors=True,
            )
            if reply is not None:
                logger.info(
                    "Auto-route specialist succeeded: user_id=%s provider=%s model=%s",
                    user_id,
                    provider,
                    resolved_model,
                )
                return await self._apply_arbiter_if_needed(
                    user_id=user_id,
                    message=message,
                    decision=decision,
                    specialist_provider=provider,
                    specialist_model=resolved_model,
                    specialist_reply=reply,
                    allowed_providers=allowed_providers,
                    catalog=catalog,
                )
            logger.debug(
                "Auto candidate failed, trying next: user_id=%s provider=%s model=%s",
                user_id,
                provider,
                resolved_model,
            )
        logger.warning("Auto-route exhausted candidate queue without reply: user_id=%s", user_id)
        return None

    async def _build_router_catalog(
        self,
        *,
        user_id: int,
        allowed_providers: list[str],
    ) -> tuple[RouterCatalogEntry, ...]:
        entries: list[RouterCatalogEntry] = []
        seen: set[tuple[str, str]] = set()
        provider_order = sorted(
            allowed_providers,
            key=lambda item: (
                0 if item in _LOCAL_PROVIDER_NAMES else 1,
                item,
            ),
        )
        for provider in provider_order:
            models = await self._get_allowed_models_for_provider(user_id=user_id, provider=provider)
            for model in models:
                key = (provider, model)
                if key in seen:
                    continue
                manifest_entry = self._model_manifest_index.get(manifest_entry_key(provider, model))
                if self._strict_manifest_mode and manifest_entry is None:
                    logger.debug(
                        "Skipping router catalog model not present in manifest: user_id=%s provider=%s model=%s",
                        user_id,
                        provider,
                        model,
                    )
                    continue
                if (
                    manifest_entry is not None
                    and manifest_entry.roles
                    and _SPECIALIST_MODEL_ROLE not in manifest_entry.roles
                ):
                    logger.debug(
                        "Skipping router catalog model due to manifest roles: user_id=%s provider=%s model=%s roles=%s",
                        user_id,
                        provider,
                        model,
                        ",".join(manifest_entry.roles),
                    )
                    continue
                seen.add(key)
                entries.append(
                    RouterCatalogEntry(
                        provider=provider,
                        model=model,
                        platform=(
                            manifest_entry.platform
                            if manifest_entry is not None and manifest_entry.platform
                            else self._provider_platform(provider)
                        ),
                        cost_tier=(
                            manifest_entry.cost_tier
                            if manifest_entry is not None and manifest_entry.cost_tier
                            else self._model_cost_tier(provider=provider, model=model)
                        ),
                        notes=(
                            manifest_entry.notes
                            if manifest_entry is not None and manifest_entry.notes
                            else self._catalog_notes(provider=provider, model=model)
                        ),
                        tags=manifest_entry.tags if manifest_entry is not None else (),
                        domains=manifest_entry.domains if manifest_entry is not None else (),
                        roles=manifest_entry.roles if manifest_entry is not None else (_SPECIALIST_MODEL_ROLE,),
                        priority=(
                            manifest_entry.priority
                            if manifest_entry is not None
                            else self._default_model_priority(provider=provider, model=model)
                        ),
                        strength=(
                            manifest_entry.strength
                            if manifest_entry is not None
                            else self._default_model_strength(provider=provider, model=model)
                        ),
                        supports_reasoning=(
                            manifest_entry.supports_reasoning if manifest_entry is not None else True
                        ),
                        supports_non_reasoning=(
                            manifest_entry.supports_non_reasoning if manifest_entry is not None else True
                        ),
                        abilities=manifest_entry.abilities if manifest_entry is not None else ("text",),
                    )
                )
        logger.debug(
            "Built router catalog: user_id=%s providers=%s entries=%d",
            user_id,
            allowed_providers,
            len(entries),
        )
        return tuple(entries)

    async def _get_allowed_models_for_provider(self, *, user_id: int, provider: str) -> tuple[str, ...]:
        if not self._provider_requires_model(provider):
            placeholder = self._default_models.get(provider, "default")
            return (placeholder,)

        available = self._available_models.get(provider, ())
        default_model = self._default_models.get(provider)
        candidates: list[str] = []
        if default_model:
            candidates.append(default_model)
        candidates.extend(available)

        seen: set[str] = set()
        allowed_models: list[str] = []
        for model in candidates:
            normalized_model = model.strip()
            if not normalized_model or normalized_model in seen:
                continue
            seen.add(normalized_model)
            permission_name = self._model_permission_name(provider=provider, model=normalized_model)
            if await self._has_assistant_permission(user_id=user_id, permission_name=permission_name):
                allowed_models.append(normalized_model)
        return tuple(allowed_models)

    def _build_auto_candidate_queue(
        self,
        *,
        decision: RouteDecision,
        catalog: tuple[RouterCatalogEntry, ...],
        candidate_model: str | None,
        low_confidence: bool,
        low_confidence_policy: str,
    ) -> tuple[RouteCandidate, ...]:
        queue: list[RouteCandidate] = []
        seen: set[tuple[str, str]] = set()
        catalog_keys = {
            (item.provider.strip().lower(), item.model.strip()): item for item in catalog
        }
        for item in decision.candidates:
            normalized_provider = item.provider.strip().lower()
            normalized_model = item.model.strip()
            key = (normalized_provider, normalized_model)
            if key in seen or key not in catalog_keys:
                continue
            seen.add(key)
            queue.append(
                RouteCandidate(
                    provider=normalized_provider,
                    model=normalized_model,
                    tier=item.tier,
                    reason=item.reason,
                )
            )

        explicit_provider, explicit_model = self._parse_model_value(candidate_model)
        if explicit_provider and explicit_model:
            key = (explicit_provider, explicit_model)
            if key in catalog_keys and key not in seen:
                seen.add(key)
                queue.append(
                    RouteCandidate(
                        provider=explicit_provider,
                        model=explicit_model,
                        tier="user_fallback",
                        reason="user_selected_model",
                    )
                )

        for item in catalog:
            key = (item.provider.strip().lower(), item.model.strip())
            if key in seen:
                continue
            seen.add(key)
            queue.append(
                RouteCandidate(
                    provider=item.provider.strip().lower(),
                    model=item.model.strip(),
                    tier=item.cost_tier,
                    reason="catalog_fallback",
                )
            )
        if self._should_prioritize_stronger_specialists(decision):
            logger.debug(
                "Applying complexity/risk queue reprioritization: complexity=%s risk=%s",
                decision.complexity,
                decision.risk_level,
            )
            queue = self._reprioritize_queue_for_complex_or_risky_request(
                queue=queue,
                catalog=catalog,
            )
        if low_confidence and low_confidence_policy == LOW_CONFIDENCE_POLICY_UPGRADE_TIER:
            logger.debug(
                "Applying low-confidence queue reprioritization: policy=%s confidence=%.2f",
                low_confidence_policy,
                decision.confidence,
            )
            queue = self._reprioritize_queue_for_low_confidence(
                queue=queue,
                catalog=catalog,
            )
        return tuple(queue)

    @staticmethod
    def _reprioritize_queue_for_low_confidence(
        *,
        queue: list[RouteCandidate],
        catalog: tuple[RouterCatalogEntry, ...],
    ) -> list[RouteCandidate]:
        catalog_map = {
            (item.provider.strip().lower(), item.model.strip()): item
            for item in catalog
        }
        with_index = list(enumerate(queue))

        def sort_key(item: tuple[int, RouteCandidate]) -> tuple[int, int, int, int]:
            entry = _catalog_item_or_none(catalog_map, item[1])
            tier = entry.cost_tier if entry is not None else item[1].tier
            strength = entry.strength if entry is not None else 0
            priority = entry.priority if entry is not None else 100
            return (
                -_AUTO_TIER_PRIORITY.get(tier, -1),
                -strength,
                priority,
                item[0],
            )

        with_index.sort(
            key=sort_key
        )
        return [candidate for _, candidate in with_index]

    @staticmethod
    def _reprioritize_queue_for_complex_or_risky_request(
        *,
        queue: list[RouteCandidate],
        catalog: tuple[RouterCatalogEntry, ...],
    ) -> list[RouteCandidate]:
        if len(queue) <= 1:
            return list(queue)

        catalog_map = {
            (item.provider.strip().lower(), item.model.strip()): item
            for item in catalog
        }
        head = queue[0]
        with_index = list(enumerate(queue[1:], start=1))

        def sort_key(item: tuple[int, RouteCandidate]) -> tuple[int, int, int, int]:
            entry = _catalog_item_or_none(catalog_map, item[1])
            tier = entry.cost_tier if entry is not None else item[1].tier
            strength = entry.strength if entry is not None else 0
            priority = entry.priority if entry is not None else 100
            return (
                -strength,
                -_AUTO_TIER_PRIORITY.get(tier, -1),
                priority,
                item[0],
            )

        with_index.sort(
            key=sort_key
        )
        return [head, *[candidate for _, candidate in with_index]]

    @staticmethod
    def _should_prioritize_stronger_specialists(decision: RouteDecision) -> bool:
        return decision.complexity == "high" or decision.risk_level == "high"

    async def _read_user_preferences(self, user_id: int) -> tuple[str | None, str | None]:
        selected_provider: str | None = None
        selected_model: str | None = None

        if self._user_settings_store is None:
            return selected_provider, selected_model

        try:
            raw_provider = await self._user_settings_store.get_setting(user_id=user_id, key="llm_provider")
            raw_model = await self._user_settings_store.get_setting(user_id=user_id, key="llm_model")
        except Exception as exc:
            logger.debug("Failed to read LLM preferences for user_id=%s: %s", user_id, exc)
            return selected_provider, selected_model

        normalized_provider = self._normalize_provider(raw_provider)
        explicit_provider, parsed_model = self._parse_model_value(raw_model)

        # Explicit llm_provider setting has higher priority than provider prefix in llm_model.
        if normalized_provider:
            selected_provider = normalized_provider
        elif explicit_provider:
            selected_provider = explicit_provider

        selected_model = parsed_model
        logger.debug(
            "User LLM preferences: user_id=%s raw_provider=%s raw_model=%s selected_provider=%s selected_model=%s",
            user_id,
            raw_provider,
            raw_model,
            selected_provider,
            selected_model,
        )
        return selected_provider, selected_model

    async def _read_auto_low_confidence_policy(self, user_id: int) -> str:
        if self._user_settings_store is None:
            return self._default_low_confidence_policy
        try:
            raw_value = await self._user_settings_store.get_setting(
                user_id=user_id,
                key=LOW_CONFIDENCE_POLICY_SETTING_KEY,
            )
        except Exception as exc:
            logger.debug(
                "Failed to read low-confidence policy, using default: user_id=%s error=%s",
                user_id,
                exc,
            )
            return self._default_low_confidence_policy

        normalized = (raw_value or "").strip().lower()
        if normalized in _LOW_CONFIDENCE_POLICIES:
            return normalized
        if raw_value:
            logger.debug(
                "Unknown low-confidence policy for user_id=%s: %s; using default=%s",
                user_id,
                raw_value,
                self._default_low_confidence_policy,
            )
        return self._default_low_confidence_policy

    async def _get_allowed_providers(self, user_id: int) -> list[str]:
        allowed: list[str] = []
        for provider in self._providers.keys():
            permission_name = self._provider_permission_name(provider)
            if await self._has_assistant_permission(user_id=user_id, permission_name=permission_name):
                allowed.append(provider)
        logger.debug("Allowed providers resolved: user_id=%s allowed=%s", user_id, allowed)
        return allowed

    async def _resolve_model_for_provider(
        self,
        user_id: int,
        provider: str,
        candidate_model: str | None,
        strict_candidate: bool = False,
    ) -> str | None:
        if not self._provider_requires_model(provider):
            return None

        available = self._available_models.get(provider, ())
        default_model = self._default_models.get(provider)

        candidates: list[str] = []
        if candidate_model:
            candidates.append(candidate_model)
        if not strict_candidate and default_model:
            candidates.append(default_model)
        if not strict_candidate:
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
                logger.debug(
                    "Resolved allowed model: user_id=%s provider=%s model=%s strict_candidate=%s",
                    user_id,
                    provider,
                    model,
                    strict_candidate,
                )
                return model

        logger.debug(
            "No allowed model resolved: user_id=%s provider=%s candidate_model=%s strict_candidate=%s",
            user_id,
            provider,
            candidate_model,
            strict_candidate,
        )
        return None

    async def _generate_reply_with_provider(
        self,
        *,
        provider_name: str,
        model: str | None,
        message: UserMessage,
        suppress_errors: bool,
    ) -> str | None:
        provider = self._providers.get(provider_name)
        if provider is None:
            logger.debug(
                "Provider is unavailable in registry: provider=%s suppress_errors=%s",
                provider_name,
                suppress_errors,
            )
            if suppress_errors:
                return None
            raise RuntimeError("No permitted LLM provider is available.")

        target_key = ModelHealthRegistry.build_target_key(provider=provider_name, model=model, scope="llm")
        if suppress_errors and self._health_registry is not None:
            if not self._health_registry.is_available(target_key):
                logger.debug(
                    "Skipping LLM target due to health cooldown: target=%s user_id=%s",
                    target_key,
                    message.user_id,
                )
                return None

        logger.debug(
            "Calling LLM provider: user_id=%s provider=%s model=%s suppress_errors=%s text_preview=%r",
            message.user_id,
            provider_name,
            model,
            suppress_errors,
            text_preview(message.text),
        )
        try:
            if hasattr(provider, "generate_reply_for_model"):
                reply = await provider.generate_reply_for_model(message=message, model=model)  # type: ignore[attr-defined]
            else:
                reply = await provider.generate_reply(message)
        except Exception as exc:
            if self._health_registry is not None:
                self._health_registry.record_failure(target_key)
            logger.warning(
                "LLM provider call failed: user_id=%s provider=%s model=%s error=%s",
                message.user_id,
                provider_name,
                model,
                exc,
            )
            if suppress_errors:
                return None
            raise

        if self._health_registry is not None:
            self._health_registry.record_success(target_key)
        logger.debug(
            "LLM provider call succeeded: user_id=%s provider=%s model=%s reply_chars=%d",
            message.user_id,
            provider_name,
            model,
            len(reply),
        )
        return reply

    async def _apply_arbiter_if_needed(
        self,
        *,
        user_id: int,
        message: UserMessage,
        decision: RouteDecision,
        specialist_provider: str,
        specialist_model: str | None,
        specialist_reply: str,
        allowed_providers: list[str],
        catalog: tuple[RouterCatalogEntry, ...],
    ) -> str:
        if not self._should_use_arbiter(decision):
            logger.debug(
                "Arbiter skipped: user_id=%s risk=%s explicit_arbiter=%s",
                user_id,
                decision.risk_level,
                bool(decision.arbiter and decision.arbiter.enabled),
            )
            return specialist_reply

        arbiter_target = await self._resolve_arbiter_target(
            user_id=user_id,
            decision=decision,
            allowed_providers=allowed_providers,
            catalog=catalog,
        )
        if arbiter_target is None:
            logger.debug("Arbiter skipped: no eligible arbiter target for user_id=%s", user_id)
            return specialist_reply

        arbiter_provider, arbiter_model = arbiter_target
        logger.info(
            "Applying arbiter: user_id=%s provider=%s model=%s specialist_provider=%s specialist_model=%s",
            user_id,
            arbiter_provider,
            arbiter_model,
            specialist_provider,
            specialist_model,
        )
        arbiter_prompt = build_arbiter_prompt(
            user_text=message.text,
            specialist_answer=specialist_reply,
        )
        arbiter_reply = await self._generate_reply_with_provider(
            provider_name=arbiter_provider,
            model=arbiter_model,
            message=UserMessage(
                user_id=user_id,
                text=arbiter_prompt,
                timestamp=message.timestamp,
            ),
            suppress_errors=True,
        )
        if not arbiter_reply:
            logger.warning("Arbiter returned empty response for user_id=%s", user_id)
            return specialist_reply

        try:
            arbiter_decision = parse_arbiter_decision(arbiter_reply)
        except Exception as exc:
            logger.warning("Arbiter decision parse failed for user_id=%s: %s", user_id, exc)
            return specialist_reply

        logger.debug(
            "Arbiter decision: user_id=%s action=%s has_final_answer=%s has_regenerate_prompt=%s",
            user_id,
            arbiter_decision.action,
            bool(arbiter_decision.final_answer),
            bool(arbiter_decision.regenerate_prompt),
        )
        if arbiter_decision.action == "approve":
            return arbiter_decision.final_answer or specialist_reply
        if arbiter_decision.action == "edit":
            return arbiter_decision.final_answer or specialist_reply
        if arbiter_decision.action != "regenerate":
            return specialist_reply

        if not arbiter_decision.regenerate_prompt:
            return arbiter_decision.final_answer or specialist_reply

        regenerated_prompt = build_regeneration_prompt(
            original_user_text=message.text,
            arbiter_feedback=arbiter_decision.feedback,
            regeneration_instruction=arbiter_decision.regenerate_prompt,
        )
        regenerated_reply = await self._generate_reply_with_provider(
            provider_name=specialist_provider,
            model=specialist_model,
            message=UserMessage(
                user_id=user_id,
                text=regenerated_prompt,
                timestamp=message.timestamp,
            ),
            suppress_errors=True,
        )
        if regenerated_reply:
            logger.info(
                "Regenerated specialist response after arbiter feedback: user_id=%s provider=%s model=%s",
                user_id,
                specialist_provider,
                specialist_model,
            )
            return regenerated_reply
        return arbiter_decision.final_answer or specialist_reply

    async def _resolve_arbiter_target(
        self,
        *,
        user_id: int,
        decision: RouteDecision,
        allowed_providers: list[str],
        catalog: tuple[RouterCatalogEntry, ...],
    ) -> tuple[str, str | None] | None:
        if decision.arbiter and decision.arbiter.enabled and decision.arbiter.provider:
            explicit_target = await self._resolve_candidate_target(
                user_id=user_id,
                provider=decision.arbiter.provider,
                candidate_model=decision.arbiter.model,
                allowed_providers=allowed_providers,
            )
            if explicit_target is not None:
                logger.debug(
                    "Using explicit arbiter target: user_id=%s provider=%s model=%s",
                    user_id,
                    explicit_target[0],
                    explicit_target[1],
                )
                return explicit_target

        if decision.risk_level != "high":
            return None

        logger.debug("Selecting fallback arbiter target from high-tier catalog for user_id=%s", user_id)
        sorted_catalog = sorted(
            catalog,
            key=lambda item: (
                -int("arbiter" in item.roles),
                -item.strength,
                -_AUTO_TIER_PRIORITY.get(item.cost_tier, -1),
                item.priority,
                item.provider,
                item.model,
            ),
        )
        for item in sorted_catalog:
            target = await self._resolve_candidate_target(
                user_id=user_id,
                provider=item.provider,
                candidate_model=item.model,
                allowed_providers=allowed_providers,
            )
            if target is not None:
                logger.debug(
                    "Resolved fallback arbiter target: user_id=%s provider=%s model=%s",
                    user_id,
                    target[0],
                    target[1],
                )
                return target
        return None

    async def _resolve_candidate_target(
        self,
        *,
        user_id: int,
        provider: str,
        candidate_model: str | None,
        allowed_providers: list[str],
    ) -> tuple[str, str | None] | None:
        normalized_provider = provider.strip().lower()
        if normalized_provider not in allowed_providers:
            return None
        resolved_model = await self._resolve_model_for_provider(
            user_id=user_id,
            provider=normalized_provider,
            candidate_model=candidate_model,
            strict_candidate=True,
        )
        if resolved_model is None and self._provider_requires_model(normalized_provider):
            return None
        return normalized_provider, resolved_model

    @staticmethod
    def _should_use_arbiter(decision: RouteDecision) -> bool:
        if decision.arbiter and decision.arbiter.enabled:
            return True
        if decision.risk_level == "high":
            return True
        return False

    def _is_auto_mode_requested(self, selected_provider: str | None) -> bool:
        if selected_provider == AUTO_PROVIDER_NAME:
            return True
        if selected_provider is None and self._default_selection_mode == "auto":
            return True
        return False

    @staticmethod
    def _provider_platform(provider: str) -> str:
        if provider in _LOCAL_PROVIDER_NAMES:
            return "local"
        return "cloud"

    @staticmethod
    def _catalog_notes(provider: str, model: str) -> str:
        normalized_model = model.strip().lower()
        if provider == "ollama":
            if any(token in normalized_model for token in ("medgemma", "medical", "clinical", "health")):
                return "local medical-specialist runtime"
            return "local general-purpose runtime"
        if provider == "mock":
            return "testing backend"
        if provider in {"openai", "anthropic"}:
            return "cloud high-quality runtime"
        return "generic backend"

    @staticmethod
    def _model_cost_tier(provider: str, model: str) -> str:
        normalized = model.strip().lower()
        if provider in _LOCAL_PROVIDER_NAMES:
            if any(token in normalized for token in ("70b", "34b", "32b", "27b", "24b", "large")):
                return "balanced_local"
            return "cheap_local"

        if any(token in normalized for token in ("nano", "mini", "haiku", "small")):
            return "cheap_cloud"
        if any(token in normalized for token in ("opus", "gpt-5", "pro", "max")):
            return "premium_cloud"
        return "balanced_cloud"

    @staticmethod
    def _default_model_priority(provider: str, model: str) -> int:
        del provider, model
        return 100

    @classmethod
    def _default_model_strength(cls, *, provider: str, model: str) -> int:
        cost_tier = cls._model_cost_tier(provider=provider, model=model)
        return _AUTO_TIER_PRIORITY.get(cost_tier, 0)

    def _provider_requires_model(self, provider: str) -> bool:
        if self._default_models.get(provider):
            return True
        if self._available_models.get(provider):
            return True
        return False

    async def _has_assistant_permission(self, user_id: int, permission_name: str) -> bool:
        if self._admin_telegram_id is not None and user_id == self._admin_telegram_id:
            logger.debug(
                "Permission granted via admin bypass: user_id=%s permission=%s",
                user_id,
                permission_name,
            )
            return True
        if self._permission_checker is None:
            return True
        allowed = await self._permission_checker.has_permission(
            user_id=user_id,
            permission_type="assistant",
            name=permission_name,
        )
        logger.debug(
            "Permission check: user_id=%s permission=%s allowed=%s",
            user_id,
            permission_name,
            allowed,
        )
        return allowed

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

    def _cache_route_decision(self, message_timestamp: datetime, decision: RouteDecision) -> None:
        """Cache a routing decision for a specific message timestamp."""
        self._route_decision_cache[message_timestamp] = decision
        # Cleanup old cache entries (keep only last 10)
        if len(self._route_decision_cache) > 10:
            oldest_keys = sorted(self._route_decision_cache.keys())[:-10]
            for key in oldest_keys:
                del self._route_decision_cache[key]
        logger.debug(
            "Cached route decision: message_ts=%s cache_size=%d",
            message_timestamp.isoformat(),
            len(self._route_decision_cache),
        )

    def _get_cached_route_decision(self, message_timestamp: datetime) -> RouteDecision | None:
        """Retrieve cached routing decision for a specific message timestamp."""
        return self._route_decision_cache.get(message_timestamp)
