import asyncio

from ai_assistant.providers.settings.in_memory_user_settings_store import InMemoryUserSettingsStore
from ai_assistant.core.models import SettingChoiceOption, SettingDefinition


def test_in_memory_user_settings_store_roundtrip() -> None:
    store = InMemoryUserSettingsStore()

    asyncio.run(store.set_setting(user_id=1, key="language", value="en"))
    asyncio.run(store.set_setting(user_id=1, key="voice", value="on"))
    asyncio.run(store.set_setting(user_id=2, key="language", value="ru"))

    assert asyncio.run(store.get_setting(user_id=1, key="language")) == "en"
    assert asyncio.run(store.get_setting(user_id=1, key="missing")) is None
    assert asyncio.run(store.get_all_settings(user_id=1)) == {
        "language": "en",
        "voice": "on",
    }
    assert asyncio.run(store.get_all_settings(user_id=2)) == {"language": "ru"}


def test_in_memory_user_settings_store_has_default_definitions_and_options() -> None:
    store = InMemoryUserSettingsStore()

    definitions = asyncio.run(store.get_setting_definitions())
    keys = {item.key for item in definitions}
    assert {"language", "tts", "signature"}.issubset(keys)

    language_options = asyncio.run(store.get_setting_choice_options("language"))
    option_names = {item.name for item in language_options}
    assert {"ru", "en"} == option_names


def test_in_memory_user_settings_store_supports_localized_metadata() -> None:
    store = InMemoryUserSettingsStore()

    definitions_ru = asyncio.run(store.get_setting_definitions(locale="ru"))
    language_setting = next(item for item in definitions_ru if item.key == "language")
    assert language_setting.section == "Ассистент"
    assert language_setting.title == "Язык"

    language_options_ru = asyncio.run(store.get_setting_choice_options("language", locale="ru"))
    labels = {item.name: item.display_name for item in language_options_ru}
    assert labels["ru"] == "Русский"
    assert labels["en"] == "Английский"


def test_in_memory_user_settings_store_supports_extra_definitions_and_options() -> None:
    store = InMemoryUserSettingsStore(
        extra_definitions=(
            SettingDefinition(
                key="llm_provider",
                value_type="choice",
                section="Assistant",
                title="LLM provider",
                description="Preferred backend.",
            ),
        ),
        extra_choice_options=(
            SettingChoiceOption(
                setting_id="llm_provider",
                name="ollama",
                display_name="Ollama",
                description="Ollama",
            ),
        ),
    )

    definitions = asyncio.run(store.get_setting_definitions())
    assert any(item.key == "llm_provider" for item in definitions)

    options = asyncio.run(store.get_setting_choice_options("llm_provider"))
    assert len(options) == 1
    assert options[0].name == "ollama"
    assert options[0].display_name == "Ollama"


def test_in_memory_user_settings_store_deduplicates_choice_options_case_insensitive() -> None:
    store = InMemoryUserSettingsStore(
        extra_choice_options=(
            SettingChoiceOption(
                setting_id="language",
                name="RU",
                display_name="Russian duplicate",
                description="Duplicate",
                permission_type="assistant",
                permission_name="assistant.language.ru",
            ),
        )
    )

    options = asyncio.run(store.get_setting_choice_options("language"))
    ru_options = [item for item in options if item.name.lower() == "ru"]
    assert len(ru_options) == 1
    assert ru_options[0].permission_type == "assistant"
    assert ru_options[0].permission_name == "assistant.language.ru"
