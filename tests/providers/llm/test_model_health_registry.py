from datetime import datetime, timedelta, timezone

from ai_assistant.providers.llm.model_health_registry import ModelHealthRegistry


def _dt(year: int, month: int, day: int, hour: int, minute: int, second: int) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)


def test_model_health_registry_marks_target_unavailable_during_cooldown() -> None:
    registry = ModelHealthRegistry(base_cooldown_seconds=60, max_cooldown_seconds=600)
    base_time = _dt(2026, 3, 3, 12, 0, 0)
    target = "llm:ollama:qwen3:8b"

    registry.record_failure(target, now=base_time)

    assert registry.is_available(target, now=base_time) is False
    assert registry.is_available(target, now=base_time + timedelta(seconds=30)) is False
    assert registry.is_available(target, now=base_time + timedelta(seconds=61)) is True


def test_model_health_registry_applies_exponential_backoff_and_resets_on_success() -> None:
    registry = ModelHealthRegistry(base_cooldown_seconds=30, max_cooldown_seconds=200)
    base_time = _dt(2026, 3, 3, 13, 0, 0)
    target = "llm:openai:gpt-4.1-mini"

    registry.record_failure(target, now=base_time)
    first = registry.get_snapshot(target, now=base_time)
    assert first is not None
    assert first.failure_count == 1
    assert first.cooldown_until == base_time + timedelta(seconds=30)

    registry.record_failure(target, now=base_time + timedelta(seconds=31))
    second = registry.get_snapshot(target, now=base_time + timedelta(seconds=31))
    assert second is not None
    assert second.failure_count == 2
    assert second.cooldown_until == base_time + timedelta(seconds=31 + 60)

    registry.record_success(target, now=base_time + timedelta(seconds=100))
    reset = registry.get_snapshot(target, now=base_time + timedelta(seconds=100))
    assert reset is not None
    assert reset.failure_count == 0
    assert reset.cooldown_until is None
    assert reset.is_available is True


def test_model_health_registry_build_target_key_normalizes_values() -> None:
    key = ModelHealthRegistry.build_target_key(
        provider=" OpenAI ",
        model=" GPT-4.1-mini ",
        scope="router",
    )
    assert key == "router:openai:gpt-4.1-mini"

