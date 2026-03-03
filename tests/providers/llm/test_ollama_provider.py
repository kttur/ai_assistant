import asyncio
import io
import json
from unittest.mock import patch
from urllib import error, request

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


def test_generate_reply_includes_auth_header() -> None:
    provider = OllamaProvider(
        base_url="http://localhost:11434",
        model="llama3.1",
        auth_header_name="Authorization",
        auth_header_value="Bearer secret-token",
    )
    message = UserMessage(user_id=1, text="hello")
    captured_headers: dict[str, str] = {}

    def _fake_urlopen(req, timeout):
        del timeout
        captured_headers.update({k.lower(): v for k, v in req.header_items()})
        return _FakeResponse({"response": "ok"})

    with patch(
        "ai_assistant.providers.llm.ollama_provider.request.urlopen",
        side_effect=_fake_urlopen,
    ):
        asyncio.run(provider.generate_reply(message))

    assert captured_headers["authorization"] == "Bearer secret-token"


def test_generate_reply_includes_extra_headers() -> None:
    provider = OllamaProvider(
        base_url="http://localhost:11434",
        model="llama3.1",
        extra_headers={
            "CF-Access-Client-Id": "client-id",
            "CF-Access-Client-Secret": "client-secret",
        },
    )
    message = UserMessage(user_id=1, text="hello")
    captured_headers: dict[str, str] = {}

    def _fake_urlopen(req, timeout):
        del timeout
        captured_headers.update({k.lower(): v for k, v in req.header_items()})
        return _FakeResponse({"response": "ok"})

    with patch(
        "ai_assistant.providers.llm.ollama_provider.request.urlopen",
        side_effect=_fake_urlopen,
    ):
        asyncio.run(provider.generate_reply(message))

    assert captured_headers["cf-access-client-id"] == "client-id"
    assert captured_headers["cf-access-client-secret"] == "client-secret"


def test_generate_reply_retries_with_trailing_slash_on_403() -> None:
    provider = OllamaProvider(base_url="https://olm.kottur.net", model="llama3.1")
    message = UserMessage(user_id=1, text="hello")
    called_urls: list[str] = []

    def _fake_urlopen(req, timeout):
        del timeout
        called_urls.append(req.full_url)
        if len(called_urls) == 1:
            raise error.HTTPError(
                url=req.full_url,
                code=403,
                msg="Forbidden",
                hdrs=None,
                fp=io.BytesIO(b"error code: 1010"),
            )
        return _FakeResponse({"response": "ok"})

    with patch(
        "ai_assistant.providers.llm.ollama_provider.request.urlopen",
        side_effect=_fake_urlopen,
    ):
        result = asyncio.run(provider.generate_reply(message))

    assert result == "ok"
    assert called_urls == [
        "https://olm.kottur.net/api/generate",
        "https://olm.kottur.net/api/generate/",
    ]


def test_generate_reply_sets_requests_like_user_agent() -> None:
    provider = OllamaProvider(base_url="http://localhost:11434", model="llama3.1")
    message = UserMessage(user_id=1, text="hello")
    captured_headers: dict[str, str] = {}

    def _fake_urlopen(req: request.Request, timeout):
        del timeout
        captured_headers.update({k.lower(): v for k, v in req.header_items()})
        return _FakeResponse({"response": "ok"})

    with patch(
        "ai_assistant.providers.llm.ollama_provider.request.urlopen",
        side_effect=_fake_urlopen,
    ):
        asyncio.run(provider.generate_reply(message))

    assert captured_headers["user-agent"] == "python-requests/2.32.3"


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
