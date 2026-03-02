from ai_assistant.config.settings import Settings


OPENAI_ENV_KEYS = (
    "AI_ASSISTANT_OPENAI_API_KEY",
    "AI_ASSISTANT_OPENAI_BASE_URL",
    "AI_ASSISTANT_OPENAI_MODEL",
    "AI_ASSISTANT_OPENAI_AVAILABLE_MODELS",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_MODEL",
    "OPENAI_AVAILABLE_MODELS",
    "OPENAI_API_KEY_1",
    "OPENAI_BASE_URL_1",
)

ANTHROPIC_ENV_KEYS = (
    "AI_ASSISTANT_ANTHROPIC_API_KEY",
    "AI_ASSISTANT_ANTHROPIC_BASE_URL",
    "AI_ASSISTANT_ANTHROPIC_MODEL",
    "AI_ASSISTANT_ANTHROPIC_AVAILABLE_MODELS",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_MODEL",
    "ANTHROPIC_AVAILABLE_MODELS",
)


def _clear_openai_env(monkeypatch) -> None:
    for key in OPENAI_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def _clear_anthropic_env(monkeypatch) -> None:
    for key in ANTHROPIC_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_from_env_reads_ai_assistant_openai_variables(monkeypatch) -> None:
    monkeypatch.setattr("ai_assistant.config.settings.load_dotenv", lambda override=False: None)
    _clear_openai_env(monkeypatch)
    monkeypatch.setenv("AI_ASSISTANT_OPENAI_API_KEY", "new-key")
    monkeypatch.setenv("AI_ASSISTANT_OPENAI_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("AI_ASSISTANT_OPENAI_MODEL", "gpt-x")
    monkeypatch.setenv("AI_ASSISTANT_OPENAI_AVAILABLE_MODELS", "gpt-x,gpt-y")

    settings = Settings.from_env()

    assert settings.openai_api_key == "new-key"
    assert settings.openai_base_url == "https://example.test/v1"
    assert settings.openai_model == "gpt-x"
    assert settings.openai_available_models == ("gpt-x", "gpt-y")


def test_from_env_keeps_openai_legacy_fallback(monkeypatch) -> None:
    monkeypatch.setattr("ai_assistant.config.settings.load_dotenv", lambda override=False: None)
    _clear_openai_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "legacy-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://legacy.test/v1")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-legacy")
    monkeypatch.setenv("OPENAI_AVAILABLE_MODELS", "gpt-legacy,gpt-legacy-2")

    settings = Settings.from_env()

    assert settings.openai_api_key == "legacy-key"
    assert settings.openai_base_url == "https://legacy.test/v1"
    assert settings.openai_model == "gpt-legacy"
    assert settings.openai_available_models == ("gpt-legacy", "gpt-legacy-2")


def test_from_env_prefers_new_openai_variables_over_legacy(monkeypatch) -> None:
    monkeypatch.setattr("ai_assistant.config.settings.load_dotenv", lambda override=False: None)
    _clear_openai_env(monkeypatch)
    monkeypatch.setenv("AI_ASSISTANT_OPENAI_MODEL", "gpt-new")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-legacy")
    monkeypatch.setenv("AI_ASSISTANT_OPENAI_AVAILABLE_MODELS", "gpt-new,gpt-new-2")
    monkeypatch.setenv("OPENAI_AVAILABLE_MODELS", "gpt-legacy,gpt-legacy-2")
    monkeypatch.setenv("AI_ASSISTANT_OPENAI_API_KEY", "new-key")
    monkeypatch.setenv("OPENAI_API_KEY", "legacy-key")
    monkeypatch.setenv("AI_ASSISTANT_OPENAI_BASE_URL", "https://new.example/v1")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://legacy.example/v1")

    settings = Settings.from_env()

    assert settings.openai_api_key == "new-key"
    assert settings.openai_base_url == "https://new.example/v1"
    assert settings.openai_model == "gpt-new"
    assert settings.openai_available_models == ("gpt-new", "gpt-new-2")


def test_from_env_reads_ai_assistant_anthropic_variables(monkeypatch) -> None:
    monkeypatch.setattr("ai_assistant.config.settings.load_dotenv", lambda override=False: None)
    _clear_anthropic_env(monkeypatch)
    monkeypatch.setenv("AI_ASSISTANT_ANTHROPIC_API_KEY", "anthropic-new-key")
    monkeypatch.setenv("AI_ASSISTANT_ANTHROPIC_BASE_URL", "https://anthropic.example/v1")
    monkeypatch.setenv("AI_ASSISTANT_ANTHROPIC_MODEL", "claude-x")
    monkeypatch.setenv("AI_ASSISTANT_ANTHROPIC_AVAILABLE_MODELS", "claude-x,claude-y")

    settings = Settings.from_env()

    assert settings.anthropic_api_key == "anthropic-new-key"
    assert settings.anthropic_base_url == "https://anthropic.example/v1"
    assert settings.anthropic_model == "claude-x"
    assert settings.anthropic_available_models == ("claude-x", "claude-y")


def test_from_env_keeps_anthropic_legacy_fallback(monkeypatch) -> None:
    monkeypatch.setattr("ai_assistant.config.settings.load_dotenv", lambda override=False: None)
    _clear_anthropic_env(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-legacy-key")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://legacy.anthropic.example/v1")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-legacy")
    monkeypatch.setenv("ANTHROPIC_AVAILABLE_MODELS", "claude-legacy,claude-legacy-2")

    settings = Settings.from_env()

    assert settings.anthropic_api_key == "anthropic-legacy-key"
    assert settings.anthropic_base_url == "https://legacy.anthropic.example/v1"
    assert settings.anthropic_model == "claude-legacy"
    assert settings.anthropic_available_models == ("claude-legacy", "claude-legacy-2")
