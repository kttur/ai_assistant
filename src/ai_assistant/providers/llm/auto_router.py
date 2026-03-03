from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol

from ai_assistant.core.interfaces import LLMProvider
from ai_assistant.core.models import UserMessage
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
            raise RuntimeError("Auto-router catalog is empty.")

        prompt = build_router_prompt(
            user_text=message.text,
            candidate_catalog=candidate_catalog,
        )
        for backend in self._backends:
            if not self._is_backend_available(backend):
                continue
            try:
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
            except Exception:
                self._record_backend_failure(backend)
                continue
            self._record_backend_success(backend)
            return normalized
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

        return await asyncio.wait_for(_request(), timeout=self._timeout_seconds)

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
            return self._build_fallback_decision(candidate_catalog)
        return RouteDecision(
            confidence=decision.confidence,
            risk_level=decision.risk_level,
            complexity=decision.complexity,
            required_capabilities=decision.required_capabilities,
            candidates=tuple(deduped),
            arbiter=decision.arbiter,
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
        )

    def _is_backend_available(self, backend: RouterBackend) -> bool:
        if self._health_registry is None:
            return True
        return self._health_registry.is_available(backend.target_key())

    def _record_backend_success(self, backend: RouterBackend) -> None:
        if self._health_registry is None:
            return
        self._health_registry.record_success(backend.target_key())

    def _record_backend_failure(self, backend: RouterBackend) -> None:
        if self._health_registry is None:
            return
        self._health_registry.record_failure(backend.target_key())

