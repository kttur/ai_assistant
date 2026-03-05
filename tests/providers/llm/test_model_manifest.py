import json

from ai_assistant.providers.llm.model_manifest import (
    build_manifest_index,
    load_model_manifest,
    manifest_entry_key,
    models_for_provider,
)


def test_load_model_manifest_parses_entries(tmp_path) -> None:
    manifest_path = tmp_path / "model_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "version": 1,
                "models": [
                    {
                        "provider": "ollama",
                        "model": "qwen3:4b",
                        "roles": ["router"],
                        "tags": ["fast", "small"],
                        "domains": ["general"],
                        "platform": "local",
                        "cost_tier": "cheap_local",
                        "notes": "routing",
                        "priority": 11,
                        "strength": 2,
                        "supports_reasoning": True,
                        "supports_non_reasoning": False,
                        "abilities": ["text", "formatting"],
                    },
                    {
                        "provider": "ollama",
                        "model": "puyangwang/medgemma-27b-it:q6",
                        "roles": ["specialist"],
                        "tags": ["medical", "clinical"],
                        "domains": ["medical"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    entries = load_model_manifest(str(manifest_path))

    assert len(entries) == 2
    assert entries[0].provider == "ollama"
    assert entries[0].model == "qwen3:4b"
    assert entries[0].roles == ("router",)
    assert entries[0].tags == ("fast", "small")
    assert entries[0].domains == ("general",)
    assert entries[0].platform == "local"
    assert entries[0].cost_tier == "cheap_local"
    assert entries[0].notes == "routing"
    assert entries[0].priority == 11
    assert entries[0].strength == 2
    assert entries[0].supports_reasoning is True
    assert entries[0].supports_non_reasoning is False
    assert entries[0].abilities == ("text", "formatting")


def test_manifest_helpers_index_and_models_lookup(tmp_path) -> None:
    manifest_path = tmp_path / "model_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "version": 1,
                "models": [
                    {"provider": "ollama", "model": "mistral-small3.2:24b"},
                    {"provider": "openai", "model": "gpt-4.1-mini"},
                    {"provider": "ollama", "model": "qwen3:4b"},
                ],
            }
        ),
        encoding="utf-8",
    )

    entries = load_model_manifest(str(manifest_path))
    index = build_manifest_index(entries)
    ollama_models = models_for_provider(entries, "ollama")

    assert manifest_entry_key("ollama", "qwen3:4b") in index
    assert ollama_models == ("mistral-small3.2:24b", "qwen3:4b")
