from ai_assistant.bootstrap_llm.build_available_provider_names import build_available_provider_names
from ai_assistant.config.settings import Settings


def test_build_available_provider_names_allows_auto_default_provider(monkeypatch) -> None:
    monkeypatch.setattr("ai_assistant.config.settings.load_dotenv", lambda override=False: None)
    monkeypatch.setenv("LLM_PROVIDER", "auto")
    monkeypatch.setenv("LLM_AVAILABLE_PROVIDERS", "auto,ollama,openai")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.1")
    monkeypatch.setenv("OLLAMA_AVAILABLE_MODELS", "llama3.1")

    settings = Settings.from_env()
    providers = build_available_provider_names(settings)

    assert "ollama" in providers
    assert "auto" not in providers

