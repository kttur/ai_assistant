from tests.modules.telegram._shared import *

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


