from __future__ import annotations

import asyncio
import logging
import uuid

from ai_assistant.core.interfaces import AssistantCommandExecutor
from ai_assistant.providers.remote.ws_protocol import decode_message, encode_message
from ai_assistant.remote_client.state_store import ClientState, FileClientStateStore

logger = logging.getLogger(__name__)


class RemoteClientAgent:
    def __init__(
        self,
        *,
        server_url: str,
        server_id: str,
        client_name: str,
        platform: str,
        command_executor: AssistantCommandExecutor,
        state_store: FileClientStateStore,
        reconnect_min_seconds: float,
        reconnect_max_seconds: float,
        ping_interval_seconds: float,
        ping_timeout_seconds: float,
    ) -> None:
        self._server_url = server_url
        self._server_id = server_id.strip().lower() or "default"
        self._client_name = client_name.strip() or "AI Assistant Client"
        self._platform = platform.strip().lower() or "windows"
        self._command_executor = command_executor
        self._state_store = state_store
        self._reconnect_min_seconds = max(reconnect_min_seconds, 0.1)
        self._reconnect_max_seconds = max(reconnect_max_seconds, self._reconnect_min_seconds)
        self._ping_interval_seconds = max(ping_interval_seconds, 1.0)
        self._ping_timeout_seconds = max(ping_timeout_seconds, 1.0)

        self._state = self._load_or_create_state()

    async def run_forever(self) -> None:
        reconnect_delay = self._reconnect_min_seconds
        while True:
            try:
                await self._run_connection()
                reconnect_delay = self._reconnect_min_seconds
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Remote client disconnected: error=%s", exc)
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2.0, self._reconnect_max_seconds)

    async def _run_connection(self) -> None:
        try:
            import websockets
        except ImportError as exc:
            raise RuntimeError(
                "websockets is required for remote client. Install dependency: pip install websockets"
            ) from exc

        async with websockets.connect(  # type: ignore[attr-defined]
            self._server_url,
            ping_interval=self._ping_interval_seconds,
            ping_timeout=self._ping_timeout_seconds,
        ) as websocket:
            await self._send_hello(websocket)

            async for raw_message in websocket:
                if not isinstance(raw_message, str):
                    continue
                message_type, payload, request_id = decode_message(raw_message)
                if message_type == "hello_ack":
                    await self._handle_hello_ack(payload)
                    continue
                if message_type == "link_completed":
                    await self._handle_link_completed(payload)
                    continue
                if message_type == "command_request":
                    await self._handle_command_request(websocket, payload, request_id)
                    continue
                if message_type == "error":
                    logger.warning("Remote server error: %s", payload)

    async def _send_hello(self, websocket: object) -> None:
        commands = await self._command_executor.get_command_catalog(user_id=None)
        message = encode_message(
            message_type="hello",
            payload={
                "client_id": self._state.client_id,
                "client_name": self._client_name,
                "platform": self._platform,
                "server_id": self._server_id,
                "auth_token": self._state.auth_token,
                "commands": commands,
            },
        )
        await websocket.send(message)  # type: ignore[attr-defined]

    async def _handle_hello_ack(self, payload: dict[str, object]) -> None:
        status = str(payload.get("status", "")).strip().lower()
        if status == "authenticated":
            logger.info(
                "Remote client authenticated: client_id=%s owner_user_id=%s",
                payload.get("client_id"),
                payload.get("owner_user_id"),
            )
            return
        if status == "link_required":
            code = str(payload.get("code", "")).strip()
            expires_at = str(payload.get("expires_at", "")).strip()
            print("=" * 80)
            print("Remote client is not linked to a Telegram user yet.")
            print(f"One-time link code: {code}")
            print("Send to Telegram: /pc_link <code>")
            if expires_at:
                print(f"Code expires at: {expires_at}")
            print("=" * 80)

    async def _handle_link_completed(self, payload: dict[str, object]) -> None:
        auth_token = str(payload.get("auth_token", "")).strip()
        client_id = str(payload.get("client_id", self._state.client_id)).strip().lower()
        if not auth_token:
            return

        self._state = ClientState(
            client_id=client_id or self._state.client_id,
            auth_token=auth_token,
            server_id=self._server_id,
        )
        self._state_store.save(self._state)
        logger.info("Remote client linked successfully: client_id=%s", self._state.client_id)

    async def _handle_command_request(
        self,
        websocket: object,
        payload: dict[str, object],
        request_id: str | None,
    ) -> None:
        if request_id is None:
            return

        command = str(payload.get("command", "")).strip().lower()
        args_raw = payload.get("args")
        wait_for_response = bool(payload.get("wait_for_response", True))
        args = args_raw if isinstance(args_raw, dict) else {}

        if command == "client.unlink_server":
            self._state = ClientState(
                client_id=self._state.client_id,
                auth_token="",
                server_id=self._state.server_id,
            )
            self._state_store.save(self._state)
            result: dict[str, object] = {"ok": True, "message": "Server link removed on client."}
        else:
            result = await self._command_executor.execute_command(
                command=command,
                args=args,
                user_id=None,
            )

        if wait_for_response:
            message = encode_message(
                message_type="command_response",
                request_id=request_id,
                payload=result,
            )
            await websocket.send(message)  # type: ignore[attr-defined]

    def clear_link(self) -> None:
        self._state = ClientState(
            client_id=self._state.client_id,
            auth_token="",
            server_id=self._state.server_id,
        )
        self._state_store.save(self._state)

    def _load_or_create_state(self) -> ClientState:
        state = self._state_store.load()
        if state is not None:
            if not state.server_id:
                state.server_id = self._server_id
                self._state_store.save(state)
            return state

        new_state = ClientState(
            client_id=str(uuid.uuid4()),
            auth_token="",
            server_id=self._server_id,
        )
        self._state_store.save(new_state)
        return new_state
