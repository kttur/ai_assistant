from __future__ import annotations


def provider_display_name(provider: str) -> str:
    if provider == "auto":
        return "Auto"
    if provider == "openai":
        return "OpenAI"
    if provider == "anthropic":
        return "Anthropic"
    if provider == "ollama":
        return "Ollama"
    if provider == "mock":
        return "Mock"
    return provider
