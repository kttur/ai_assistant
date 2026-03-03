from __future__ import annotations

import json

from ai_assistant.config.settings import Settings
from ai_assistant.core.interfaces import LLMProvider
from ai_assistant.providers.llm.anthropic_provider import AnthropicProvider
from ai_assistant.providers.llm.mock_provider import MockLLMProvider
from ai_assistant.providers.llm.ollama_provider import OllamaProvider
from ai_assistant.providers.llm.openai_provider import OpenAIProvider


def _parse_ollama_extra_headers(raw_value: str) -> dict[str, str]:
    cleaned = raw_value.strip()
    if not cleaned:
        return {}
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError("OLLAMA_EXTRA_HEADERS_JSON must be valid JSON object.") from exc
    if not isinstance(parsed, dict):
        raise ValueError("OLLAMA_EXTRA_HEADERS_JSON must be a JSON object.")

    normalized: dict[str, str] = {}
    for key, value in parsed.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("OLLAMA_EXTRA_HEADERS_JSON values must be strings.")
        header_name = key.strip().rstrip(":")
        header_value = value.strip()
        if header_name and header_value:
            normalized[header_name] = header_value
    return normalized


def build_single_llm_provider(provider: str, settings: Settings) -> LLMProvider:
    if provider == "mock":
        return MockLLMProvider()
    if provider == "openai":
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=settings.openai_base_url,
        )
    if provider == "anthropic":
        return AnthropicProvider(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
            base_url=settings.anthropic_base_url,
        )
    if provider == "ollama":
        return OllamaProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            auth_header_name=settings.ollama_auth_header_name,
            auth_header_value=settings.ollama_auth_header_value,
            extra_headers=_parse_ollama_extra_headers(settings.ollama_extra_headers_json),
        )
    raise ValueError(f"Unsupported LLM provider: {provider}")
