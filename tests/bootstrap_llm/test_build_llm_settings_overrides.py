from ai_assistant.bootstrap_llm.build_llm_settings_overrides import build_llm_settings_overrides
from ai_assistant.config.settings import Settings


def test_build_llm_settings_overrides_adds_auto_provider_option(monkeypatch) -> None:
    monkeypatch.setattr("ai_assistant.config.settings.load_dotenv", lambda override=False: None)
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LLM_AVAILABLE_PROVIDERS", "ollama,openai")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.1")
    monkeypatch.setenv("OLLAMA_AVAILABLE_MODELS", "llama3.1")
    monkeypatch.setenv("AI_ASSISTANT_OPENAI_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("AI_ASSISTANT_OPENAI_AVAILABLE_MODELS", "gpt-4.1-mini")

    settings = Settings.from_env()
    definitions, options, translations, choice_translations = build_llm_settings_overrides(
        settings=settings,
        enabled_providers=("ollama", "openai"),
    )

    provider_options = [item for item in options if item.setting_id == "llm_provider"]
    names = [item.name for item in provider_options]
    assert names[0] == "auto"
    assert "ollama" in names
    assert "openai" in names

    auto_option = provider_options[0]
    assert auto_option.permission_type is None
    assert auto_option.permission_name is None

    ru_translations = choice_translations["ru"]
    assert ru_translations[("llm_provider", "auto")]["display_name"] == "Авто"
    assert any(item.key == "llm_auto_low_confidence_policy" for item in definitions)

    policy_options = [item for item in options if item.setting_id == "llm_auto_low_confidence_policy"]
    assert [item.name for item in policy_options] == ["keep_current", "upgrade_tier"]
    assert (
        ru_translations[("llm_auto_low_confidence_policy", "upgrade_tier")]["display_name"]
        == "Выбрать подороже"
    )
    assert (
        translations["ru"]["llm_auto_low_confidence_policy"]["title"]
        == "Политика при низкой уверенности"
    )
