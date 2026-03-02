import asyncio
from types import SimpleNamespace

from telegram.constants import ChatAction

from ai_assistant.modules.telegram.handlers import (
    MPC_AUDIO_PREVIOUS,
    MPC_AUDIO_NEXT,
    MPC_AUDIO_RU,
    MPC_SUBTITLE_NEXT,
    MPC_SUBTITLE_RU,
    PLAYER_NEXT,
    PLAYER_OUTPUT_TOGGLE,
    PLAYER_PLAY_PAUSE,
    PLAYER_PREVIOUS,
    SETTINGS_HOME,
    TelegramHandlers,
)
from ai_assistant.core.models import SettingChoiceOption, SettingDefinition, TerminalCommandResult


class FakeAssistantService:
    def __init__(self) -> None:
        self.process_calls: list[tuple[int, str]] = []
        self.cleared_users: list[int] = []

    async def process_text(self, user_id: int, text: str):
        self.process_calls.append((user_id, text))
        return SimpleNamespace(user_id=user_id, text=f"processed: {text}")

    async def clear_context(self, user_id: int) -> None:
        self.cleared_users.append(user_id)


class FakeMessage:
    def __init__(self, text: str = "") -> None:
        self.text = text
        self.reply_to_message = None
        self.replies: list[str] = []
        self.reply_markup = None
        self.reply_kwargs: list[dict[str, object]] = []

    async def reply_text(self, text: str, reply_markup=None, **kwargs) -> None:
        self.replies.append(text)
        self.reply_markup = reply_markup
        self.reply_kwargs.append(kwargs)


class FakeUser:
    def __init__(
        self,
        user_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> None:
        self.id = user_id
        self.username = username
        self.first_name = first_name
        self.last_name = last_name


class FakeChat:
    def __init__(self, chat_id: int) -> None:
        self.id = chat_id


class FakeUpdate:
    def __init__(self, user_id: int = 1, text: str = "") -> None:
        message = FakeMessage(text=text)
        self.effective_user = FakeUser(user_id)
        self.effective_chat = FakeChat(chat_id=user_id)
        self.effective_message = message
        self.message = message
        self.callback_query = None


class FakeCallbackQuery:
    def __init__(self, data: str, message: FakeMessage) -> None:
        self.data = data
        self.message = message
        self.answers: list[tuple[str | None, bool]] = []
        self.edits: list[tuple[str, object | None]] = []

    async def answer(self, text: str | None = None, show_alert: bool = False) -> None:
        self.answers.append((text, show_alert))

    async def edit_message_text(self, text: str, reply_markup=None, **kwargs) -> None:
        del kwargs
        self.edits.append((text, reply_markup))
        self.message.replies.append(text)
        self.message.reply_markup = reply_markup


class FakeMediaController:
    def __init__(self) -> None:
        self.actions: list[str] = []

    def play_pause(self) -> None:
        self.actions.append("play_pause")

    def previous_track(self) -> None:
        self.actions.append("previous")

    def next_track(self) -> None:
        self.actions.append("next")


class FakeMpcController:
    def __init__(self) -> None:
        self.actions: list[str] = []

    def audio_next(self) -> bool:
        self.actions.append("audio_next")
        return True

    def audio_previous(self) -> bool:
        self.actions.append("audio_previous")
        return True

    def subtitle_next(self) -> bool:
        self.actions.append("subtitle_next")
        return True

    def subtitle_previous(self) -> bool:
        self.actions.append("subtitle_previous")
        return True

    def audio_set_language(self, language: str) -> bool:
        self.actions.append(f"audio_{language}")
        return True

    def subtitle_set_language(self, language: str) -> bool:
        self.actions.append(f"subtitle_{language}")
        return True


class FakeOutputController:
    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled
        self.actions: list[str] = []

    def enable_output(self) -> bool:
        self.enabled = True
        self.actions.append("enable")
        return self.enabled

    def disable_output(self) -> bool:
        self.enabled = False
        self.actions.append("disable")
        return self.enabled

    def toggle_output(self) -> bool:
        self.enabled = not self.enabled
        self.actions.append("toggle")
        return self.enabled

    def is_output_enabled(self) -> bool:
        self.actions.append("status")
        return self.enabled


class FakeBot:
    def __init__(self) -> None:
        self.actions: list[tuple[int, str]] = []

    async def send_chat_action(self, chat_id: int, action: str) -> None:
        self.actions.append((chat_id, action))


class FakeTerminalExecutor:
    def __init__(self, shell_name: str = "powershell") -> None:
        self.shell_name = shell_name
        self.commands: list[tuple[int, str]] = []
        self.active_sessions: set[int] = set()

    def describe_shell(self) -> str:
        return self.shell_name

    async def start_session(self, session_id: int) -> None:
        self.active_sessions.add(session_id)

    async def close_session(self, session_id: int) -> None:
        self.active_sessions.discard(session_id)

    def is_session_active(self, session_id: int) -> bool:
        return session_id in self.active_sessions

    async def run_command(self, session_id: int, command: str) -> TerminalCommandResult:
        self.commands.append((session_id, command))
        return TerminalCommandResult(
            shell=self.shell_name,
            command=command,
            exit_code=0,
            stdout=f"ran: {command}",
            stderr="",
        )


class FakeInteractiveTerminalExecutor(FakeTerminalExecutor):
    async def run_command(self, session_id: int, command: str) -> TerminalCommandResult:
        self.commands.append((session_id, command))
        return TerminalCommandResult(
            shell=self.shell_name,
            command=command,
            exit_code=None,
            stdout="password:",
            stderr="",
            running=True,
        )


class FakeUserSettingsStore:
    def __init__(self) -> None:
        self._data: dict[int, dict[str, str]] = {}
        self._definitions: list[SettingDefinition] = [
            SettingDefinition(
                key="language",
                value_type="choice",
                section="Assistant",
                title="Language",
                description="Preferred language.",
                is_shown_in_ui=True,
            ),
            SettingDefinition(
                key="tts",
                value_type="bool",
                section="Assistant",
                title="Voice replies",
                description="Toggle TTS replies.",
                is_shown_in_ui=True,
            ),
            SettingDefinition(
                key="signature",
                value_type="text",
                section="Assistant",
                title="Signature",
                description="Optional signature.",
                is_shown_in_ui=True,
            ),
            SettingDefinition(
                key="hidden_internal",
                value_type="text",
                section="Internal",
                title="Hidden",
                description="Should not be shown in UI.",
                is_shown_in_ui=False,
            ),
        ]
        self._choice_options: dict[str, list[SettingChoiceOption]] = {
            "language": [
                SettingChoiceOption(
                    setting_id="language",
                    name="ru",
                    description="Russian",
                ),
                SettingChoiceOption(
                    setting_id="language",
                    name="en",
                    description="English",
                ),
            ]
        }

    async def set_setting(self, user_id: int, key: str, value: str) -> None:
        if user_id not in self._data:
            self._data[user_id] = {}
        self._data[user_id][key] = value

    async def get_setting(self, user_id: int, key: str) -> str | None:
        return self._data.get(user_id, {}).get(key)

    async def get_all_settings(self, user_id: int) -> dict[str, str]:
        return dict(self._data.get(user_id, {}))

    async def get_setting_definitions(self, locale: str | None = None) -> list[SettingDefinition]:
        del locale
        return list(self._definitions)

    async def get_setting_choice_options(
        self,
        setting_id: str,
        locale: str | None = None,
    ) -> list[SettingChoiceOption]:
        del locale
        return list(self._choice_options.get(setting_id, []))


class FakePermissionChecker:
    def __init__(self, allowed: set[tuple[int, str, str]] | None = None) -> None:
        self.allowed = allowed or set()
        self.calls: list[tuple[int, str, str]] = []
        self.user_permission_updates: list[tuple[int, str, str, bool]] = []
        self.roles_created: list[str] = []
        self.role_assignments: list[tuple[int, str]] = []
        self.role_grants: list[tuple[str, str, str]] = []
        self.role_revokes: list[tuple[str, str, str]] = []
        self.user_roles_response: dict[int, list[str]] = {}
        self.user_permissions_response: dict[int, dict[str, list[dict[str, object]]]] = {}

    async def has_permission(self, user_id: int, permission_type: str, name: str) -> bool:
        key = (user_id, permission_type, name)
        self.calls.append(key)
        return key in self.allowed

    async def set_user_permission(
        self,
        user_id: int,
        permission_type: str,
        name: str,
        is_active: bool,
    ) -> None:
        self.user_permission_updates.append((user_id, permission_type, name, is_active))

    async def create_role(self, role_name: str) -> None:
        self.roles_created.append(role_name)

    async def assign_role(self, user_id: int, role_name: str) -> None:
        self.role_assignments.append((user_id, role_name))

    async def grant_role_permission(self, role_name: str, permission_type: str, name: str) -> None:
        self.role_grants.append((role_name, permission_type, name))

    async def revoke_role_permission(self, role_name: str, permission_type: str, name: str) -> None:
        self.role_revokes.append((role_name, permission_type, name))

    async def get_user_roles(self, user_id: int) -> list[str]:
        return list(self.user_roles_response.get(user_id, []))

    async def get_user_permission_report(
        self,
        user_id: int,
    ) -> dict[str, list[dict[str, object]]]:
        return dict(
            self.user_permissions_response.get(
                user_id,
                {"user_overrides": [], "role_permissions": [], "effective": []},
            )
        )


def test_handle_ping_replies_pong() -> None:
    assistant = FakeAssistantService()
    handlers = TelegramHandlers(assistant_service=assistant)
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_ping(update, context))

    assert update.effective_message.replies == ["pong"]


def test_handle_start_shows_only_permitted_commands_and_roles() -> None:
    assistant = FakeAssistantService()
    permissions = FakePermissionChecker(
        allowed={
            (101, "general", "usage"),
            (101, "general", "assistant"),
            (101, "command", "start"),
            (101, "command", "id"),
            (101, "command", "ping"),
            (101, "command", "ask"),
            (101, "command", "clear"),
        }
    )
    permissions.user_roles_response[101] = ["operator"]
    handlers = TelegramHandlers(
        assistant_service=assistant,
        permission_checker=permissions,
        permission_admin=permissions,
    )
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_start(update, context))

    text = update.effective_message.replies[0]
    assert "Home AI Assistant" in text
    assert "Роли: operator" in text
    assert "/start -" in text
    assert "/id -" in text
    assert "/ping -" in text
    assert "/ask -" in text
    assert "/clear -" in text
    assert "Общение с ИИ:" in text
    assert "/terminal -" not in text
    assert "/grant -" not in text


def test_handle_start_hides_ai_block_without_assistant_permission() -> None:
    assistant = FakeAssistantService()
    permissions = FakePermissionChecker(
        allowed={
            (101, "general", "usage"),
            (101, "command", "start"),
            (101, "command", "ping"),
            (101, "command", "ask"),
        }
    )
    handlers = TelegramHandlers(assistant_service=assistant, permission_checker=permissions)
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_start(update, context))

    text = update.effective_message.replies[0]
    assert "Общение с ИИ:" not in text
    assert "/ask -" not in text
    assert "/ping -" in text


def test_handle_start_uses_user_language_setting_for_localized_text() -> None:
    assistant = FakeAssistantService()
    permissions = FakePermissionChecker(
        allowed={
            (101, "general", "usage"),
            (101, "general", "assistant"),
            (101, "command", "start"),
            (101, "command", "ping"),
            (101, "command", "ask"),
            (101, "command", "clear"),
        }
    )
    settings_store = FakeUserSettingsStore()
    asyncio.run(settings_store.set_setting(user_id=101, key="language", value="en"))
    handlers = TelegramHandlers(
        assistant_service=assistant,
        user_settings_store=settings_store,
        permission_checker=permissions,
    )
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_start(update, context))

    text = update.effective_message.replies[0]
    assert "Home AI Assistant" in text
    assert "Available commands:" in text
    assert "/ping - Quick bot availability check." in text
    assert "Assistant chat:" in text


def test_handle_id_replies_current_user_id() -> None:
    assistant = FakeAssistantService()
    handlers = TelegramHandlers(assistant_service=assistant)
    update = FakeUpdate(user_id=777)
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_id(update, context))

    text = update.effective_message.replies[0]
    assert "Your account:" in text
    assert "ID: 777" in text


def test_handle_id_replies_target_user_id_from_reply() -> None:
    assistant = FakeAssistantService()
    handlers = TelegramHandlers(assistant_service=assistant)
    update = FakeUpdate(user_id=777)
    update.effective_message.reply_to_message = SimpleNamespace(
        from_user=SimpleNamespace(id=888, username="target_user")
    )
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_id(update, context))

    text = update.effective_message.replies[0]
    assert "Reply sender:" in text
    assert "ID: 888" in text
    assert "Username: @target_user" in text


def test_handle_id_replies_forwarded_sender_and_original_author() -> None:
    assistant = FakeAssistantService()
    handlers = TelegramHandlers(assistant_service=assistant)
    update = FakeUpdate(user_id=777)
    update.effective_message.reply_to_message = SimpleNamespace(
        from_user=SimpleNamespace(id=888, username="forwarder"),
        forward_origin=SimpleNamespace(user=SimpleNamespace(id=999, username="origin_user")),
    )
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_id(update, context))

    text = update.effective_message.replies[0]
    assert "Forwarded by:" in text
    assert "ID: 888" in text
    assert "Original author:" in text
    assert "ID: 999" in text
    assert "Username: @origin_user" in text


def test_handle_id_replies_contact_sender_and_contact_data() -> None:
    assistant = FakeAssistantService()
    handlers = TelegramHandlers(assistant_service=assistant)
    update = FakeUpdate(user_id=777)
    update.effective_message.reply_to_message = SimpleNamespace(
        from_user=SimpleNamespace(id=888, username="sender_user"),
        contact=SimpleNamespace(
            user_id=444,
            first_name="Ivan",
            last_name="Petrov",
            phone_number="+79990001122",
        ),
    )
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_id(update, context))

    text = update.effective_message.replies[0]
    assert "Contact sent by:" in text
    assert "ID: 888" in text
    assert "Contact in message:" in text
    assert "ID: 444" in text
    assert "Name: Ivan Petrov" in text
    assert "Phone: +79990001122" in text


def test_handle_echo_replies_args() -> None:
    assistant = FakeAssistantService()
    handlers = TelegramHandlers(assistant_service=assistant)
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=["hello", "world"])

    asyncio.run(handlers.handle_echo(update, context))

    assert update.effective_message.replies == ["hello world"]


def test_handle_text_message_calls_llm() -> None:
    assistant = FakeAssistantService()
    handlers = TelegramHandlers(assistant_service=assistant)
    update = FakeUpdate(user_id=101, text="какая погода?")
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_text_message(update, context))

    assert assistant.process_calls == [(101, "какая погода?")]
    assert update.effective_message.replies == ["processed: какая погода?"]
    assert update.effective_message.reply_kwargs[0].get("parse_mode") == "HTML"


def test_terminal_mode_routes_text_to_terminal() -> None:
    assistant = FakeAssistantService()
    terminal = FakeTerminalExecutor(shell_name="powershell")
    handlers = TelegramHandlers(assistant_service=assistant, terminal_executor=terminal)
    update_mode = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_terminal_mode(update_mode, context))

    update_command = FakeUpdate(user_id=101, text="Get-Date")
    asyncio.run(handlers.handle_text_message(update_command, context))

    assert terminal.commands == [(101, "Get-Date")]
    assert assistant.process_calls == []
    assert "Terminal mode ON" in update_mode.effective_message.replies[0]
    assert "[powershell] $ Get-Date" in update_command.effective_message.replies[0]


def test_terminal_mode_exit_returns_to_llm() -> None:
    assistant = FakeAssistantService()
    terminal = FakeTerminalExecutor(shell_name="powershell")
    handlers = TelegramHandlers(assistant_service=assistant, terminal_executor=terminal)
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_terminal_mode(FakeUpdate(user_id=101), context))
    asyncio.run(handlers.handle_exit_terminal_mode(FakeUpdate(user_id=101), context))

    update_llm = FakeUpdate(user_id=101, text="привет")
    asyncio.run(handlers.handle_text_message(update_llm, context))

    assert assistant.process_calls == [(101, "привет")]
    assert terminal.commands == []


def test_terminal_mode_formats_running_interactive_result() -> None:
    assistant = FakeAssistantService()
    terminal = FakeInteractiveTerminalExecutor(shell_name="powershell")
    handlers = TelegramHandlers(assistant_service=assistant, terminal_executor=terminal)
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_terminal_mode(FakeUpdate(user_id=101), context))
    update_command = FakeUpdate(user_id=101, text="ssh deu")
    asyncio.run(handlers.handle_text_message(update_command, context))

    reply = update_command.effective_message.replies[0]
    assert "Interactive process is running" in reply
    assert "password:" in reply


def test_handle_text_message_sends_typing_action() -> None:
    assistant = FakeAssistantService()
    handlers = TelegramHandlers(assistant_service=assistant)
    update = FakeUpdate(user_id=111, text="hello")
    fake_bot = FakeBot()
    context = SimpleNamespace(args=[], bot=fake_bot)

    asyncio.run(handlers.handle_text_message(update, context))

    assert fake_bot.actions
    assert fake_bot.actions[0] == (111, ChatAction.TYPING)


def test_handle_clear_clears_user_context() -> None:
    assistant = FakeAssistantService()
    handlers = TelegramHandlers(assistant_service=assistant)
    update = FakeUpdate(user_id=303)
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_clear(update, context))

    assert assistant.cleared_users == [303]
    assert update.effective_message.replies == ["Контекст очищен."]


def test_handle_set_setting_saves_value() -> None:
    assistant = FakeAssistantService()
    settings_store = FakeUserSettingsStore()
    handlers = TelegramHandlers(assistant_service=assistant, user_settings_store=settings_store)
    update = FakeUpdate(user_id=404)
    context = SimpleNamespace(args=["voice", "on"])

    asyncio.run(handlers.handle_set_setting(update, context))

    saved = asyncio.run(settings_store.get_setting(user_id=404, key="voice"))
    assert saved == "on"
    assert update.effective_message.replies == ["Сохранено: voice = on"]


def test_handle_settings_raw_returns_saved_values() -> None:
    assistant = FakeAssistantService()
    settings_store = FakeUserSettingsStore()
    handlers = TelegramHandlers(assistant_service=assistant, user_settings_store=settings_store)
    update = FakeUpdate(user_id=505)
    context = SimpleNamespace(args=[])

    asyncio.run(settings_store.set_setting(user_id=505, key="language", value="ru"))
    asyncio.run(settings_store.set_setting(user_id=505, key="tts", value="off"))
    asyncio.run(handlers.handle_settings_raw(update, context))

    assert "Текущие настройки:" in update.effective_message.replies[0]
    assert "- language: ru" in update.effective_message.replies[0]
    assert "- tts: off" in update.effective_message.replies[0]


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


def test_handle_player_shows_keyboard() -> None:
    assistant = FakeAssistantService()
    handlers = TelegramHandlers(assistant_service=assistant)
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_player(update, context))

    assert update.effective_message.replies == ["Управление плеером:"]
    keyboard = update.effective_message.reply_markup
    assert keyboard is not None
    callbacks = [button.callback_data for button in keyboard.inline_keyboard[0]]
    assert callbacks == [PLAYER_PREVIOUS, PLAYER_PLAY_PAUSE, PLAYER_NEXT]


def test_handle_player_shows_output_button_if_configured() -> None:
    assistant = FakeAssistantService()
    output = FakeOutputController()
    handlers = TelegramHandlers(assistant_service=assistant, output_controller=output)
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_player(update, context))

    keyboard = update.effective_message.reply_markup
    callbacks = [button.callback_data for button in keyboard.inline_keyboard[0]]
    assert callbacks == [PLAYER_PREVIOUS, PLAYER_PLAY_PAUSE, PLAYER_NEXT, PLAYER_OUTPUT_TOGGLE]


def test_handle_player_button_calls_media_controller() -> None:
    media_controller = FakeMediaController()
    assistant = FakeAssistantService()
    handlers = TelegramHandlers(
        assistant_service=assistant,
        media_controller=media_controller,
    )
    update = FakeUpdate(user_id=101)
    update.callback_query = FakeCallbackQuery(data=PLAYER_NEXT, message=update.effective_message)
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_player_button(update, context))

    assert media_controller.actions == ["next"]
    assert update.callback_query.answers == [("Next track", False)]


def test_handle_player_output_button_toggles_output() -> None:
    media_controller = FakeMediaController()
    output_controller = FakeOutputController(enabled=False)
    assistant = FakeAssistantService()
    handlers = TelegramHandlers(
        assistant_service=assistant,
        media_controller=media_controller,
        output_controller=output_controller,
    )
    update = FakeUpdate(user_id=101)
    update.callback_query = FakeCallbackQuery(
        data=PLAYER_OUTPUT_TOGGLE, message=update.effective_message
    )
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_player_button(update, context))

    assert output_controller.actions == ["toggle"]
    assert output_controller.enabled is True
    assert update.callback_query.answers == [("Speakers output: ON", False)]


def test_handle_mpc_shows_keyboard() -> None:
    assistant = FakeAssistantService()
    handlers = TelegramHandlers(assistant_service=assistant)
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_mpc(update, context))

    assert update.effective_message.replies == ["MPC-HC: управление дорожками"]
    keyboard = update.effective_message.reply_markup
    assert keyboard is not None
    first_row_callbacks = [button.callback_data for button in keyboard.inline_keyboard[0]]
    assert first_row_callbacks == [MPC_AUDIO_PREVIOUS, MPC_AUDIO_NEXT]


def test_handle_mpc_button_calls_mpc_controller() -> None:
    mpc_controller = FakeMpcController()
    assistant = FakeAssistantService()
    handlers = TelegramHandlers(
        assistant_service=assistant,
        mpc_controller=mpc_controller,
    )
    update = FakeUpdate(user_id=101)
    update.callback_query = FakeCallbackQuery(data=MPC_SUBTITLE_NEXT, message=update.effective_message)
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_mpc_button(update, context))

    assert mpc_controller.actions == ["subtitle_next"]
    assert update.callback_query.answers == [("Субтитры: следующая дорожка", False)]


def test_handle_mpc_button_selects_ru_audio() -> None:
    mpc_controller = FakeMpcController()
    assistant = FakeAssistantService()
    handlers = TelegramHandlers(
        assistant_service=assistant,
        mpc_controller=mpc_controller,
    )
    update = FakeUpdate(user_id=101)
    update.callback_query = FakeCallbackQuery(data=MPC_AUDIO_RU, message=update.effective_message)
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_mpc_button(update, context))

    assert mpc_controller.actions == ["audio_ru"]
    assert update.callback_query.answers == [("Аудио: переключено на RU", False)]


def test_handle_mpc_button_selects_ru_subtitles() -> None:
    mpc_controller = FakeMpcController()
    assistant = FakeAssistantService()
    handlers = TelegramHandlers(
        assistant_service=assistant,
        mpc_controller=mpc_controller,
    )
    update = FakeUpdate(user_id=101)
    update.callback_query = FakeCallbackQuery(data=MPC_SUBTITLE_RU, message=update.effective_message)
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_mpc_button(update, context))

    assert mpc_controller.actions == ["subtitle_ru"]
    assert update.callback_query.answers == [("Субтитры: переключено на RU", False)]


def test_handle_ping_requires_usage_permission() -> None:
    assistant = FakeAssistantService()
    permissions = FakePermissionChecker(allowed={(101, "command", "ping")})
    handlers = TelegramHandlers(assistant_service=assistant, permission_checker=permissions)
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_ping(update, context))

    assert update.effective_message.replies == ["Недостаточно прав: general/usage."]


def test_handle_ping_requires_command_permission() -> None:
    assistant = FakeAssistantService()
    permissions = FakePermissionChecker(allowed={(101, "general", "usage")})
    handlers = TelegramHandlers(assistant_service=assistant, permission_checker=permissions)
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_ping(update, context))

    assert update.effective_message.replies == ["Недостаточно прав: command/ping."]


def test_handle_settings_raw_requires_command_permission() -> None:
    assistant = FakeAssistantService()
    settings_store = FakeUserSettingsStore()
    permissions = FakePermissionChecker(allowed={(101, "general", "usage")})
    handlers = TelegramHandlers(
        assistant_service=assistant,
        user_settings_store=settings_store,
        permission_checker=permissions,
    )
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_settings_raw(update, context))

    assert update.effective_message.replies == ["Недостаточно прав: command/settings_raw."]


def test_handle_settings_callback_requires_command_permission() -> None:
    assistant = FakeAssistantService()
    settings_store = FakeUserSettingsStore()
    permissions = FakePermissionChecker(allowed={(101, "general", "usage")})
    handlers = TelegramHandlers(
        assistant_service=assistant,
        user_settings_store=settings_store,
        permission_checker=permissions,
    )
    update = FakeUpdate(user_id=101)
    update.callback_query = FakeCallbackQuery(data="settings:home", message=update.effective_message)
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_settings_callback(update, context))

    assert update.callback_query.answers == [("Недостаточно прав: command/settings.", True)]


def test_handle_cancel_requires_command_permission() -> None:
    assistant = FakeAssistantService()
    permissions = FakePermissionChecker(allowed={(101, "general", "usage")})
    handlers = TelegramHandlers(assistant_service=assistant, permission_checker=permissions)
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_cancel(update, context))

    assert update.effective_message.replies == ["Недостаточно прав: command/cancel."]


def test_handle_id_requires_command_permission() -> None:
    assistant = FakeAssistantService()
    permissions = FakePermissionChecker(allowed={(101, "general", "usage")})
    handlers = TelegramHandlers(assistant_service=assistant, permission_checker=permissions)
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_id(update, context))

    assert update.effective_message.replies == ["Недостаточно прав: command/id."]


def test_admin_telegram_id_bypasses_permissions_in_handlers() -> None:
    assistant = FakeAssistantService()
    permissions = FakePermissionChecker(allowed=set())
    handlers = TelegramHandlers(
        assistant_service=assistant,
        permission_checker=permissions,
        admin_telegram_id=101,
    )
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_ping(update, context))

    assert update.effective_message.replies == ["pong"]


def test_text_message_requires_assistant_permission() -> None:
    assistant = FakeAssistantService()
    permissions = FakePermissionChecker(allowed={(101, "general", "usage")})
    handlers = TelegramHandlers(assistant_service=assistant, permission_checker=permissions)
    update = FakeUpdate(user_id=101, text="hello")
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_text_message(update, context))

    assert update.effective_message.replies == ["Недостаточно прав: general/assistant."]
    assert assistant.process_calls == []


def test_handle_role_add_creates_role() -> None:
    assistant = FakeAssistantService()
    permissions = FakePermissionChecker(
        allowed={(101, "general", "usage"), (101, "command", "role_add")}
    )
    handlers = TelegramHandlers(
        assistant_service=assistant,
        permission_checker=permissions,
        permission_admin=permissions,
    )
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=["admin"])

    asyncio.run(handlers.handle_role_add(update, context))

    assert permissions.roles_created == ["admin"]
    assert update.effective_message.replies == ["Role created: admin"]


def test_handle_grant_user_sets_permission() -> None:
    assistant = FakeAssistantService()
    permissions = FakePermissionChecker(
        allowed={(101, "general", "usage"), (101, "command", "grant")}
    )
    handlers = TelegramHandlers(
        assistant_service=assistant,
        permission_checker=permissions,
        permission_admin=permissions,
    )
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=["user", "200", "command", "ping"])

    asyncio.run(handlers.handle_grant(update, context))

    assert permissions.user_permission_updates == [(200, "command", "ping", True)]
    assert "Granted user permission" in update.effective_message.replies[0]


def test_handle_revoke_role_removes_permission() -> None:
    assistant = FakeAssistantService()
    permissions = FakePermissionChecker(
        allowed={(101, "general", "usage"), (101, "command", "revoke")}
    )
    handlers = TelegramHandlers(
        assistant_service=assistant,
        permission_checker=permissions,
        permission_admin=permissions,
    )
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=["role", "admins", "assistant", "media.play_pause"])

    asyncio.run(handlers.handle_revoke(update, context))

    assert permissions.role_revokes == [("admins", "assistant", "media.play_pause")]
    assert "Revoked role permission" in update.effective_message.replies[0]


def test_handle_user_roles_returns_roles() -> None:
    assistant = FakeAssistantService()
    permissions = FakePermissionChecker(
        allowed={(101, "general", "usage"), (101, "command", "user_roles")}
    )
    permissions.user_roles_response[200] = ["admin", "operator"]
    handlers = TelegramHandlers(
        assistant_service=assistant,
        permission_checker=permissions,
        permission_admin=permissions,
    )
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=["200"])

    asyncio.run(handlers.handle_user_roles(update, context))

    text = update.effective_message.replies[0]
    assert "user=200 roles:" in text
    assert "- admin" in text
    assert "- operator" in text


def test_handle_user_permissions_returns_report() -> None:
    assistant = FakeAssistantService()
    permissions = FakePermissionChecker(
        allowed={(101, "general", "usage"), (101, "command", "user_permissions")}
    )
    permissions.user_permissions_response[200] = {
        "user_overrides": [{"type": "command", "name": "ping", "is_active": False}],
        "role_permissions": [{"role": "admin", "type": "general", "name": "usage"}],
        "effective": [
            {
                "type": "general",
                "name": "usage",
                "is_active": True,
                "source": "role",
                "roles": ["admin"],
            },
            {
                "type": "command",
                "name": "ping",
                "is_active": False,
                "source": "user_override",
                "roles": [],
            },
        ],
    }
    handlers = TelegramHandlers(
        assistant_service=assistant,
        permission_checker=permissions,
        permission_admin=permissions,
    )
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=["200"])

    asyncio.run(handlers.handle_user_permissions(update, context))

    text = update.effective_message.replies[0]
    assert "user=200 permissions:" in text
    assert "user_overrides:" in text
    assert "command/ping = False" in text
    assert "role_permissions:" in text
    assert "role=admin: general/usage" in text
    assert "effective:" in text
