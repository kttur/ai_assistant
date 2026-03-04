import asyncio

from ai_assistant.providers.system.assistant_command_executor import SystemAssistantCommandExecutor


class FakeMediaController:
    def play_pause(self) -> None:
        pass

    def previous_track(self) -> None:
        pass

    def next_track(self) -> None:
        pass


class FakeMpcController:
    def audio_next(self) -> bool:
        return True

    def audio_previous(self) -> bool:
        return True

    def subtitle_next(self) -> bool:
        return True

    def subtitle_previous(self) -> bool:
        return True

    def audio_set_language(self, language: str) -> bool:
        return language in {"ru", "en"}

    def subtitle_set_language(self, language: str) -> bool:
        return language in {"ru", "en"}


def test_system_executor_respects_active_skill_filter() -> None:
    executor = SystemAssistantCommandExecutor(
        media_controller=FakeMediaController(),
        mpc_controller=FakeMpcController(),
        active_skill_ids=("media",),
    )

    commands = {item["command"] for item in asyncio.run(executor.get_command_catalog())}
    assert "media.play_pause" in commands
    assert "mpc.audio_next" not in commands
