from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Protocol

from ai_assistant.core.interfaces import LLMProvider
from ai_assistant.core.models import UserMessage
from ai_assistant.logging_utils import format_model_chain, text_preview
from ai_assistant.providers.llm.auto_router_policy import build_router_prompt
from ai_assistant.providers.llm.auto_router_types import (
    RouteCandidate,
    RouteDecision,
    RouterCatalogEntry,
    parse_route_decision,
)
from ai_assistant.providers.llm.model_health_registry import ModelHealthRegistry

_LOCAL_PLATFORMS = {"local"}
_COST_RANK = {
    "cheap_local": 0,
    "balanced_local": 1,
    "cheap_cloud": 2,
    "balanced_cloud": 3,
    "premium_cloud": 4,
}

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class RouterBackend:
    name: str
    provider_name: str
    model: str
    provider: LLMProvider

    def target_key(self) -> str:
        return ModelHealthRegistry.build_target_key(
            provider=self.provider_name,
            model=self.model,
            scope="router",
        )


class AutoRouterProtocol(Protocol):
    async def route(
        self,
        *,
        message: UserMessage,
        candidate_catalog: tuple[RouterCatalogEntry, ...],
    ) -> RouteDecision:
        ...


class PolicyBasedAutoRouter:
    def __init__(
        self,
        *,
        backends: tuple[RouterBackend, ...],
        timeout_seconds: float = 20.0,
        health_registry: ModelHealthRegistry | None = None,
    ) -> None:
        self._backends = backends
        self._timeout_seconds = timeout_seconds
        self._health_registry = health_registry

    async def route(
        self,
        *,
        message: UserMessage,
        candidate_catalog: tuple[RouterCatalogEntry, ...],
    ) -> RouteDecision:
        if not candidate_catalog:
            logger.error("Auto-router received empty candidate catalog.")
            raise RuntimeError("Auto-router catalog is empty.")

        logger.debug(
            "Auto-router request: user_id=%s candidates=%d request_preview=%r",
            message.user_id,
            len(candidate_catalog),
            text_preview(message.text),
        )
        prompt = build_router_prompt(
            user_text=message.text,
            candidate_catalog=candidate_catalog,
        )
        for backend in self._backends:
            if not self._is_backend_available(backend):
                logger.debug(
                    "Auto-router backend skipped (cooldown): backend=%s provider=%s model=%s",
                    backend.name,
                    backend.provider_name,
                    backend.model,
                )
                continue
            try:
                logger.debug(
                    "Auto-router querying backend=%s provider=%s model=%s",
                    backend.name,
                    backend.provider_name,
                    backend.model,
                )
                raw_reply = await self._ask_backend(
                    backend=backend,
                    user_id=message.user_id,
                    prompt=prompt,
                )
                decision = parse_route_decision(raw_reply)
                normalized = self._normalize_decision(
                    decision=decision,
                    candidate_catalog=candidate_catalog,
                )
                logger.debug(
                    "Auto-router decision: backend=%s confidence=%.2f risk=%s complexity=%s topic=%s capabilities=%s chain=%s",
                    backend.name,
                    normalized.confidence,
                    normalized.risk_level,
                    normalized.complexity,
                    normalized.topic,
                    ",".join(normalized.required_capabilities) or "-",
                    format_model_chain(
                        (item.provider, item.model) for item in normalized.candidates
                    ),
                )
            except Exception as exc:
                logger.warning(
                    "Auto-router backend failed: backend=%s provider=%s model=%s error=%s",
                    backend.name,
                    backend.provider_name,
                    backend.model,
                    exc,
                )
                self._record_backend_failure(backend)
                continue
            self._record_backend_success(backend)
            return normalized
        logger.warning("Auto-router failed on all backends; using fallback candidate ordering.")
        return self._build_fallback_decision(candidate_catalog)

    async def _ask_backend(self, *, backend: RouterBackend, user_id: int, prompt: str) -> str:
        request_message = UserMessage(user_id=user_id, text=prompt)

        async def _request() -> str:
            provider = backend.provider
            if hasattr(provider, "generate_reply_for_model"):
                return await provider.generate_reply_for_model(  # type: ignore[attr-defined]
                    message=request_message,
                    model=backend.model,
                )
            return await provider.generate_reply(request_message)

        reply = await asyncio.wait_for(_request(), timeout=self._timeout_seconds)
        logger.debug(
            "Auto-router backend response received: backend=%s chars=%d",
            backend.name,
            len(reply),
        )
        return reply

    def _normalize_decision(
        self,
        *,
        decision: RouteDecision,
        candidate_catalog: tuple[RouterCatalogEntry, ...],
    ) -> RouteDecision:
        known_keys = {
            (item.provider.strip().lower(), item.model.strip().lower())
            for item in candidate_catalog
        }
        deduped: list[RouteCandidate] = []
        seen: set[tuple[str, str]] = set()
        for item in decision.candidates:
            key = (item.provider.strip().lower(), item.model.strip().lower())
            if key in seen or key not in known_keys:
                continue
            seen.add(key)
            deduped.append(
                RouteCandidate(
                    provider=key[0],
                    model=item.model.strip(),
                    tier=item.tier,
                    reason=item.reason,
                )
            )
        if not deduped:
            logger.warning(
                "Auto-router decision has no valid catalog candidates after normalization; using fallback."
            )
            return self._build_fallback_decision(candidate_catalog)
        return RouteDecision(
            confidence=decision.confidence,
            risk_level=decision.risk_level,
            complexity=decision.complexity,
            required_capabilities=decision.required_capabilities,
            candidates=tuple(deduped),
            arbiter=decision.arbiter,
            topic=decision.topic,
        )

    def _build_fallback_decision(
        self,
        candidate_catalog: tuple[RouterCatalogEntry, ...],
    ) -> RouteDecision:
        ordered = sorted(
            candidate_catalog,
            key=lambda item: (
                0 if item.platform in _LOCAL_PLATFORMS else 1,
                _COST_RANK.get(item.cost_tier, 99),
                item.provider,
                item.model,
            ),
        )
        candidates = tuple(
            RouteCandidate(
                provider=item.provider,
                model=item.model,
                tier=item.cost_tier,
                reason="fallback",
            )
            for item in ordered
        )
        return RouteDecision(
            confidence=0.0,
            risk_level="unknown",
            complexity="unknown",
            required_capabilities=(),
            candidates=candidates,
            arbiter=None,
            topic="fallback",
        )

    def _is_backend_available(self, backend: RouterBackend) -> bool:
        if self._health_registry is None:
            return True
        return self._health_registry.is_available(backend.target_key())

    def _record_backend_success(self, backend: RouterBackend) -> None:
        if self._health_registry is None:
            return
        logger.debug(
            "Auto-router backend marked healthy: provider=%s model=%s",
            backend.provider_name,
            backend.model,
        )
        self._health_registry.record_success(backend.target_key())

    def _record_backend_failure(self, backend: RouterBackend) -> None:
        if self._health_registry is None:
            return
        logger.debug(
            "Auto-router backend marked unhealthy: provider=%s model=%s",
            backend.provider_name,
            backend.model,
        )
        self._health_registry.record_failure(backend.target_key())
