import asyncio

import pytest

from ai_assistant.core.models import UserMessage
from ai_assistant.providers.llm.auto_router_types import RouteArbiter, RouteCandidate, RouteDecision
from ai_assistant.providers.llm.model_health_registry import ModelHealthRegistry
from ai_assistant.providers.llm.model_manifest import ModelManifestEntry
from ai_assistant.providers.llm.user_selectable_provider import UserSelectableLLMProvider


class _FakeProvider:
    def __init__(self, name: str) -> None:
        self.name = name
        self.calls: list[tuple[int, str | None]] = []

    async def generate_reply_for_model(self, message: UserMessage, model: str | None = None) -> str:
        self.calls.append((message.user_id, model))
        return f"{self.name}:{model or '-'}"


class _FlakyProvider(_FakeProvider):
    def __init__(self, name: str, failing_models: set[str] | None = None) -> None:
        super().__init__(name)
        self.failing_models = failing_models or set()

    async def generate_reply_for_model(self, message: UserMessage, model: str | None = None) -> str:
        self.calls.append((message.user_id, model))
        if model in self.failing_models:
            raise RuntimeError(f"{self.name} failed for model {model}")
        return f"{self.name}:{model or '-'}"


class _ScriptedProvider(_FakeProvider):
    def __init__(self, name: str, replies: list[object]) -> None:
        super().__init__(name)
        self._replies = list(replies)
        self.messages: list[tuple[int, str | None, str]] = []

    async def generate_reply_for_model(self, message: UserMessage, model: str | None = None) -> str:
        self.calls.append((message.user_id, model))
        self.messages.append((message.user_id, model, message.text))
        if not self._replies:
            raise RuntimeError("No scripted response configured.")
        reply = self._replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return str(reply)


class _FakeStore:
    def __init__(self, data: dict[tuple[int, str], str] | None = None) -> None:
        self.data = data or {}

    async def get_setting(self, user_id: int, key: str) -> str | None:
        return self.data.get((user_id, key))


class _FakePermissionChecker:
    def __init__(self, allowed: set[tuple[int, str, str]]) -> None:
        self.allowed = allowed

    async def has_permission(self, user_id: int, permission_type: str, name: str) -> bool:
        return (user_id, permission_type, name) in self.allowed


class _FakeAutoRouter:
    def __init__(self, decisions: list[object]) -> None:
        self.decisions = list(decisions)
        self.calls: list[tuple[int, tuple[tuple[str, str], ...]]] = []

    async def route(self, *, message: UserMessage, candidate_catalog) -> RouteDecision:
        self.calls.append(
            (
                message.user_id,
                tuple((item.provider, item.model) for item in candidate_catalog),
            )
        )
        if not self.decisions:
            raise RuntimeError("No route decisions configured.")
        item = self.decisions.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class _CatalogSpyAutoRouter:
    def __init__(self, decision: RouteDecision) -> None:
        self.decision = decision
        self.catalogs = []

    async def route(self, *, message: UserMessage, candidate_catalog) -> RouteDecision:
        self.catalogs.append(candidate_catalog)
        return self.decision


def test_user_selectable_provider_uses_defaults() -> None:
    provider = _FakeProvider("openai")
    router = UserSelectableLLMProvider(
        providers={"openai": provider},
        default_provider="openai",
        default_models={"openai": "gpt-4.1-mini"},
        available_models={"openai": ("gpt-4.1-mini", "gpt-4.1")},
        user_settings_store=_FakeStore(),
    )

    result = asyncio.run(router.generate_reply(UserMessage(user_id=10, text="hi")))

    assert result == "openai:gpt-4.1-mini"
    assert provider.calls == [(10, "gpt-4.1-mini")]


def test_user_selectable_provider_uses_user_selected_provider_and_model() -> None:
    openai = _FakeProvider("openai")
    ollama = _FakeProvider("ollama")
    store = _FakeStore(
        {
            (20, "llm_provider"): "ollama",
            (20, "llm_model"): "ollama:llama3.2",
        }
    )
    router = UserSelectableLLMProvider(
        providers={"openai": openai, "ollama": ollama},
        default_provider="openai",
        default_models={"openai": "gpt-4.1-mini", "ollama": "llama3.1"},
        available_models={"openai": ("gpt-4.1-mini",), "ollama": ("llama3.1", "llama3.2")},
        user_settings_store=store,
    )

    result = asyncio.run(router.generate_reply(UserMessage(user_id=20, text="hi")))

    assert result == "ollama:llama3.2"
    assert ollama.calls == [(20, "llama3.2")]
    assert openai.calls == []


def test_user_selectable_provider_prefers_llm_provider_over_model_prefix() -> None:
    openai = _FakeProvider("openai")
    ollama = _FakeProvider("ollama")
    store = _FakeStore(
        {
            (25, "llm_provider"): "openai",
            (25, "llm_model"): "ollama:llama3.2",
        }
    )
    router = UserSelectableLLMProvider(
        providers={"openai": openai, "ollama": ollama},
        default_provider="ollama",
        default_models={"openai": "gpt-4.1-mini", "ollama": "llama3.1"},
        available_models={"openai": ("gpt-4.1-mini", "gpt-4.1"), "ollama": ("llama3.1", "llama3.2")},
        user_settings_store=store,
    )

    result = asyncio.run(router.generate_reply(UserMessage(user_id=25, text="hi")))

    assert result == "openai:gpt-4.1-mini"
    assert openai.calls == [(25, "gpt-4.1-mini")]
    assert ollama.calls == []


def test_user_selectable_provider_falls_back_for_invalid_model() -> None:
    provider = _FakeProvider("ollama")
    store = _FakeStore(
        {
            (30, "llm_provider"): "ollama",
            (30, "llm_model"): "ollama:not-allowed",
        }
    )
    router = UserSelectableLLMProvider(
        providers={"ollama": provider},
        default_provider="ollama",
        default_models={"ollama": "llama3.1"},
        available_models={"ollama": ("llama3.1", "llama3.2")},
        user_settings_store=store,
    )

    result = asyncio.run(router.generate_reply(UserMessage(user_id=30, text="hi")))

    assert result == "ollama:llama3.1"
    assert provider.calls == [(30, "llama3.1")]


def test_user_selectable_provider_respects_provider_permissions() -> None:
    openai = _FakeProvider("openai")
    ollama = _FakeProvider("ollama")
    store = _FakeStore({(40, "llm_provider"): "ollama"})
    permission_checker = _FakePermissionChecker(
        allowed={
            (40, "assistant", "llm.provider.openai"),
            (40, "assistant", "llm.model.openai:gpt-4.1-mini"),
        }
    )

    router = UserSelectableLLMProvider(
        providers={"openai": openai, "ollama": ollama},
        default_provider="openai",
        default_models={"openai": "gpt-4.1-mini", "ollama": "llama3.1"},
        available_models={"openai": ("gpt-4.1-mini",), "ollama": ("llama3.1",)},
        user_settings_store=store,
        permission_checker=permission_checker,
    )

    result = asyncio.run(router.generate_reply(UserMessage(user_id=40, text="hi")))

    assert result == "openai:gpt-4.1-mini"
    assert openai.calls == [(40, "gpt-4.1-mini")]
    assert ollama.calls == []


def test_user_selectable_provider_respects_model_permissions() -> None:
    openai = _FakeProvider("openai")
    store = _FakeStore({(50, "llm_model"): "openai:gpt-4.1"})
    permission_checker = _FakePermissionChecker(
        allowed={
            (50, "assistant", "llm.provider.openai"),
            (50, "assistant", "llm.model.openai:gpt-4.1-mini"),
        }
    )

    router = UserSelectableLLMProvider(
        providers={"openai": openai},
        default_provider="openai",
        default_models={"openai": "gpt-4.1-mini"},
        available_models={"openai": ("gpt-4.1-mini", "gpt-4.1")},
        user_settings_store=store,
        permission_checker=permission_checker,
    )

    result = asyncio.run(router.generate_reply(UserMessage(user_id=50, text="hi")))

    assert result == "openai:gpt-4.1-mini"
    assert openai.calls == [(50, "gpt-4.1-mini")]


def test_user_selectable_provider_raises_if_no_allowed_provider() -> None:
    openai = _FakeProvider("openai")
    permission_checker = _FakePermissionChecker(allowed=set())

    router = UserSelectableLLMProvider(
        providers={"openai": openai},
        default_provider="openai",
        default_models={"openai": "gpt-4.1-mini"},
        available_models={"openai": ("gpt-4.1-mini",)},
        user_settings_store=_FakeStore(),
        permission_checker=permission_checker,
    )

    with pytest.raises(RuntimeError, match="No permitted LLM providers"):
        asyncio.run(router.generate_reply(UserMessage(user_id=60, text="hi")))


def test_user_selectable_provider_does_not_fallback_for_explicit_model_provider() -> None:
    openai = _FakeProvider("openai")
    ollama = _FakeProvider("ollama")
    store = _FakeStore({(70, "llm_model"): "openai:gpt-4.1"})
    permission_checker = _FakePermissionChecker(
        allowed={
            (70, "assistant", "llm.provider.ollama"),
            (70, "assistant", "llm.model.ollama:llama3.1"),
        }
    )
    router = UserSelectableLLMProvider(
        providers={"openai": openai, "ollama": ollama},
        default_provider="ollama",
        default_models={"openai": "gpt-4.1-mini", "ollama": "llama3.1"},
        available_models={"openai": ("gpt-4.1-mini", "gpt-4.1"), "ollama": ("llama3.1",)},
        user_settings_store=store,
        permission_checker=permission_checker,
    )

    with pytest.raises(RuntimeError, match="Selected LLM provider is not permitted: openai"):
        asyncio.run(router.generate_reply(UserMessage(user_id=70, text="hi")))


def test_user_selectable_provider_raises_if_no_model_for_explicit_provider() -> None:
    openai = _FakeProvider("openai")
    ollama = _FakeProvider("ollama")
    store = _FakeStore({(80, "llm_model"): "openai:gpt-4.1"})
    permission_checker = _FakePermissionChecker(
        allowed={
            (80, "assistant", "llm.provider.openai"),
            (80, "assistant", "llm.provider.ollama"),
            (80, "assistant", "llm.model.ollama:llama3.1"),
        }
    )
    router = UserSelectableLLMProvider(
        providers={"openai": openai, "ollama": ollama},
        default_provider="ollama",
        default_models={"openai": "gpt-4.1-mini", "ollama": "llama3.1"},
        available_models={"openai": ("gpt-4.1-mini", "gpt-4.1"), "ollama": ("llama3.1",)},
        user_settings_store=store,
        permission_checker=permission_checker,
    )

    with pytest.raises(RuntimeError, match="No permitted LLM model for selected provider: openai"):
        asyncio.run(router.generate_reply(UserMessage(user_id=80, text="hi")))


def test_user_selectable_provider_raises_if_explicit_provider_not_configured() -> None:
    ollama = _FakeProvider("ollama")
    store = _FakeStore(
        {
            (90, "llm_provider"): "openai",
            (90, "llm_model"): "openai:gpt-5.2",
        }
    )
    router = UserSelectableLLMProvider(
        providers={"ollama": ollama},
        default_provider="ollama",
        default_models={"ollama": "llama3.1"},
        available_models={"ollama": ("llama3.1",)},
        user_settings_store=store,
    )

    with pytest.raises(RuntimeError, match="Selected LLM provider is not permitted: openai"):
        asyncio.run(router.generate_reply(UserMessage(user_id=90, text="hi")))


def test_user_selectable_provider_auto_mode_falls_back_to_next_candidate_on_runtime_failure() -> None:
    ollama = _FlakyProvider("ollama", failing_models={"llama3.1"})
    openai = _FakeProvider("openai")
    store = _FakeStore(
        {
            (100, "llm_provider"): "auto",
        }
    )
    auto_router = _FakeAutoRouter(
        [
            RouteDecision(
                confidence=0.8,
                risk_level="low",
                complexity="low",
                required_capabilities=("reasoning",),
                candidates=(
                    RouteCandidate(provider="ollama", model="llama3.1"),
                    RouteCandidate(provider="openai", model="gpt-4.1-mini"),
                ),
            )
        ]
    )
    health = ModelHealthRegistry(base_cooldown_seconds=300, max_cooldown_seconds=600)
    router = UserSelectableLLMProvider(
        providers={"ollama": ollama, "openai": openai},
        default_provider="openai",
        default_models={"openai": "gpt-4.1-mini", "ollama": "llama3.1"},
        available_models={"openai": ("gpt-4.1-mini",), "ollama": ("llama3.1",)},
        user_settings_store=store,
        auto_router=auto_router,
        health_registry=health,
    )

    result = asyncio.run(router.generate_reply(UserMessage(user_id=100, text="hello")))

    assert result == "openai:gpt-4.1-mini"
    assert ollama.calls == [(100, "llama3.1")]
    assert openai.calls == [(100, "gpt-4.1-mini")]
    snapshot = health.get_snapshot("llm:ollama:llama3.1")
    assert snapshot is not None
    assert snapshot.failure_count == 1
    assert snapshot.is_available is False


def test_user_selectable_provider_auto_mode_skips_unhealthy_candidate_until_cooldown_expires() -> None:
    ollama = _FlakyProvider("ollama", failing_models={"llama3.1"})
    openai = _FakeProvider("openai")
    store = _FakeStore(
        {
            (110, "llm_provider"): "auto",
        }
    )
    auto_router = _FakeAutoRouter(
        [
            RouteDecision(
                confidence=0.8,
                risk_level="low",
                complexity="low",
                required_capabilities=(),
                candidates=(
                    RouteCandidate(provider="ollama", model="llama3.1"),
                    RouteCandidate(provider="openai", model="gpt-4.1-mini"),
                ),
            ),
            RouteDecision(
                confidence=0.8,
                risk_level="low",
                complexity="low",
                required_capabilities=(),
                candidates=(
                    RouteCandidate(provider="ollama", model="llama3.1"),
                    RouteCandidate(provider="openai", model="gpt-4.1-mini"),
                ),
            ),
        ]
    )
    health = ModelHealthRegistry(base_cooldown_seconds=300, max_cooldown_seconds=600)
    router = UserSelectableLLMProvider(
        providers={"ollama": ollama, "openai": openai},
        default_provider="openai",
        default_models={"openai": "gpt-4.1-mini", "ollama": "llama3.1"},
        available_models={"openai": ("gpt-4.1-mini",), "ollama": ("llama3.1",)},
        user_settings_store=store,
        auto_router=auto_router,
        health_registry=health,
    )

    first = asyncio.run(router.generate_reply(UserMessage(user_id=110, text="one")))
    second = asyncio.run(router.generate_reply(UserMessage(user_id=110, text="two")))

    assert first == "openai:gpt-4.1-mini"
    assert second == "openai:gpt-4.1-mini"
    assert ollama.calls == [(110, "llama3.1")]
    assert openai.calls == [(110, "gpt-4.1-mini"), (110, "gpt-4.1-mini")]


def test_user_selectable_provider_auto_mode_falls_back_to_manual_selection_if_router_fails() -> None:
    openai = _FakeProvider("openai")
    store = _FakeStore(
        {
            (120, "llm_provider"): "auto",
        }
    )
    auto_router = _FakeAutoRouter([RuntimeError("router down")])
    router = UserSelectableLLMProvider(
        providers={"openai": openai},
        default_provider="openai",
        default_models={"openai": "gpt-4.1-mini"},
        available_models={"openai": ("gpt-4.1-mini",)},
        user_settings_store=store,
        auto_router=auto_router,
    )

    result = asyncio.run(router.generate_reply(UserMessage(user_id=120, text="hello")))

    assert result == "openai:gpt-4.1-mini"
    assert openai.calls == [(120, "gpt-4.1-mini")]


def test_user_selectable_provider_default_auto_mode_uses_router_without_explicit_user_setting() -> None:
    openai = _FakeProvider("openai")
    auto_router = _FakeAutoRouter(
        [
            RouteDecision(
                confidence=0.7,
                risk_level="medium",
                complexity="medium",
                required_capabilities=("reasoning",),
                candidates=(
                    RouteCandidate(provider="openai", model="gpt-4.1-mini"),
                ),
            )
        ]
    )
    router = UserSelectableLLMProvider(
        providers={"openai": openai},
        default_provider="openai",
        default_models={"openai": "gpt-4.1-mini"},
        available_models={"openai": ("gpt-4.1-mini",)},
        user_settings_store=_FakeStore(),
        auto_router=auto_router,
        default_selection_mode="auto",
    )

    result = asyncio.run(router.generate_reply(UserMessage(user_id=130, text="hello")))

    assert result == "openai:gpt-4.1-mini"
    assert len(auto_router.calls) == 1
    assert openai.calls == [(130, "gpt-4.1-mini")]


def test_auto_mode_low_confidence_keep_current_policy_preserves_router_priority() -> None:
    ollama = _FakeProvider("ollama")
    openai = _FakeProvider("openai")
    store = _FakeStore(
        {
            (140, "llm_provider"): "auto",
        }
    )
    auto_router = _FakeAutoRouter(
        [
            RouteDecision(
                confidence=0.2,
                risk_level="medium",
                complexity="medium",
                required_capabilities=(),
                candidates=(
                    RouteCandidate(provider="ollama", model="llama3.1"),
                    RouteCandidate(provider="openai", model="gpt-4.1-mini"),
                ),
            )
        ]
    )
    router = UserSelectableLLMProvider(
        providers={"ollama": ollama, "openai": openai},
        default_provider="openai",
        default_models={"openai": "gpt-4.1-mini", "ollama": "llama3.1"},
        available_models={"openai": ("gpt-4.1-mini",), "ollama": ("llama3.1",)},
        user_settings_store=store,
        auto_router=auto_router,
        auto_low_confidence_threshold=0.5,
    )

    result = asyncio.run(router.generate_reply(UserMessage(user_id=140, text="hello")))

    assert result == "ollama:llama3.1"
    assert ollama.calls == [(140, "llama3.1")]
    assert openai.calls == []


def test_auto_mode_low_confidence_upgrade_tier_policy_prefers_higher_tier_model() -> None:
    ollama = _FakeProvider("ollama")
    openai = _FakeProvider("openai")
    store = _FakeStore(
        {
            (150, "llm_provider"): "auto",
            (150, "llm_auto_low_confidence_policy"): "upgrade_tier",
        }
    )
    auto_router = _FakeAutoRouter(
        [
            RouteDecision(
                confidence=0.2,
                risk_level="medium",
                complexity="medium",
                required_capabilities=(),
                candidates=(
                    RouteCandidate(provider="ollama", model="llama3.1"),
                    RouteCandidate(provider="openai", model="gpt-4.1-mini"),
                ),
            )
        ]
    )
    router = UserSelectableLLMProvider(
        providers={"ollama": ollama, "openai": openai},
        default_provider="openai",
        default_models={"openai": "gpt-4.1-mini", "ollama": "llama3.1"},
        available_models={"openai": ("gpt-4.1-mini",), "ollama": ("llama3.1",)},
        user_settings_store=store,
        auto_router=auto_router,
        auto_low_confidence_threshold=0.5,
    )

    result = asyncio.run(router.generate_reply(UserMessage(user_id=150, text="hello")))

    assert result == "openai:gpt-4.1-mini"
    assert openai.calls == [(150, "gpt-4.1-mini")]
    assert ollama.calls == []


def test_auto_mode_high_complexity_prefers_stronger_specialist_from_manifest() -> None:
    ollama = _FlakyProvider("ollama", failing_models={"mistral-small3.2:24b"})
    openai = _FakeProvider("openai")
    store = _FakeStore(
        {
            (151, "llm_provider"): "auto",
        }
    )
    auto_router = _FakeAutoRouter(
        [
            RouteDecision(
                confidence=0.9,
                risk_level="medium",
                complexity="high",
                required_capabilities=("reasoning",),
                candidates=(
                    RouteCandidate(provider="ollama", model="mistral-small3.2:24b"),
                ),
            )
        ]
    )
    router = UserSelectableLLMProvider(
        providers={"ollama": ollama, "openai": openai},
        default_provider="openai",
        default_models={"openai": "gpt-5-mini", "ollama": "mistral-small3.2:24b"},
        available_models={"openai": ("gpt-5.2", "gpt-5-mini"), "ollama": ("mistral-small3.2:24b",)},
        user_settings_store=store,
        auto_router=auto_router,
        model_manifest_entries=(
            ModelManifestEntry(
                provider="ollama",
                model="mistral-small3.2:24b",
                roles=("specialist",),
                priority=30,
                strength=3,
            ),
            ModelManifestEntry(
                provider="openai",
                model="gpt-5.2",
                roles=("specialist",),
                priority=25,
                strength=5,
            ),
            ModelManifestEntry(
                provider="openai",
                model="gpt-5-mini",
                roles=("specialist",),
                priority=35,
                strength=4,
            ),
        ),
    )

    result = asyncio.run(router.generate_reply(UserMessage(user_id=151, text="hard task")))

    assert result == "openai:gpt-5.2"
    assert openai.calls == [(151, "gpt-5.2")]
    assert ollama.calls == [(151, "mistral-small3.2:24b")]


def test_auto_mode_arbiter_can_edit_specialist_answer() -> None:
    specialist = _ScriptedProvider("ollama", replies=["draft answer"])
    arbiter = _ScriptedProvider(
        "openai",
        replies=[
            '{"action":"edit","final_answer":"edited answer","feedback":"fixed wording"}',
        ],
    )
    store = _FakeStore(
        {
            (160, "llm_provider"): "auto",
        }
    )
    auto_router = _FakeAutoRouter(
        [
            RouteDecision(
                confidence=0.8,
                risk_level="medium",
                complexity="medium",
                required_capabilities=(),
                candidates=(RouteCandidate(provider="ollama", model="llama3.1"),),
                arbiter=RouteArbiter(
                    enabled=True,
                    provider="openai",
                    model="gpt-4.1-mini",
                ),
            )
        ]
    )
    router = UserSelectableLLMProvider(
        providers={"ollama": specialist, "openai": arbiter},
        default_provider="ollama",
        default_models={"openai": "gpt-4.1-mini", "ollama": "llama3.1"},
        available_models={"openai": ("gpt-4.1-mini",), "ollama": ("llama3.1",)},
        user_settings_store=store,
        auto_router=auto_router,
    )

    result = asyncio.run(router.generate_reply(UserMessage(user_id=160, text="question")))

    assert result == "edited answer"
    assert specialist.calls == [(160, "llama3.1")]
    assert arbiter.calls == [(160, "gpt-4.1-mini")]
    assert "draft answer" in arbiter.messages[0][2]


def test_auto_mode_arbiter_can_request_single_regeneration() -> None:
    specialist = _ScriptedProvider("ollama", replies=["first draft", "regenerated draft"])
    arbiter = _ScriptedProvider(
        "openai",
        replies=[
            (
                '{"action":"regenerate","feedback":"missing details",'
                '"regenerate_prompt":"add implementation details"}'
            ),
        ],
    )
    store = _FakeStore(
        {
            (170, "llm_provider"): "auto",
        }
    )
    auto_router = _FakeAutoRouter(
        [
            RouteDecision(
                confidence=0.8,
                risk_level="medium",
                complexity="high",
                required_capabilities=("reasoning",),
                candidates=(RouteCandidate(provider="ollama", model="llama3.1"),),
                arbiter=RouteArbiter(
                    enabled=True,
                    provider="openai",
                    model="gpt-4.1-mini",
                ),
            )
        ]
    )
    router = UserSelectableLLMProvider(
        providers={"ollama": specialist, "openai": arbiter},
        default_provider="ollama",
        default_models={"openai": "gpt-4.1-mini", "ollama": "llama3.1"},
        available_models={"openai": ("gpt-4.1-mini",), "ollama": ("llama3.1",)},
        user_settings_store=store,
        auto_router=auto_router,
    )

    result = asyncio.run(router.generate_reply(UserMessage(user_id=170, text="question")))

    assert result == "regenerated draft"
    assert specialist.calls == [(170, "llama3.1"), (170, "llama3.1")]
    assert arbiter.calls == [(170, "gpt-4.1-mini")]
    assert "missing details" in specialist.messages[1][2]
    assert "add implementation details" in specialist.messages[1][2]


def test_auto_mode_uses_high_risk_arbiter_even_when_router_arbiter_missing() -> None:
    specialist = _ScriptedProvider("ollama", replies=["specialist answer"])
    arbiter = _ScriptedProvider(
        "openai",
        replies=['{"action":"approve","feedback":"looks good"}'],
    )
    store = _FakeStore(
        {
            (180, "llm_provider"): "auto",
        }
    )
    auto_router = _FakeAutoRouter(
        [
            RouteDecision(
                confidence=0.9,
                risk_level="high",
                complexity="high",
                required_capabilities=("reasoning",),
                candidates=(RouteCandidate(provider="ollama", model="llama3.1"),),
                arbiter=None,
            )
        ]
    )
    router = UserSelectableLLMProvider(
        providers={"ollama": specialist, "openai": arbiter},
        default_provider="ollama",
        default_models={"openai": "gpt-4.1-mini", "ollama": "llama3.1"},
        available_models={"openai": ("gpt-4.1-mini",), "ollama": ("llama3.1",)},
        user_settings_store=store,
        auto_router=auto_router,
    )

    result = asyncio.run(router.generate_reply(UserMessage(user_id=180, text="question")))

    assert result == "specialist answer"
    assert specialist.calls == [(180, "llama3.1")]
    assert arbiter.calls == [(180, "gpt-4.1-mini")]


def test_catalog_notes_marks_local_medical_models() -> None:
    notes = UserSelectableLLMProvider._catalog_notes(
        provider="ollama",
        model="puyangwang/medgemma-27b-it:q6",
    )

    assert notes == "local medical-specialist runtime"


def test_catalog_notes_marks_local_general_models() -> None:
    notes = UserSelectableLLMProvider._catalog_notes(
        provider="ollama",
        model="mistral-small3.2:24b",
    )

    assert notes == "local general-purpose runtime"


def test_model_cost_tier_treats_mid_size_local_models_as_balanced() -> None:
    assert (
        UserSelectableLLMProvider._model_cost_tier(
            provider="ollama",
            model="mistral-small3.2:24b",
        )
        == "balanced_local"
    )


def test_auto_mode_catalog_uses_manifest_metadata_and_skips_router_only_models() -> None:
    specialist = _FakeProvider("ollama")
    store = _FakeStore(
        {
            (190, "llm_provider"): "auto",
        }
    )
    auto_router = _CatalogSpyAutoRouter(
        RouteDecision(
            confidence=0.7,
            risk_level="medium",
            complexity="medium",
            required_capabilities=("reasoning",),
            candidates=(RouteCandidate(provider="ollama", model="mistral-small3.2:24b"),),
        )
    )
    router = UserSelectableLLMProvider(
        providers={"ollama": specialist},
        default_provider="ollama",
        default_models={"ollama": "mistral-small3.2:24b"},
        available_models={"ollama": ("mistral-small3.2:24b", "qwen3:4b")},
        user_settings_store=store,
        auto_router=auto_router,
        model_manifest_entries=(
            ModelManifestEntry(
                provider="ollama",
                model="qwen3:4b",
                roles=("router",),
                tags=("fast", "small"),
                domains=("general",),
            ),
            ModelManifestEntry(
                provider="ollama",
                model="mistral-small3.2:24b",
                roles=("specialist",),
                tags=("general", "reasoning"),
                domains=("general",),
                notes="primary local specialist",
                supports_reasoning=True,
                supports_non_reasoning=True,
                abilities=("text", "tool_calling"),
            ),
        ),
    )

    result = asyncio.run(router.generate_reply(UserMessage(user_id=190, text="explain this topic")))

    assert result == "ollama:mistral-small3.2:24b"
    assert specialist.calls == [(190, "mistral-small3.2:24b")]
    assert len(auto_router.catalogs) == 1
    catalog = auto_router.catalogs[0]
    assert len(catalog) == 1
    assert catalog[0].provider == "ollama"
    assert catalog[0].model == "mistral-small3.2:24b"
    assert catalog[0].notes == "primary local specialist"
    assert catalog[0].tags == ("general", "reasoning")
    assert catalog[0].domains == ("general",)
    assert catalog[0].supports_reasoning is True
    assert catalog[0].supports_non_reasoning is True
    assert catalog[0].abilities == ("text", "tool_calling")


def test_auto_mode_catalog_in_strict_manifest_mode_ignores_non_manifest_models() -> None:
    ollama = _FakeProvider("ollama")
    openai = _FakeProvider("openai")
    store = _FakeStore(
        {
            (191, "llm_provider"): "auto",
        }
    )
    auto_router = _CatalogSpyAutoRouter(
        RouteDecision(
            confidence=0.8,
            risk_level="low",
            complexity="low",
            required_capabilities=(),
            candidates=(RouteCandidate(provider="ollama", model="qwen3:8b"),),
        )
    )
    router = UserSelectableLLMProvider(
        providers={"openai": openai, "ollama": ollama},
        default_provider="ollama",
        default_models={"openai": "gpt-5-mini", "ollama": "qwen3:8b"},
        available_models={
            "openai": ("gpt-5-mini", "gpt-5-nano"),
            "ollama": ("qwen3:8b", "qwen3:4b", "qwen3:4b-instruct"),
        },
        user_settings_store=store,
        auto_router=auto_router,
        model_manifest_entries=(
            ModelManifestEntry(
                provider="ollama",
                model="qwen3:8b",
                roles=("specialist",),
            ),
            ModelManifestEntry(
                provider="openai",
                model="gpt-5-mini",
                roles=("specialist",),
            ),
        ),
    )

    result = asyncio.run(router.generate_reply(UserMessage(user_id=191, text="resume playback")))

    assert result == "ollama:qwen3:8b"
    assert ollama.calls == [(191, "qwen3:8b")]
    assert len(auto_router.catalogs) == 1
    catalog = auto_router.catalogs[0]
    assert tuple((item.provider, item.model) for item in catalog) == (
        ("ollama", "qwen3:8b"),
        ("openai", "gpt-5-mini"),
    )
