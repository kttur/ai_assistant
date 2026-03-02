import asyncio

from ai_assistant.modules.telegram.bot import TelegramBotModule


class FakeApplication:
    def __init__(self) -> None:
        self.called = False
        self.loop_seen = False

    def run_polling(self, drop_pending_updates: bool = True) -> None:
        self.called = drop_pending_updates
        self.loop_seen = asyncio.get_event_loop() is not None


def test_run_sets_current_event_loop() -> None:
    module = TelegramBotModule(token="test-token", handlers=None)  # type: ignore[arg-type]
    fake_application = FakeApplication()
    module._build_application = lambda: fake_application  # type: ignore[method-assign]

    asyncio.set_event_loop(None)
    module.run()

    assert fake_application.called is True
    assert fake_application.loop_seen is True

    current_loop = asyncio.get_event_loop()
    current_loop.close()
    asyncio.set_event_loop(None)

