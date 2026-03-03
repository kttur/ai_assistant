from tests.modules.telegram._shared import *

def test_handle_settings_shows_sections_keyboard() -> None:
    assistant = FakeAssistantService()
    settings_store = FakeUserSettingsStore()
    handlers = TelegramHandlers(assistant_service=assistant, user_settings_store=settings_store)
    update = FakeUpdate(user_id=505)
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_settings(update, context))

    assert "Разделы настроек:" in update.effective_message.replies[0]
    keyboard = update.effective_message.reply_markup
    assert keyboard is not None
    first_button = keyboard.inline_keyboard[0][0]
    assert str(first_button.callback_data).startswith("settings:section:")


def test_handle_settings_merges_and_localizes_section_names() -> None:
    assistant = FakeAssistantService()
    settings_store = FakeUserSettingsStore()
    settings_store._definitions.append(
        SettingDefinition(
            key="llm_provider",
            value_type="text",
            section="Ассистент",
            title="LLM Provider",
            description="Model backend selector.",
            is_shown_in_ui=True,
        )
    )
    settings_store._definitions.append(
        SettingDefinition(
            key="timezone",
            value_type="text",
            section="General",
            title="Timezone",
            description="User timezone.",
            is_shown_in_ui=True,
        )
    )
    handlers = TelegramHandlers(assistant_service=assistant, user_settings_store=settings_store)
    update = FakeUpdate(user_id=505)
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_settings(update, context))

    text = update.effective_message.replies[0]
    assert "- Ассистент: 4" in text
    assert "- Общие: 1" in text
    assert "- Assistant:" not in text
    assert "- General:" not in text


def _add_llm_settings_for_provider_model_tests(settings_store: FakeUserSettingsStore) -> None:
    settings_store._definitions.append(
        SettingDefinition(
            key="llm_provider",
            value_type="choice",
            section="Ассистент",
            title="LLM Provider",
            description="Select provider.",
            is_shown_in_ui=True,
        )
    )
    settings_store._definitions.append(
        SettingDefinition(
            key="llm_model",
            value_type="choice",
            section="Ассистент",
            title="LLM Model",
            description="Select model.",
            is_shown_in_ui=True,
        )
    )
    settings_store._choice_options["llm_provider"] = [
        SettingChoiceOption(setting_id="llm_provider", name="openai", description="OpenAI"),
        SettingChoiceOption(setting_id="llm_provider", name="ollama", description="Ollama"),
    ]
    settings_store._choice_options["llm_model"] = [
        SettingChoiceOption(setting_id="llm_model", name="openai:gpt-5-mini", description="OpenAI"),
        SettingChoiceOption(setting_id="llm_model", name="openai:gpt-5-nano", description="OpenAI"),
        SettingChoiceOption(setting_id="llm_model", name="ollama:qwen3:8b", description="Ollama"),
    ]


def _add_llm_settings_with_plain_model_names(settings_store: FakeUserSettingsStore) -> None:
    settings_store._definitions.append(
        SettingDefinition(
            key="llm_provider",
            value_type="choice",
            section="Ассистент",
            title="LLM Provider",
            description="Select provider.",
            is_shown_in_ui=True,
        )
    )
    settings_store._definitions.append(
        SettingDefinition(
            key="llm_model",
            value_type="choice",
            section="Ассистент",
            title="LLM Model",
            description="Select model.",
            is_shown_in_ui=True,
        )
    )
    settings_store._choice_options["llm_provider"] = [
        SettingChoiceOption(setting_id="llm_provider", name="openai", description="OpenAI"),
        SettingChoiceOption(setting_id="llm_provider", name="ollama", description="Ollama"),
    ]
    settings_store._choice_options["llm_model"] = [
        SettingChoiceOption(setting_id="llm_model", name="gpt-5-mini"),
        SettingChoiceOption(setting_id="llm_model", name="gpt-5-nano"),
    ]


def test_llm_model_options_are_filtered_by_selected_provider() -> None:
    assistant = FakeAssistantService()
    settings_store = FakeUserSettingsStore()
    _add_llm_settings_for_provider_model_tests(settings_store)
    asyncio.run(settings_store.set_setting(user_id=505, key="llm_provider", value="openai"))
    asyncio.run(settings_store.set_setting(user_id=505, key="llm_model", value="ollama:qwen3:8b"))
    handlers = TelegramHandlers(assistant_service=assistant, user_settings_store=settings_store)

    sections = asyncio.run(
        handlers._get_visible_settings_sections(
            user_id=505,
            ui_only=True,
            locale="ru",
        )
    )
    llm_model_setting = next(
        setting
        for _, settings_list in sections
        for setting in settings_list
        if setting.key == "llm_model"
    )
    option_names = [item.name for item in llm_model_setting.options]

    assert option_names == ["openai:gpt-5-mini", "openai:gpt-5-nano"]
    assert "ollama:qwen3:8b" not in option_names


def test_llm_model_options_with_plain_names_are_not_hidden() -> None:
    assistant = FakeAssistantService()
    settings_store = FakeUserSettingsStore()
    _add_llm_settings_with_plain_model_names(settings_store)
    asyncio.run(settings_store.set_setting(user_id=505, key="llm_provider", value="openai"))
    asyncio.run(settings_store.set_setting(user_id=505, key="llm_model", value="ollama:qwen3:8b"))
    handlers = TelegramHandlers(assistant_service=assistant, user_settings_store=settings_store)

    sections = asyncio.run(
        handlers._get_visible_settings_sections(
            user_id=505,
            ui_only=True,
            locale="ru",
        )
    )
    llm_model_setting = next(
        setting
        for _, settings_list in sections
        for setting in settings_list
        if setting.key == "llm_model"
    )
    option_names = [item.name for item in llm_model_setting.options]

    assert option_names == ["gpt-5-mini", "gpt-5-nano"]


def test_switching_llm_provider_updates_llm_model_to_same_provider() -> None:
    assistant = FakeAssistantService()
    settings_store = FakeUserSettingsStore()
    _add_llm_settings_for_provider_model_tests(settings_store)
    asyncio.run(settings_store.set_setting(user_id=505, key="llm_provider", value="ollama"))
    asyncio.run(settings_store.set_setting(user_id=505, key="llm_model", value="ollama:qwen3:8b"))
    handlers = TelegramHandlers(assistant_service=assistant, user_settings_store=settings_store)

    sections = asyncio.run(
        handlers._get_visible_settings_sections(
            user_id=505,
            ui_only=True,
            locale="ru",
        )
    )
    target_section_index = -1
    target_setting_index = -1
    target_option_index = -1
    for section_index, (_, settings_list) in enumerate(sections):
        for setting_index, setting in enumerate(settings_list):
            if setting.key != "llm_provider":
                continue
            target_section_index = section_index
            target_setting_index = setting_index
            for option_index, option in enumerate(setting.options):
                if option.name == "openai":
                    target_option_index = option_index
                    break
            break
        if target_section_index >= 0:
            break

    assert target_section_index >= 0
    assert target_setting_index >= 0
    assert target_option_index >= 0

    chosen = asyncio.run(
        handlers._set_choice_setting_value(
            user_id=505,
            section_index=target_section_index,
            setting_index=target_setting_index,
            option_index=target_option_index,
            locale="ru",
        )
    )

    assert chosen is not None
    assert chosen.name == "openai"
    assert asyncio.run(settings_store.get_setting(user_id=505, key="llm_provider")) == "openai"
    assert asyncio.run(settings_store.get_setting(user_id=505, key="llm_model")) == "openai:gpt-5-mini"


def test_switching_llm_provider_with_plain_model_names_picks_first_available() -> None:
    assistant = FakeAssistantService()
    settings_store = FakeUserSettingsStore()
    _add_llm_settings_with_plain_model_names(settings_store)
    asyncio.run(settings_store.set_setting(user_id=505, key="llm_provider", value="ollama"))
    asyncio.run(settings_store.set_setting(user_id=505, key="llm_model", value="ollama:qwen3:8b"))
    handlers = TelegramHandlers(assistant_service=assistant, user_settings_store=settings_store)

    sections = asyncio.run(
        handlers._get_visible_settings_sections(
            user_id=505,
            ui_only=True,
            locale="ru",
        )
    )
    target_section_index = -1
    target_setting_index = -1
    target_option_index = -1
    for section_index, (_, settings_list) in enumerate(sections):
        for setting_index, setting in enumerate(settings_list):
            if setting.key != "llm_provider":
                continue
            target_section_index = section_index
            target_setting_index = setting_index
            for option_index, option in enumerate(setting.options):
                if option.name == "openai":
                    target_option_index = option_index
                    break
            break
        if target_section_index >= 0:
            break

    assert target_section_index >= 0
    assert target_setting_index >= 0
    assert target_option_index >= 0

    chosen = asyncio.run(
        handlers._set_choice_setting_value(
            user_id=505,
            section_index=target_section_index,
            setting_index=target_setting_index,
            option_index=target_option_index,
            locale="ru",
        )
    )

    assert chosen is not None
    assert chosen.name == "openai"
    assert asyncio.run(settings_store.get_setting(user_id=505, key="llm_provider")) == "openai"
    assert asyncio.run(settings_store.get_setting(user_id=505, key="llm_model")) == "gpt-5-mini"


def test_handle_settings_callback_section_shows_setting_page() -> None:
    assistant = FakeAssistantService()
    settings_store = FakeUserSettingsStore()
    asyncio.run(settings_store.set_setting(user_id=505, key="language", value="en"))
    handlers = TelegramHandlers(assistant_service=assistant, user_settings_store=settings_store)
    update = FakeUpdate(user_id=505)
    update.callback_query = FakeCallbackQuery(
        data="settings:section:0",
        message=update.effective_message,
    )
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_settings_callback(update, context))

    assert update.callback_query.edits
    text, _ = update.callback_query.edits[0]
    assert "Language" in text
    assert "Current value: en" in text


def test_choice_setting_page_hides_redundant_back_button() -> None:
    assistant = FakeAssistantService()
    settings_store = FakeUserSettingsStore()
    handlers = TelegramHandlers(assistant_service=assistant, user_settings_store=settings_store)
    update = FakeUpdate(user_id=505)
    update.callback_query = FakeCallbackQuery(
        data="settings:section:0",
        message=update.effective_message,
    )
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_settings_callback(update, context))

    _, reply_markup = update.callback_query.edits[-1]
    assert reply_markup is not None
    callbacks = [
        button.callback_data
        for row in reply_markup.inline_keyboard
        for button in row
    ]
    assert "settings:section:0" not in callbacks
    assert SETTINGS_HOME in callbacks


def test_handle_settings_callback_toggle_bool_value() -> None:
    assistant = FakeAssistantService()
    settings_store = FakeUserSettingsStore()
    handlers = TelegramHandlers(assistant_service=assistant, user_settings_store=settings_store)
    update = FakeUpdate(user_id=505)
    update.callback_query = FakeCallbackQuery(
        data="settings:toggle:0:2",
        message=update.effective_message,
    )
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_settings_callback(update, context))

    assert asyncio.run(settings_store.get_setting(user_id=505, key="tts")) == "on"
    assert update.callback_query.answers[-1] == ("Сохранено: ON", False)


def test_handle_settings_callback_choice_sets_option() -> None:
    assistant = FakeAssistantService()
    settings_store = FakeUserSettingsStore()
    handlers = TelegramHandlers(assistant_service=assistant, user_settings_store=settings_store)
    update = FakeUpdate(user_id=505)
    update.callback_query = FakeCallbackQuery(
        data="settings:choice:0:0:1",
        message=update.effective_message,
    )
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_settings_callback(update, context))

    assert asyncio.run(settings_store.get_setting(user_id=505, key="language")) == "en"
    assert update.callback_query.answers[-1] == ("Сохранено: en", False)


def test_text_setting_input_flow_updates_value_without_set_command() -> None:
    assistant = FakeAssistantService()
    settings_store = FakeUserSettingsStore()
    handlers = TelegramHandlers(assistant_service=assistant, user_settings_store=settings_store)
    context = SimpleNamespace(args=[])

    update_callback = FakeUpdate(user_id=505)
    update_callback.callback_query = FakeCallbackQuery(
        data="settings:text:0:1",
        message=update_callback.effective_message,
    )
    asyncio.run(handlers.handle_settings_callback(update_callback, context))

    update_text = FakeUpdate(user_id=505, text="Best regards")
    asyncio.run(handlers.handle_text_message(update_text, context))

    assert asyncio.run(settings_store.get_setting(user_id=505, key="signature")) == "Best regards"
    assert "Сохранено: signature = Best regards" in update_text.effective_message.replies[0]
    assert assistant.process_calls == []


def test_text_setting_page_shows_reset_button_when_value_exists() -> None:
    assistant = FakeAssistantService()
    settings_store = FakeUserSettingsStore()
    asyncio.run(settings_store.set_setting(user_id=505, key="signature", value="Signed"))
    handlers = TelegramHandlers(assistant_service=assistant, user_settings_store=settings_store)
    update = FakeUpdate(user_id=505)
    update.callback_query = FakeCallbackQuery(
        data="settings:view:0:1",
        message=update.effective_message,
    )
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_settings_callback(update, context))

    _, reply_markup = update.callback_query.edits[-1]
    assert reply_markup is not None
    callbacks = [
        button.callback_data
        for row in reply_markup.inline_keyboard
        for button in row
    ]
    assert "settings:text_clear:0:1" in callbacks


def test_handle_settings_callback_text_clear_resets_value() -> None:
    assistant = FakeAssistantService()
    settings_store = FakeUserSettingsStore()
    asyncio.run(settings_store.set_setting(user_id=505, key="signature", value="Signed"))
    handlers = TelegramHandlers(assistant_service=assistant, user_settings_store=settings_store)
    update = FakeUpdate(user_id=505)
    update.callback_query = FakeCallbackQuery(
        data="settings:text_clear:0:1",
        message=update.effective_message,
    )
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_settings_callback(update, context))

    assert asyncio.run(settings_store.get_setting(user_id=505, key="signature")) == ""
    assert update.callback_query.answers[-1] == ("Сброшено.", False)


def test_handle_cancel_clears_pending_text_input() -> None:
    assistant = FakeAssistantService()
    settings_store = FakeUserSettingsStore()
    handlers = TelegramHandlers(assistant_service=assistant, user_settings_store=settings_store)
    context = SimpleNamespace(args=[])

    update_callback = FakeUpdate(user_id=505)
    update_callback.callback_query = FakeCallbackQuery(
        data="settings:text:0:1",
        message=update_callback.effective_message,
    )
    asyncio.run(handlers.handle_settings_callback(update_callback, context))

    update_cancel = FakeUpdate(user_id=505)
    asyncio.run(handlers.handle_cancel(update_cancel, context))
    assert "отменен" in update_cancel.effective_message.replies[0]

    update_text = FakeUpdate(user_id=505, text="Should go to assistant")
    asyncio.run(handlers.handle_text_message(update_text, context))

    assert asyncio.run(settings_store.get_setting(user_id=505, key="signature")) is None
    assert assistant.process_calls == [(505, "Should go to assistant")]


