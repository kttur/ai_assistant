import json

from ai_assistant.bootstrap_llm.build_models_for_provider import build_models_for_provider
from ai_assistant.config.settings import Settings


def test_build_models_for_provider_prefers_manifest_models_when_present(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("ai_assistant.config.settings.load_dotenv", lambda override=False: None)
    manifest_path = tmp_path / "model_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "version": 1,
                "models": [
                    {"provider": "ollama", "model": "qwen3:8b"},
                    {"provider": "ollama", "model": "mistral-small3.2:24b"},
                    {"provider": "openai", "model": "gpt-5-mini"},
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("AI_ASSISTANT_MODEL_MANIFEST_PATH", str(manifest_path))
    monkeypatch.setenv("OLLAMA_MODEL", "mistral-small3.2:24b")
    monkeypatch.setenv(
        "OLLAMA_AVAILABLE_MODELS",
        "mistral-small3.2:24b,puyangwang/medgemma-27b-it:q6",
    )

    settings = Settings.from_env()
    models = build_models_for_provider(settings, "ollama")

    assert models == ("qwen3:8b", "mistral-small3.2:24b")


def test_build_models_for_provider_uses_env_when_manifest_is_empty(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("ai_assistant.config.settings.load_dotenv", lambda override=False: None)
    manifest_path = tmp_path / "model_manifest.json"
    manifest_path.write_text(json.dumps({"version": 1, "models": []}), encoding="utf-8")
    monkeypatch.setenv("AI_ASSISTANT_MODEL_MANIFEST_PATH", str(manifest_path))
    monkeypatch.setenv("OLLAMA_MODEL", "mistral-small3.2:24b")
    monkeypatch.setenv(
        "OLLAMA_AVAILABLE_MODELS",
        "mistral-small3.2:24b,puyangwang/medgemma-27b-it:q6",
    )

    settings = Settings.from_env()
    models = build_models_for_provider(settings, "ollama")

    assert models == ("mistral-small3.2:24b", "puyangwang/medgemma-27b-it:q6")
