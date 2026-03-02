from ai_assistant.providers.system.assistant_command_executor import SystemAssistantCommandExecutor


class FakeMediaController:
    def __init__(self) -> None:
        self.actions: list[str] = []

    def play_pause(self) -> None:
        self.actions.append("play_pause")

    def previous_track(self) -> None:
        self.actions.append("previous_track")

    def next_track(self) -> None:
        self.actions.append("next_track")


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
    def __init__(self) -> None:
        self.enabled = False
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


def test_command_executor_catalog_and_execution() -> None:
    media = FakeMediaController()
    mpc = FakeMpcController()
    output = FakeOutputController()
    executor = SystemAssistantCommandExecutor(
        media_controller=media,
        mpc_controller=mpc,
        output_controller=output,
    )

    catalog = executor.get_command_catalog()
    commands = {item["command"] for item in catalog}
    assert "media.play_pause" in commands
    assert "mpc.audio_set_language" in commands
    assert "output.toggle" in commands

    media_result = executor.execute_command("media.next_track", {})
    mpc_result = executor.execute_command("mpc.audio_set_language", {"language": "ru"})
    output_result = executor.execute_command("output.toggle", {})

    assert media_result["ok"] is True
    assert mpc_result["ok"] is True
    assert output_result["ok"] is True
    assert media.actions == ["next_track"]
    assert mpc.actions == ["audio_ru"]
    assert output.actions == ["toggle"]
