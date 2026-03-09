import asyncio
import logging

from ai_assistant.providers.remote.ws_protocol import decode_message
from ai_assistant.remote_client.agent import RemoteClientAgent
from ai_assistant.remote_client.state_store import ClientState


class FakeStateStore:
    def __init__(self, state: ClientState) -> None:
        self._state = state

    def load(self) -> ClientState | None:
        return self._state

    def save(self, state: ClientState) -> None:
        self._state = state


class FakeCommandExecutor:
    async def get_command_catalog(self, user_id: int | None = None) -> list[dict[str, object]]:
        del user_id
        return []

    async def execute_command(
        self,
        command: str,
        args: dict[str, object],
        user_id: int | None = None,
    ) -> dict[str, object]:
        del command, args, user_id
        return {"ok": True, "message": "done"}


class FailingCommandExecutor(FakeCommandExecutor):
    async def execute_command(
        self,
        command: str,
        args: dict[str, object],
        user_id: int | None = None,
    ) -> dict[str, object]:
        del command, args, user_id
        raise RuntimeError("boom")


class FakeWebSocket:
    def __init__(self) -> None:
        self.messages: list[str] = []

    async def send(self, message: str) -> None:
        self.messages.append(message)


def _build_agent(command_executor: object) -> RemoteClientAgent:
    store = FakeStateStore(
        ClientState(
            client_id="client-1",
            auth_token="token",
            server_id="default",
        )
    )
    return RemoteClientAgent(
        server_url="ws://localhost:8765/ws/remote",
        server_id="default",
        client_name="Test Client",
        platform="windows",
        command_executor=command_executor,  # type: ignore[arg-type]
        state_store=store,  # type: ignore[arg-type]
        reconnect_min_seconds=1.0,
        reconnect_max_seconds=5.0,
        ping_interval_seconds=20.0,
        ping_timeout_seconds=20.0,
    )


def test_remote_client_logs_command_request_and_args(caplog) -> None:
    agent = _build_agent(FakeCommandExecutor())
    websocket = FakeWebSocket()
    payload = {
        "command": "filesystem.search_files",
        "args": {"query": "*.mkv", "path": "D:/Media"},
        "wait_for_response": True,
    }

    with caplog.at_level(logging.DEBUG, logger="ai_assistant.remote_client.agent"):
        asyncio.run(agent._handle_command_request(websocket, payload, "req-1"))

    assert any(
        "Remote command request received" in record.message
        and "filesystem.search_files" in record.message
        for record in caplog.records
    )
    assert any("D:/Media" in record.message for record in caplog.records)
    assert len(websocket.messages) == 1

    message_type, response_payload, request_id = decode_message(websocket.messages[0])
    assert message_type == "command_response"
    assert request_id == "req-1"
    assert response_payload["ok"] is True


def test_remote_client_logs_execution_error_and_returns_failure(caplog) -> None:
    agent = _build_agent(FailingCommandExecutor())
    websocket = FakeWebSocket()
    payload = {
        "command": "filesystem.search_files",
        "args": {"query": "*.mkv"},
        "wait_for_response": True,
    }

    with caplog.at_level(logging.DEBUG, logger="ai_assistant.remote_client.agent"):
        asyncio.run(agent._handle_command_request(websocket, payload, "req-err"))

    assert any("Remote command execution failed" in record.message for record in caplog.records)
    assert len(websocket.messages) == 1

    message_type, response_payload, request_id = decode_message(websocket.messages[0])
    assert message_type == "command_response"
    assert request_id == "req-err"
    assert response_payload["ok"] is False
    assert "Command execution error" in str(response_payload["message"])
