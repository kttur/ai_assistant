from __future__ import annotations

from ai_assistant.config.settings import Settings
from ai_assistant.core.interfaces import LLMProvider
from ai_assistant.providers.llm.anthropic_provider import AnthropicProvider
from ai_assistant.providers.llm.mock_provider import MockLLMProvider
from ai_assistant.providers.llm.ollama_provider import OllamaProvider
from ai_assistant.providers.llm.openai_provider import OpenAIProvider


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
        return OllamaProvider(base_url=settings.ollama_base_url, model=settings.ollama_model)
    raise ValueError(f"Unsupported LLM provider: {provider}")
