from __future__ import annotations

from ai_assistant.core.interfaces import AssistantCommandExecutor
from ai_assistant.providers.remote.ws_hub import RemoteWebSocketHub


class HybridAssistantCommandExecutor(AssistantCommandExecutor):
    def __init__(
        self,
        local_executor: AssistantCommandExecutor,
        remote_ws_hub: RemoteWebSocketHub | None = None,
    ) -> None:
        self._local_executor = local_executor
        self._remote_ws_hub = remote_ws_hub

    async def get_command_catalog(self, user_id: int | None = None) -> list[dict[str, object]]:
        catalog = await self._local_executor.get_command_catalog(user_id=user_id)
        if user_id is None or self._remote_ws_hub is None:
            return catalog

        remote_catalog = await self._remote_ws_hub.get_user_command_catalog(user_id)
        return [*catalog, *remote_catalog]

    async def execute_command(
        self,
        command: str,
        args: dict[str, object],
        user_id: int | None = None,
    ) -> dict[str, object]:
        normalized = command.strip().lower()
        if normalized.startswith("remote."):
            if self._remote_ws_hub is None:
                return {"ok": False, "message": "Remote runtime is unavailable."}
            if user_id is None:
                return {"ok": False, "message": "user_id is required for remote commands."}
            return await self._remote_ws_hub.execute_user_remote_command(
                user_id=user_id,
                command=normalized.removeprefix("remote."),
                args=args,
            )

        return await self._local_executor.execute_command(
            command=normalized,
            args=args,
            user_id=user_id,
        )
