import asyncio
import time

from ai_assistant.core.models import UserMessage
from ai_assistant.providers.llm.auto_router import PolicyBasedAutoRouter, RouterBackend
from ai_assistant.providers.llm.auto_router_types import RouterCatalogEntry
from ai_assistant.providers.llm.model_health_registry import ModelHealthRegistry


class _FakeProvider:
    def __init__(self, replies: list[object]) -> None:
        self._replies = list(replies)
        self.calls: list[tuple[int, str | None]] = []
        self.prompts: list[str] = []

    async def generate_reply_for_model(self, message: UserMessage, model: str | None = None) -> str:
        self.calls.append((message.user_id, model))
        self.prompts.append(message.text)
        if not self._replies:
            raise RuntimeError("No more fake replies configured.")
        reply = self._replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return str(reply)


class _SlowProvider:
    def __init__(self, sleep_seconds: float) -> None:
        self._sleep_seconds = sleep_seconds
        self.calls: list[tuple[int, str | None]] = []

    async def generate_reply_for_model(self, message: UserMessage, model: str | None = None) -> str:
        self.calls.append((message.user_id, model))
        await asyncio.sleep(self._sleep_seconds)
        return '{"confidence":0.6,"candidates":[{"provider":"openai","model":"gpt-4.1-mini"}]}'


def _catalog() -> tuple[RouterCatalogEntry, ...]:
    return (
        RouterCatalogEntry(
            provider="ollama",
            model="qwen3:8b",
            platform="local",
            cost_tier="cheap_local",
        ),
        RouterCatalogEntry(
            provider="openai",
            model="gpt-4.1-mini",
            platform="cloud",
            cost_tier="balanced_cloud",
        ),
    )


def test_policy_router_uses_primary_backend_when_json_is_valid() -> None:
    primary = _FakeProvider(
        [
            '{"confidence":0.8,"candidates":[{"provider":"ollama","model":"qwen3:8b"}]}',
        ]
    )
    fallback = _FakeProvider([])
    router = PolicyBasedAutoRouter(
        backends=(
            RouterBackend(
                name="local",
                provider_name="ollama",
                model="qwen3:8b",
                provider=primary,
            ),
            RouterBackend(
                name="cloud",
                provider_name="openai",
                model="gpt-4.1-mini",
                provider=fallback,
            ),
        )
    )

    decision = asyncio.run(
        router.route(
            message=UserMessage(user_id=101, text="simple question"),
            candidate_catalog=_catalog(),
        )
    )

    assert decision.candidates[0].provider == "ollama"
    assert primary.calls == [(101, "qwen3:8b")]
    assert fallback.calls == []


def test_policy_router_falls_back_to_secondary_backend_on_primary_failure() -> None:
    primary = _FakeProvider([RuntimeError("primary down")])
    fallback = _FakeProvider(
        [
            '{"confidence":0.7,"candidates":[{"provider":"openai","model":"gpt-4.1-mini"}]}',
        ]
    )
    health = ModelHealthRegistry(base_cooldown_seconds=300, max_cooldown_seconds=600)
    router = PolicyBasedAutoRouter(
        backends=(
            RouterBackend(
                name="local",
                provider_name="ollama",
                model="qwen3:8b",
                provider=primary,
            ),
            RouterBackend(
                name="cloud",
                provider_name="openai",
                model="gpt-4.1-mini",
                provider=fallback,
            ),
        ),
        health_registry=health,
    )

    decision = asyncio.run(
        router.route(
            message=UserMessage(user_id=102, text="complex question"),
            candidate_catalog=_catalog(),
        )
    )

    assert decision.candidates[0].provider == "openai"
    assert primary.calls == [(102, "qwen3:8b")]
    assert fallback.calls == [(102, "gpt-4.1-mini")]

    primary_snapshot = health.get_snapshot("router:ollama:qwen3:8b")
    assert primary_snapshot is not None
    assert primary_snapshot.failure_count == 1
    assert primary_snapshot.is_available is False


def test_policy_router_skips_backend_while_cooldown_active() -> None:
    primary = _FakeProvider([])
    fallback = _FakeProvider(
        [
            '{"confidence":0.6,"candidates":[{"provider":"openai","model":"gpt-4.1-mini"}]}',
        ]
    )
    health = ModelHealthRegistry(base_cooldown_seconds=300, max_cooldown_seconds=600)
    health.record_failure("router:ollama:qwen3:8b")
    router = PolicyBasedAutoRouter(
        backends=(
            RouterBackend(
                name="local",
                provider_name="ollama",
                model="qwen3:8b",
                provider=primary,
            ),
            RouterBackend(
                name="cloud",
                provider_name="openai",
                model="gpt-4.1-mini",
                provider=fallback,
            ),
        ),
        health_registry=health,
    )

    decision = asyncio.run(
        router.route(
            message=UserMessage(user_id=103, text="another question"),
            candidate_catalog=_catalog(),
        )
    )

    assert decision.candidates[0].provider == "openai"
    assert primary.calls == []
    assert fallback.calls == [(103, "gpt-4.1-mini")]


def test_policy_router_uses_short_timeout_for_fallback_backend() -> None:
    primary = _FakeProvider([RuntimeError("primary down")])
    fallback = _SlowProvider(sleep_seconds=0.35)
    router = PolicyBasedAutoRouter(
        backends=(
            RouterBackend(
                name="local",
                provider_name="ollama",
                model="qwen3:8b",
                provider=primary,
            ),
            RouterBackend(
                name="cloud",
                provider_name="openai",
                model="gpt-4.1-mini",
                provider=fallback,
            ),
        ),
        timeout_seconds=1.0,
        fallback_backend_timeout_seconds=0.05,
    )

    started = time.perf_counter()
    decision = asyncio.run(
        router.route(
            message=UserMessage(user_id=104, text="simple question"),
            candidate_catalog=_catalog(),
        )
    )
    elapsed = time.perf_counter() - started

    assert elapsed < 0.25
    assert decision.candidates[0].provider == "ollama"
    assert primary.calls == [(104, "qwen3:8b")]
    assert fallback.calls == [(104, "gpt-4.1-mini")]


def test_policy_router_quick_command_skips_secondary_backend() -> None:
    primary = _FakeProvider([RuntimeError("primary down")])
    fallback = _FakeProvider(
        [
            '{"confidence":0.9,"candidates":[{"provider":"openai","model":"gpt-4.1-mini"}]}',
        ]
    )
    router = PolicyBasedAutoRouter(
        backends=(
            RouterBackend(
                name="local",
                provider_name="ollama",
                model="qwen3:8b",
                provider=primary,
            ),
            RouterBackend(
                name="cloud",
                provider_name="openai",
                model="gpt-4.1-mini",
                provider=fallback,
            ),
        ),
        timeout_seconds=5.0,
        fallback_backend_timeout_seconds=5.0,
        quick_command_timeout_seconds=0.1,
        fast_path_enabled=False,  # Disable fast path to test router backend behavior
    )

    decision = asyncio.run(
        router.route(
            message=UserMessage(user_id=105, text="Поставь на паузу"),
            candidate_catalog=_catalog(),
        )
    )

    assert decision.candidates[0].provider == "ollama"
    assert primary.calls == [(105, "qwen3:8b")]
    assert fallback.calls == []


def test_policy_router_applies_nothink_directive_for_qwen3_router_backend() -> None:
    primary = _FakeProvider(
        [
            '{"confidence":0.8,"candidates":[{"provider":"ollama","model":"qwen3:8b"}]}',
        ]
    )
    fallback = _FakeProvider([])
    router = PolicyBasedAutoRouter(
        backends=(
            RouterBackend(
                name="local",
                provider_name="ollama",
                model="qwen3:8b",
                provider=primary,
            ),
            RouterBackend(
                name="cloud",
                provider_name="openai",
                model="gpt-4.1-mini",
                provider=fallback,
            ),
        )
    )

    decision = asyncio.run(
        router.route(
            message=UserMessage(user_id=106, text="simple question"),
            candidate_catalog=_catalog(),
        )
    )

    assert decision.candidates[0].provider == "ollama"
    assert primary.calls == [(106, "qwen3:8b")]
    assert primary.prompts
    assert primary.prompts[0].startswith("/nothink\n")
