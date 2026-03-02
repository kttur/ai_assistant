import asyncio
import json
from unittest.mock import patch
from urllib import error

import pytest

from ai_assistant.core.models import UserMessage
from ai_assistant.providers.llm.ollama_provider import OllamaProvider


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        del exc_type, exc, tb
        return False

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def test_generate_reply_success() -> None:
    provider = OllamaProvider(base_url="http://localhost:11434", model="llama3.1")
    message = UserMessage(user_id=1, text="hello")

    with patch(
        "ai_assistant.providers.llm.ollama_provider.request.urlopen",
        return_value=_FakeResponse({"response": "Привет"}),
    ):
        result = asyncio.run(provider.generate_reply(message))

    assert result == "Привет"


def test_generate_reply_includes_system_prompt() -> None:
    provider = OllamaProvider(base_url="http://localhost:11434", model="llama3.1")
    message = UserMessage(user_id=1, text="hello")
    captured_payload: dict[str, object] = {}

    def _fake_urlopen(req, timeout):
        del timeout
        captured_payload.update(json.loads(req.data.decode("utf-8")))
        return _FakeResponse({"response": "ok"})

    with patch(
        "ai_assistant.providers.llm.ollama_provider.request.urlopen",
        side_effect=_fake_urlopen,
    ):
        asyncio.run(provider.generate_reply(message))

    assert captured_payload["model"] == "llama3.1"
    assert captured_payload["prompt"] == "hello"
    assert "Telegram HTML formatting only" in str(captured_payload["system"])


def test_generate_reply_api_error() -> None:
    provider = OllamaProvider(base_url="http://localhost:11434", model="llama3.1")
    message = UserMessage(user_id=1, text="hello")

    with patch(
        "ai_assistant.providers.llm.ollama_provider.request.urlopen",
        return_value=_FakeResponse({"error": "model not found"}),
    ):
        with pytest.raises(RuntimeError, match="Ollama API error"):
            asyncio.run(provider.generate_reply(message))


def test_generate_reply_url_error() -> None:
    provider = OllamaProvider(base_url="http://localhost:11434", model="llama3.1")
    message = UserMessage(user_id=1, text="hello")

    with patch(
        "ai_assistant.providers.llm.ollama_provider.request.urlopen",
        side_effect=error.URLError("refused"),
    ):
        with pytest.raises(RuntimeError, match="Ollama is unreachable"):
            asyncio.run(provider.generate_reply(message))
