from tests.modules.telegram._shared import *

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


def test_handle_start_shows_player_and_mpc_when_remote_runtime_available() -> None:
    assistant = FakeAssistantService()
    permissions = FakePermissionChecker(
        allowed={
            (101, "general", "usage"),
            (101, "command", "start"),
            (101, "command", "player"),
            (101, "command", "mpc"),
        }
    )
    handlers = TelegramHandlers(
        assistant_service=assistant,
        permission_checker=permissions,
        remote_ws_hub=object(),
    )
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_start(update, context))

    text = update.effective_message.replies[0]
    assert "/player -" in text
    assert "/mpc -" in text


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


def test_handle_text_message_splits_long_llm_reply_into_chunks() -> None:
    long_reply = "x" * 9000

    class LongReplyAssistant(FakeAssistantService):
        async def process_text(self, user_id: int, text: str):
            self.process_calls.append((user_id, text))
            return SimpleNamespace(user_id=user_id, text=long_reply)

    assistant = LongReplyAssistant()
    handlers = TelegramHandlers(assistant_service=assistant)
    update = FakeUpdate(user_id=101, text="long please")
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_text_message(update, context))

    assert assistant.process_calls == [(101, "long please")]
    assert len(update.effective_message.replies) == 3
    assert "".join(update.effective_message.replies) == long_reply
    assert all(
        kwargs.get("parse_mode") == "HTML" for kwargs in update.effective_message.reply_kwargs
    )
    assert all(
        kwargs.get("disable_web_page_preview") is True
        for kwargs in update.effective_message.reply_kwargs
    )


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


