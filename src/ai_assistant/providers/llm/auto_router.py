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
_QUICK_COMMAND_MAX_CHARS = 120
_QUICK_COMMAND_HINTS = (
    "поставь",
    "пауза",
    "включи",
    "выключи",
    "переключи",
    "сделай громче",
    "сделай тише",
    "убавь",
    "добавь",
    "pause",
    "play",
    "mute",
    "unmute",
    "subtitle",
    "track",
    "audio",
)
_QUICK_COMMAND_QUESTION_HINTS = (
    "почему",
    "зачем",
    "как",
    "what",
    "why",
    "how",
)
_USER_LINE_PREFIXES = ("Пользователь:", "User:")
_QWEN_ROUTER_MODEL_PREFIX = "qwen3:"
_QWEN_NOTHINK_DIRECTIVE = "/nothink"

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
        fallback_backend_timeout_seconds: float = 2.0,
        quick_command_timeout_seconds: float = 3.0,
        health_registry: ModelHealthRegistry | None = None,
        fast_path_enabled: bool = True,
        fast_path_provider: str = "ollama",
        fast_path_model: str = "qwen3:8b",
    ) -> None:
        self._backends = backends
        self._timeout_seconds = timeout_seconds
        self._fallback_backend_timeout_seconds = max(
            0.1,
            float(fallback_backend_timeout_seconds),
        )
        self._quick_command_timeout_seconds = max(
            0.1,
            float(quick_command_timeout_seconds),
        )
        self._health_registry = health_registry
        self._fast_path_enabled = fast_path_enabled
        self._fast_path_provider = fast_path_provider.strip().lower()
        self._fast_path_model = fast_path_model.strip()

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
        quick_command = _is_quick_command_request(message.text)

        # Fast path: skip LLM routing for ultra-quick commands
        if quick_command and self._fast_path_enabled:
            # Check if fast path model is in catalog
            fast_path_candidate = None
            for entry in candidate_catalog:
                if (entry.provider.strip().lower() == self._fast_path_provider and
                    entry.model.strip() == self._fast_path_model):
                    fast_path_candidate = entry
                    break

            if fast_path_candidate is not None:
                logger.debug(
                    "Auto-router fast-path enabled: user_id=%s provider=%s model=%s",
                    message.user_id,
                    self._fast_path_provider,
                    self._fast_path_model,
                )
                return RouteDecision(
                    confidence=1.0,
                    risk_level="low",
                    complexity="low",
                    required_capabilities=(),
                    candidates=(RouteCandidate(
                        provider=self._fast_path_provider,
                        model=self._fast_path_model,
                        tier=fast_path_candidate.cost_tier,
                        reason="fast_path",
                    ),),
                    arbiter=None,
                    topic="quick_command",
                )

        prompt = build_router_prompt(
            user_text=message.text,
            candidate_catalog=candidate_catalog,
            quick_mode=quick_command,
        )
        if quick_command:
            logger.debug(
                "Auto-router quick-command mode enabled: user_id=%s timeout=%.2fs",
                message.user_id,
                self._quick_command_timeout_seconds,
            )
        for index, backend in enumerate(self._backends):
            if quick_command and index > 0:
                logger.debug(
                    "Auto-router quick-command mode: skipping backend=%s provider=%s model=%s",
                    backend.name,
                    backend.provider_name,
                    backend.model,
                )
                break
            if not self._is_backend_available(backend):
                logger.debug(
                    "Auto-router backend skipped (cooldown): backend=%s provider=%s model=%s",
                    backend.name,
                    backend.provider_name,
                    backend.model,
                )
                continue
            backend_timeout = self._timeout_seconds
            if index > 0:
                backend_timeout = min(
                    self._timeout_seconds,
                    self._fallback_backend_timeout_seconds,
                )
            if quick_command:
                backend_timeout = min(
                    backend_timeout,
                    self._quick_command_timeout_seconds,
                )
            try:
                logger.debug(
                    "Auto-router querying backend=%s provider=%s model=%s timeout=%.2fs",
                    backend.name,
                    backend.provider_name,
                    backend.model,
                    backend_timeout,
                )
                raw_reply = await self._ask_backend(
                    backend=backend,
                    user_id=message.user_id,
                    prompt=prompt,
                    timeout_seconds=backend_timeout,
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
            except asyncio.TimeoutError as exc:
                logger.warning(
                    "Auto-router backend timeout: backend=%s provider=%s model=%s timeout=%.2fs error=%s",
                    backend.name,
                    backend.provider_name,
                    backend.model,
                    backend_timeout,
                    exc,
                )
                self._record_backend_failure(backend)
                continue
            except Exception as exc:
                logger.warning(
                    "Auto-router backend failed: backend=%s provider=%s model=%s error_type=%s error=%s",
                    backend.name,
                    backend.provider_name,
                    backend.model,
                    type(exc).__name__,
                    exc,
                )
                self._record_backend_failure(backend)
                continue
            self._record_backend_success(backend)
            return normalized
        logger.warning("Auto-router failed on all backends; using fallback candidate ordering.")
        return self._build_fallback_decision(candidate_catalog)

    async def _ask_backend(
        self,
        *,
        backend: RouterBackend,
        user_id: int,
        prompt: str,
        timeout_seconds: float,
    ) -> str:
        backend_prompt = _prepare_router_prompt_for_backend(prompt=prompt, backend=backend)
        request_message = UserMessage(user_id=user_id, text=backend_prompt)

        async def _request() -> str:
            provider = backend.provider
            if hasattr(provider, "generate_reply_for_model"):
                return await provider.generate_reply_for_model(  # type: ignore[attr-defined]
                    message=request_message,
                    model=backend.model,
                )
            return await provider.generate_reply(request_message)

        reply = await asyncio.wait_for(_request(), timeout=timeout_seconds)
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


def _is_quick_command_request(text: str) -> bool:
    intent = _extract_last_user_intent(text)
    if not intent:
        return False
    normalized = " ".join(intent.split()).lower()
    if not normalized:
        return False
    if len(normalized) > _QUICK_COMMAND_MAX_CHARS:
        return False
    if "?" in normalized or any(normalized.startswith(item) for item in _QUICK_COMMAND_QUESTION_HINTS):
        return False
    return any(hint in normalized for hint in _QUICK_COMMAND_HINTS)


def _extract_last_user_intent(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    for raw_line in reversed(stripped.splitlines()):
        line = raw_line.strip()
        if not line:
            continue
        for prefix in _USER_LINE_PREFIXES:
            if line.startswith(prefix):
                return line.removeprefix(prefix).strip()
    return stripped


def _prepare_router_prompt_for_backend(*, prompt: str, backend: RouterBackend) -> str:
    normalized_provider = backend.provider_name.strip().lower()
    normalized_model = backend.model.strip().lower()
    if normalized_provider != "ollama":
        return prompt
    if not normalized_model.startswith(_QWEN_ROUTER_MODEL_PREFIX):
        return prompt
    stripped_prompt = prompt.lstrip()
    if stripped_prompt.startswith(_QWEN_NOTHINK_DIRECTIVE):
        return prompt
    return f"{_QWEN_NOTHINK_DIRECTIVE}\n{prompt}"
