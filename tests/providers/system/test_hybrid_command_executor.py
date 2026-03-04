import asyncio

from ai_assistant.providers.system.hybrid_command_executor import HybridAssistantCommandExecutor


class FakeLocalExecutor:
    async def get_command_catalog(self, user_id: int | None = None) -> list[dict[str, object]]:
        del user_id
        return [{"command": "media.play_pause", "description": "local", "args": {}}]

    async def execute_command(
        self,
        command: str,
        args: dict[str, object],
        user_id: int | None = None,
    ) -> dict[str, object]:
        return {"ok": True, "source": "local", "command": command, "args": args, "user_id": user_id}


class FakeHub:
    async def get_user_command_catalog(self, user_id: int) -> list[dict[str, object]]:
        return [{"command": "remote.media.play_pause", "description": "remote", "args": {}}]

    async def execute_user_remote_command(
        self,
        *,
        user_id: int,
        command: str,
        args: dict[str, object],
    ) -> dict[str, object]:
        return {"ok": True, "source": "remote", "command": command, "args": args, "user_id": user_id}


def test_hybrid_catalog_includes_remote_for_user() -> None:
    executor = HybridAssistantCommandExecutor(local_executor=FakeLocalExecutor(), remote_ws_hub=FakeHub())

    catalog = asyncio.run(executor.get_command_catalog(user_id=5))
    commands = {item["command"] for item in catalog}
    assert "media.play_pause" in commands
    assert "remote.media.play_pause" in commands


def test_hybrid_executes_remote_prefix_on_hub() -> None:
    executor = HybridAssistantCommandExecutor(local_executor=FakeLocalExecutor(), remote_ws_hub=FakeHub())

    result = asyncio.run(
        executor.execute_command(
            command="remote.media.play_pause",
            args={"x": 1},
            user_id=7,
        )
    )

    assert result["source"] == "remote"
    assert result["command"] == "media.play_pause"
    assert result["user_id"] == 7


def test_hybrid_executes_local_command_via_local_executor() -> None:
    executor = HybridAssistantCommandExecutor(local_executor=FakeLocalExecutor(), remote_ws_hub=FakeHub())

    result = asyncio.run(
        executor.execute_command(
            command="media.play_pause",
            args={},
            user_id=3,
        )
    )

    assert result["source"] == "local"
    assert result["command"] == "media.play_pause"
    assert result["user_id"] == 3
