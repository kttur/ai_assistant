from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True, frozen=True)
class ModelHealthSnapshot:
    target: str
    failure_count: int
    last_failure_at: datetime | None
    cooldown_until: datetime | None
    last_success_at: datetime | None
    is_available: bool


@dataclass(slots=True)
class _ModelHealthState:
    failure_count: int = 0
    last_failure_at: datetime | None = None
    cooldown_until: datetime | None = None
    last_success_at: datetime | None = None


class ModelHealthRegistry:
    def __init__(
        self,
        base_cooldown_seconds: int = 120,
        max_cooldown_seconds: int = 1800,
    ) -> None:
        self._base_cooldown_seconds = max(1, int(base_cooldown_seconds))
        self._max_cooldown_seconds = max(
            self._base_cooldown_seconds,
            int(max_cooldown_seconds),
        )
        self._states: dict[str, _ModelHealthState] = {}

    def is_available(self, target: str, now: datetime | None = None) -> bool:
        normalized = self._normalize_target(target)
        state = self._states.get(normalized)
        if state is None:
            return True
        if state.cooldown_until is None:
            return True
        ts = now or _utc_now()
        return ts >= state.cooldown_until

    def record_success(self, target: str, now: datetime | None = None) -> None:
        normalized = self._normalize_target(target)
        state = self._states.setdefault(normalized, _ModelHealthState())
        state.failure_count = 0
        state.last_success_at = now or _utc_now()
        state.cooldown_until = None
        logger.debug("Model health marked success: target=%s", normalized)

    def record_failure(self, target: str, now: datetime | None = None) -> None:
        normalized = self._normalize_target(target)
        state = self._states.setdefault(normalized, _ModelHealthState())
        ts = now or _utc_now()
        state.failure_count += 1
        state.last_failure_at = ts
        cooldown_seconds = min(
            self._max_cooldown_seconds,
            self._base_cooldown_seconds * (2 ** (state.failure_count - 1)),
        )
        state.cooldown_until = ts + timedelta(seconds=cooldown_seconds)
        logger.warning(
            "Model health failure recorded: target=%s failures=%d cooldown_until=%s",
            normalized,
            state.failure_count,
            state.cooldown_until.isoformat(),
        )

    def get_snapshot(self, target: str, now: datetime | None = None) -> ModelHealthSnapshot | None:
        normalized = self._normalize_target(target)
        state = self._states.get(normalized)
        if state is None:
            return None
        return ModelHealthSnapshot(
            target=normalized,
            failure_count=state.failure_count,
            last_failure_at=state.last_failure_at,
            cooldown_until=state.cooldown_until,
            last_success_at=state.last_success_at,
            is_available=self.is_available(normalized, now=now),
        )

    @staticmethod
    def build_target_key(provider: str, model: str | None = None, *, scope: str = "llm") -> str:
        normalized_provider = provider.strip().lower()
        normalized_model = (model or "").strip().lower()
        if normalized_model:
            return f"{scope}:{normalized_provider}:{normalized_model}"
        return f"{scope}:{normalized_provider}"

    @staticmethod
    def _normalize_target(target: str) -> str:
        normalized = target.strip().lower()
        if not normalized:
            raise ValueError("Health target key cannot be empty.")
        return normalized
