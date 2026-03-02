from __future__ import annotations

import asyncio
import sys
import types

import pytest

from ai_assistant.core.models import UserMessage
from ai_assistant.providers.llm.anthropic_provider import AnthropicProvider


def _install_fake_anthropic_module(
    monkeypatch,
    *,
    response=None,
    raise_error: Exception | None = None,
):
    calls: list[dict[str, object]] = []
    init_args: dict[str, object] = {}

    class _FakeMessages:
        async def create(self, **kwargs):
            calls.append(dict(kwargs))
            if raise_error is not None:
                raise raise_error
            return response

    class _FakeClient:
        def __init__(self, api_key: str, base_url=None, timeout=None) -> None:
            init_args["api_key"] = api_key
            init_args["base_url"] = base_url
            init_args["timeout"] = timeout
            self.messages = _FakeMessages()

    fake_module = types.SimpleNamespace(AsyncAnthropic=_FakeClient)
    monkeypatch.setitem(sys.modules, "anthropic", fake_module)
    return calls, init_args


def test_anthropic_provider_requires_api_key() -> None:
    with pytest.raises(ValueError, match="AI_ASSISTANT_ANTHROPIC_API_KEY"):
        AnthropicProvider(api_key="", model="claude-3-5-sonnet-latest")


def test_anthropic_provider_generates_reply(monkeypatch) -> None:
    response = types.SimpleNamespace(content=[types.SimpleNamespace(text="Hello from Claude")])
    calls, init_args = _install_fake_anthropic_module(monkeypatch, response=response)
    provider = AnthropicProvider(
        api_key="anthropic-key",
        model="claude-3-5-sonnet-latest",
        base_url="https://api.anthropic.com",
    )

    reply = asyncio.run(provider.generate_reply(UserMessage(user_id=1, text="Hello")))

    assert reply == "Hello from Claude"
    assert init_args["api_key"] == "anthropic-key"
    assert init_args["base_url"] == "https://api.anthropic.com"
    assert calls
    assert calls[0]["model"] == "claude-3-5-sonnet-latest"
    assert calls[0]["messages"] == [{"role": "user", "content": "Hello"}]
    assert "Telegram HTML formatting only" in str(calls[0]["system"])


def test_anthropic_provider_uses_explicit_model(monkeypatch) -> None:
    response = types.SimpleNamespace(content=[types.SimpleNamespace(text="override model reply")])
    calls, _ = _install_fake_anthropic_module(monkeypatch, response=response)
    provider = AnthropicProvider(
        api_key="anthropic-key",
        model="claude-default",
    )

    reply = asyncio.run(
        provider.generate_reply_for_model(
            UserMessage(user_id=1, text="Hello"),
            model="claude-3-7-sonnet-latest",
        )
    )

    assert reply == "override model reply"
    assert calls[0]["model"] == "claude-3-7-sonnet-latest"


def test_anthropic_provider_raises_on_request_error(monkeypatch) -> None:
    _install_fake_anthropic_module(monkeypatch, raise_error=RuntimeError("bad request"))
    provider = AnthropicProvider(
        api_key="anthropic-key",
        model="claude-3-5-sonnet-latest",
    )

    with pytest.raises(RuntimeError, match="Anthropic request failed"):
        asyncio.run(provider.generate_reply(UserMessage(user_id=1, text="Hello")))


def test_anthropic_provider_raises_on_empty_response(monkeypatch) -> None:
    response = types.SimpleNamespace(content=[])
    _install_fake_anthropic_module(monkeypatch, response=response)
    provider = AnthropicProvider(
        api_key="anthropic-key",
        model="claude-3-5-sonnet-latest",
    )

    with pytest.raises(RuntimeError, match="Anthropic returned empty response"):
        asyncio.run(provider.generate_reply(UserMessage(user_id=1, text="Hello")))
