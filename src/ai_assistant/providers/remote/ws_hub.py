from __future__ import annotations

import asyncio
import logging
import ssl
import uuid
from dataclasses import dataclass, field

from ai_assistant.providers.remote.remote_device_service import (
    AccessDeniedError,
    RemoteDeviceService,
)
from ai_assistant.providers.remote.types import LinkDeviceResult
from ai_assistant.providers.remote.ws_protocol import RemoteProtocolError, decode_message, encode_message

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _ConnectionState:
    session_id: str
    websocket: object
    client_id: str | None = None
    user_id: int | None = None
    server_id: str | None = None
    commands: dict[str, dict[str, object]] = field(default_factory=dict)


@dataclass(slots=True)
class _PendingCommand:
    future: asyncio.Future[dict[str, object]]
    client_id: str


class RemoteWebSocketHub:
    def __init__(
        self,
        *,
        device_service: RemoteDeviceService,
        host: str,
        port: int,
        path: str,
        server_id: str,
        request_timeout_seconds: float,
        ping_interval_seconds: float,
        ping_timeout_seconds: float,
        tls_cert_path: str = "",
        tls_key_path: str = "",
    ) -> None:
        self._device_service = device_service
        self._host = host
        self._port = port
        self._path = path.strip() or "/"
        self._server_id = server_id.strip().lower()
        self._request_timeout_seconds = max(request_timeout_seconds, 0.1)
        self._ping_interval_seconds = max(ping_interval_seconds, 1.0)
        self._ping_timeout_seconds = max(ping_timeout_seconds, 1.0)
        self._tls_cert_path = tls_cert_path.strip()
        self._tls_key_path = tls_key_path.strip()

        self._server: object | None = None
        self._connections_by_session: dict[str, _ConnectionState] = {}
        self._connections_by_client: dict[str, _ConnectionState] = {}
        self._pending_commands: dict[str, _PendingCommand] = {}
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        if self._server is not None:
            return

        try:
            import websockets
        except ImportError as exc:
            raise RuntimeError(
                "websockets is required for remote hub. Install dependency: pip install websockets"
            ) from exc

        ssl_context = self._build_ssl_context()
        self._server = await websockets.serve(  # type: ignore[attr-defined]
            self._handle_connection,
            self._host,
            self._port,
            ping_interval=self._ping_interval_seconds,
            ping_timeout=self._ping_timeout_seconds,
            ssl=ssl_context,
        )
        logger.info(
            "Remote WS hub started: host=%s port=%s path=%s server_id=%s tls=%s",
            self._host,
            self._port,
            self._path,
            self._server_id,
            bool(ssl_context),
        )

    async def stop(self) -> None:
        if self._server is None:
            return

        server = self._server
        self._server = None

        server.close()  # type: ignore[union-attr]
        await server.wait_closed()  # type: ignore[union-attr]

        async with self._lock:
            pending = list(self._pending_commands.values())
            self._pending_commands.clear()
        for item in pending:
            if not item.future.done():
                item.future.set_result(
                    {
                        "ok": False,
                        "message": "Remote hub stopped before response was received.",
                    }
                )

        logger.info("Remote WS hub stopped.")

    async def complete_link_code(self, *, user_id: int, code: str) -> LinkDeviceResult:
        result = await self._device_service.link_device(user_id=user_id, code=code)
        state = self._connections_by_session.get(result.session_id)
        if state is not None:
            state.client_id = result.client.client_id
            state.user_id = result.client.owner_user_id
            state.server_id = result.client.server_id
            self._connections_by_client[result.client.client_id] = state
            await self._send_message(
                state.websocket,
                message_type="link_completed",
                payload={
                    "client_id": result.client.client_id,
                    "owner_user_id": result.client.owner_user_id,
                    "auth_token": result.auth_token,
                },
            )

        return result

    async def get_user_command_catalog(self, user_id: int) -> list[dict[str, object]]:
        user_clients = await self._device_service.list_user_clients(user_id)
        aggregate: dict[str, dict[str, object]] = {}

        for client in user_clients:
            state = self._connections_by_client.get(client.client_id)
            if state is None:
                continue
            for base_command, command_spec in state.commands.items():
                entry = aggregate.get(base_command)
                if entry is None:
                    entry = {
                        "description": str(command_spec.get("description", "")).strip(),
                        "args": dict(command_spec.get("args", {})),
                        "clients": [],
                        "default_client_id": None,
                    }
                    aggregate[base_command] = entry

                clients = entry["clients"]
                if isinstance(clients, list) and client.client_id not in clients:
                    clients.append(client.client_id)

                if client.is_default:
                    entry["default_client_id"] = client.client_id

        catalog: list[dict[str, object]] = []
        for base_command, payload in sorted(aggregate.items()):
            args = dict(payload["args"])
            args.setdefault(
                "client_id",
                "optional client id; default device is used when omitted",
            )
            description = str(payload.get("description", "")).strip() or f"Execute {base_command}"
            clients = payload.get("clients", [])
            catalog.append(
                {
                    "command": f"remote.{base_command}",
                    "description": f"Remote: {description}",
                    "args": args,
                    "remote": {
                        "clients": clients,
                        "default_client_id": payload.get("default_client_id"),
                    },
                }
            )

        return catalog

    async def execute_user_remote_command(
        self,
        *,
        user_id: int,
        command: str,
        args: dict[str, object],
    ) -> dict[str, object]:
        normalized_command = command.strip().lower()
        if not normalized_command:
            return {"ok": False, "message": "Remote command name is empty."}

        payload_args = dict(args)
        raw_client = payload_args.pop("client_id", None)
        client_id: str | None
        if isinstance(raw_client, str) and raw_client.strip():
            client_id = raw_client.strip().lower()
        else:
            client_id = await self._device_service.get_user_default_client_id(user_id)

        if not client_id:
            user_clients = await self._device_service.list_user_clients(user_id)
            eligible = [
                client.client_id
                for client in user_clients
                if client.client_id in self._connections_by_client
                and self._client_supports_command(client.client_id, normalized_command)
            ]
            if len(eligible) == 1:
                client_id = eligible[0]
            elif not eligible:
                return {
                    "ok": False,
                    "message": "No online devices with access are available for this command.",
                }
            else:
                return {
                    "ok": False,
                    "message": "Multiple devices available. Set default device or pass client_id.",
                }

        if not self._client_supports_command(client_id, normalized_command):
            return {
                "ok": False,
                "message": f"Client {client_id} does not support command: {normalized_command}",
            }

        result = await self.execute_client_command(
            user_id=user_id,
            client_id=client_id,
            command=normalized_command,
            args=payload_args,
            wait_for_response=True,
        )
        if "client_id" not in result:
            result["client_id"] = client_id
        return result

    async def execute_client_command(
        self,
        *,
        user_id: int,
        client_id: str,
        command: str,
        args: dict[str, object],
        wait_for_response: bool = True,
        timeout_seconds: float | None = None,
    ) -> dict[str, object]:
        normalized_client_id = client_id.strip().lower()
        has_access = await self._device_service.user_has_access(
            user_id=user_id,
            client_id=normalized_client_id,
        )
        if not has_access:
            raise AccessDeniedError("No access to this client.")

        state = self._connections_by_client.get(normalized_client_id)
        if state is None:
            return {"ok": False, "message": "Client is offline."}

        request_id = str(uuid.uuid4())
        future: asyncio.Future[dict[str, object]] | None = None
        if wait_for_response:
            future = asyncio.get_running_loop().create_future()
            async with self._lock:
                self._pending_commands[request_id] = _PendingCommand(
                    future=future,
                    client_id=normalized_client_id,
                )

        await self._send_message(
            state.websocket,
            message_type="command_request",
            request_id=request_id,
            payload={
                "command": command,
                "args": args,
                "wait_for_response": wait_for_response,
            },
        )

        if not wait_for_response:
            return {"ok": True, "message": "Command dispatched."}

        assert future is not None
        timeout = timeout_seconds if timeout_seconds is not None else self._request_timeout_seconds
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            async with self._lock:
                self._pending_commands.pop(request_id, None)
            return {
                "ok": False,
                "message": f"Client response timeout for request_id={request_id}",
            }

    async def _handle_connection(self, websocket: object) -> None:
        raw_path = str(getattr(websocket, "path", "") or "")
        path = raw_path.split("?", 1)[0]
        if path and path != self._path:
            await websocket.close(code=1008, reason="Invalid path")  # type: ignore[attr-defined]
            return

        session_id = str(uuid.uuid4())
        state = _ConnectionState(session_id=session_id, websocket=websocket)
        self._connections_by_session[session_id] = state
        logger.info("Remote WS connection opened: session_id=%s", session_id)

        try:
            async for raw_message in websocket:  # type: ignore[attr-defined]
                if not isinstance(raw_message, str):
                    continue
                await self._process_message(state, raw_message)
        except Exception as exc:
            logger.warning("Remote WS connection error: session_id=%s error=%s", session_id, exc)
        finally:
            await self._cleanup_connection(state)

    async def _process_message(self, state: _ConnectionState, raw_message: str) -> None:
        try:
            message_type, payload, request_id = decode_message(raw_message)
        except RemoteProtocolError as exc:
            await self._send_message(
                state.websocket,
                message_type="error",
                payload={"message": str(exc)},
            )
            return

        if message_type == "hello":
            await self._handle_hello(state, payload)
            return

        if message_type == "command_response":
            if request_id:
                await self._handle_command_response(request_id=request_id, payload=payload)
            return

        if message_type == "event":
            logger.info(
                "Remote client event: session_id=%s client_id=%s payload=%s",
                state.session_id,
                state.client_id,
                payload,
            )
            return

    async def _handle_hello(self, state: _ConnectionState, payload: dict[str, object]) -> None:
        client_id = str(payload.get("client_id", "")).strip().lower()
        client_name = str(payload.get("client_name", "")).strip()
        platform = str(payload.get("platform", "windows")).strip().lower() or "windows"
        server_id = str(payload.get("server_id", self._server_id)).strip().lower() or self._server_id
        auth_token = str(payload.get("auth_token", "")).strip()
        commands = self._normalize_command_catalog(payload.get("commands"))
        state.commands = commands

        if not client_id:
            await self._send_message(
                state.websocket,
                message_type="error",
                payload={"message": "client_id is required in hello payload."},
            )
            return
        if server_id != self._server_id:
            await self._send_message(
                state.websocket,
                message_type="error",
                payload={"message": f"Unknown server_id: {server_id}"},
            )
            return

        if auth_token:
            client = await self._device_service.authenticate_client(
                client_id=client_id,
                server_id=server_id,
                auth_token=auth_token,
            )
            if client is not None:
                state.client_id = client.client_id
                state.user_id = client.owner_user_id
                state.server_id = client.server_id
                self._connections_by_client[client.client_id] = state
                await self._device_service.mark_client_seen(client.client_id)
                await self._send_message(
                    state.websocket,
                    message_type="hello_ack",
                    payload={
                        "status": "authenticated",
                        "client_id": client.client_id,
                        "owner_user_id": client.owner_user_id,
                    },
                )
                return

        link = await self._device_service.issue_link_code(
            session_id=state.session_id,
            client_id=client_id,
            display_name=client_name,
            platform=platform,
            server_id=server_id,
        )
        await self._send_message(
            state.websocket,
            message_type="hello_ack",
            payload={
                "status": "link_required",
                "code": link.code,
                "expires_at": link.expires_at.isoformat(),
                "server_id": link.server_id,
            },
        )

    async def _handle_command_response(self, *, request_id: str, payload: dict[str, object]) -> None:
        async with self._lock:
            pending = self._pending_commands.pop(request_id, None)
        if pending is None:
            return
        if not pending.future.done():
            pending.future.set_result(payload)

    async def _cleanup_connection(self, state: _ConnectionState) -> None:
        self._connections_by_session.pop(state.session_id, None)
        if state.client_id:
            active = self._connections_by_client.get(state.client_id)
            if active and active.session_id == state.session_id:
                self._connections_by_client.pop(state.client_id, None)

        async with self._lock:
            items = list(self._pending_commands.items())
            self._pending_commands = {
                request_id: pending
                for request_id, pending in items
                if pending.client_id != (state.client_id or "")
            }
        for request_id, pending in items:
            if pending.client_id != (state.client_id or ""):
                continue
            if not pending.future.done():
                pending.future.set_result(
                    {
                        "ok": False,
                        "message": "Connection closed before command response was received.",
                        "request_id": request_id,
                    }
                )

        logger.info(
            "Remote WS connection closed: session_id=%s client_id=%s",
            state.session_id,
            state.client_id,
        )

    async def _send_message(
        self,
        websocket: object,
        *,
        message_type: str,
        payload: dict[str, object],
        request_id: str | None = None,
    ) -> None:
        message = encode_message(
            message_type=message_type,
            payload=payload,
            request_id=request_id,
        )
        await websocket.send(message)  # type: ignore[attr-defined]

    @staticmethod
    def _normalize_command_catalog(raw_value: object) -> dict[str, dict[str, object]]:
        if not isinstance(raw_value, list):
            return {}

        result: dict[str, dict[str, object]] = {}
        for item in raw_value:
            if not isinstance(item, dict):
                continue
            command = item.get("command")
            if not isinstance(command, str):
                continue
            normalized_command = command.strip().lower()
            if not normalized_command:
                continue
            description = item.get("description", "")
            args = item.get("args", {})
            if not isinstance(description, str):
                description = str(description)
            if not isinstance(args, dict):
                args = {}
            result[normalized_command] = {
                "description": description.strip(),
                "args": dict(args),
            }
        return result

    def _client_supports_command(self, client_id: str, command: str) -> bool:
        state = self._connections_by_client.get(client_id)
        if state is None:
            return False
        return command in state.commands

    def _build_ssl_context(self) -> ssl.SSLContext | None:
        if not self._tls_cert_path and not self._tls_key_path:
            return None
        if not self._tls_cert_path or not self._tls_key_path:
            raise RuntimeError(
                "Both AI_ASSISTANT_REMOTE_TLS_CERT_PATH and AI_ASSISTANT_REMOTE_TLS_KEY_PATH are required for TLS."
            )

        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(self._tls_cert_path, self._tls_key_path)
        return context
