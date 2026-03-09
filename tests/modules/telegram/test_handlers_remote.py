import asyncio
import base64
from datetime import datetime, timezone
from types import SimpleNamespace

from ai_assistant.modules.telegram.handlers import TelegramHandlers
from ai_assistant.providers.remote.types import LinkDeviceResult, RemoteClientRecord, UserRemoteClient
from tests.modules.telegram._shared import FakeAssistantService, FakePermissionChecker, FakeUpdate


class FakeRemoteHub:
    def __init__(self) -> None:
        self.completed: list[tuple[int, str]] = []
        self.executed: list[tuple[int, str, str]] = []

    async def complete_link_code(self, *, user_id: int, code: str) -> LinkDeviceResult:
        self.completed.append((user_id, code))
        client = RemoteClientRecord(
            client_id="pc-1",
            owner_user_id=user_id,
            display_name="Home PC",
            platform="windows",
            server_id="default",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            last_seen_at=None,
        )
        return LinkDeviceResult(
            session_id="s1",
            client=client,
            auth_token="token",
            default_assigned=True,
        )

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
        del args, wait_for_response, timeout_seconds
        self.executed.append((user_id, client_id, command))
        return {"ok": True}

    async def execute_user_remote_command(
        self,
        *,
        user_id: int,
        command: str,
        args: dict[str, object],
    ) -> dict[str, object]:
        del args
        self.executed.append((user_id, "default", command))
        return {"ok": True, "client_id": "pc-1", "message": "done"}


class FakeRemoteDeviceService:
    def __init__(self) -> None:
        self.defaults: list[tuple[int, str | None]] = []
        self.unlinked: list[tuple[int, str]] = []

    async def list_user_clients(self, user_id: int) -> list[UserRemoteClient]:
        del user_id
        return [
            UserRemoteClient(
                client_id="pc-1",
                display_name="Home PC",
                platform="windows",
                server_id="default",
                is_owner=True,
                is_default=True,
                last_seen_at=None,
            )
        ]

    async def set_default_client(self, user_id: int, client_id: str | None) -> None:
        self.defaults.append((user_id, client_id))

    async def unlink_client(self, *, owner_user_id: int, client_id: str) -> None:
        self.unlinked.append((owner_user_id, client_id))


class FakeRemoteHubWithDocument(FakeRemoteHub):
    async def execute_user_remote_command(
        self,
        *,
        user_id: int,
        command: str,
        args: dict[str, object],
    ) -> dict[str, object]:
        del args
        self.executed.append((user_id, "default", command))
        payload = base64.b64encode(b"hello").decode("ascii")
        return {
            "ok": True,
            "client_id": "pc-1",
            "message": "file prepared",
            "telegram_documents": [
                {
                    "filename": "hello.txt",
                    "caption": "generated",
                    "content_base64": payload,
                }
            ],
        }



def test_handle_pc_link_success() -> None:
    assistant = FakeAssistantService()
    permissions = FakePermissionChecker(
        allowed={(101, "general", "usage"), (101, "command", "pc_link")}
    )
    hub = FakeRemoteHub()
    handlers = TelegramHandlers(
        assistant_service=assistant,
        permission_checker=permissions,
        remote_ws_hub=hub,
    )
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=["ABCD1234"])

    asyncio.run(handlers.handle_pc_link(update, context))

    assert hub.completed == [(101, "ABCD1234")]
    assert "Linked device successfully" in update.effective_message.replies[0]


def test_handle_pc_list_returns_devices() -> None:
    assistant = FakeAssistantService()
    permissions = FakePermissionChecker(
        allowed={(101, "general", "usage"), (101, "command", "pc_list")}
    )
    remote_service = FakeRemoteDeviceService()
    handlers = TelegramHandlers(
        assistant_service=assistant,
        permission_checker=permissions,
        remote_device_service=remote_service,
    )
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=[])

    asyncio.run(handlers.handle_pc_list(update, context))

    text = update.effective_message.replies[0]
    assert "Your devices:" in text
    assert "pc-1" in text


def test_handle_pc_unlink_invokes_remote_services() -> None:
    assistant = FakeAssistantService()
    permissions = FakePermissionChecker(
        allowed={(101, "general", "usage"), (101, "command", "pc_unlink")}
    )
    remote_service = FakeRemoteDeviceService()
    hub = FakeRemoteHub()
    handlers = TelegramHandlers(
        assistant_service=assistant,
        permission_checker=permissions,
        remote_device_service=remote_service,
        remote_ws_hub=hub,
    )
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=["pc-1"])

    asyncio.run(handlers.handle_pc_unlink(update, context))

    assert hub.executed == [(101, "pc-1", "client.unlink_server")]
    assert remote_service.unlinked == [(101, "pc-1")]
    assert update.effective_message.replies == ["Client unlinked: pc-1"]


def test_handle_pc_run_dispatches_remote_command() -> None:
    assistant = FakeAssistantService()
    permissions = FakePermissionChecker(
        allowed={(101, "general", "usage"), (101, "command", "pc_run")}
    )
    hub = FakeRemoteHub()
    remote_service = FakeRemoteDeviceService()
    handlers = TelegramHandlers(
        assistant_service=assistant,
        permission_checker=permissions,
        remote_ws_hub=hub,
        remote_device_service=remote_service,
    )
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=["media.play_pause"])

    asyncio.run(handlers.handle_pc_run(update, context))

    assert hub.executed == [(101, "default", "media.play_pause")]
    assert "Remote command result:" in update.effective_message.replies[0]


def test_handle_pc_run_requires_list_permission_for_filesystem_listing() -> None:
    assistant = FakeAssistantService()
    permissions = FakePermissionChecker(
        allowed={(101, "general", "usage"), (101, "command", "pc_run")}
    )
    hub = FakeRemoteHub()
    handlers = TelegramHandlers(
        assistant_service=assistant,
        permission_checker=permissions,
        remote_ws_hub=hub,
    )
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=["filesystem.list_directory", '{"path":"C:\\\\tmp"}'])

    asyncio.run(handlers.handle_pc_run(update, context))

    assert hub.executed == []
    assert "assistant/remote.filesystem.list_directory" in update.effective_message.replies[0]


def test_handle_pc_run_requires_list_permission_for_filesystem_search() -> None:
    assistant = FakeAssistantService()
    permissions = FakePermissionChecker(
        allowed={(101, "general", "usage"), (101, "command", "pc_run")}
    )
    hub = FakeRemoteHub()
    handlers = TelegramHandlers(
        assistant_service=assistant,
        permission_checker=permissions,
        remote_ws_hub=hub,
    )
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=["filesystem.search_files", '{"query":"*.mkv","path":"D:\\\\Media"}'])

    asyncio.run(handlers.handle_pc_run(update, context))

    assert hub.executed == []
    assert "assistant/remote.filesystem.list_directory" in update.effective_message.replies[0]


def test_handle_pc_run_requires_read_permission_for_filesystem_read() -> None:
    assistant = FakeAssistantService()
    permissions = FakePermissionChecker(
        allowed={(101, "general", "usage"), (101, "command", "pc_run")}
    )
    hub = FakeRemoteHub()
    handlers = TelegramHandlers(
        assistant_service=assistant,
        permission_checker=permissions,
        remote_ws_hub=hub,
    )
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(args=["filesystem.read_file", '{"path":"C:\\\\tmp\\\\note.txt"}'])

    asyncio.run(handlers.handle_pc_run(update, context))

    assert hub.executed == []
    assert "assistant/remote.filesystem.read_file" in update.effective_message.replies[0]


def test_handle_pc_run_requires_write_permission_for_filesystem_write() -> None:
    assistant = FakeAssistantService()
    permissions = FakePermissionChecker(
        allowed={(101, "general", "usage"), (101, "command", "pc_run")}
    )
    hub = FakeRemoteHub()
    handlers = TelegramHandlers(
        assistant_service=assistant,
        permission_checker=permissions,
        remote_ws_hub=hub,
    )
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(
        args=[
            "filesystem.write_file",
            '{"path":"C:\\\\tmp\\\\note.txt","content":"hello"}',
        ]
    )

    asyncio.run(handlers.handle_pc_run(update, context))

    assert hub.executed == []
    assert "assistant/remote.filesystem.write_file" in update.effective_message.replies[0]


def test_handle_pc_run_allows_filesystem_write_with_permission() -> None:
    assistant = FakeAssistantService()
    permissions = FakePermissionChecker(
        allowed={
            (101, "general", "usage"),
            (101, "command", "pc_run"),
            (101, "assistant", "remote.filesystem.write_file"),
        }
    )
    hub = FakeRemoteHub()
    handlers = TelegramHandlers(
        assistant_service=assistant,
        permission_checker=permissions,
        remote_ws_hub=hub,
    )
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(
        args=[
            "filesystem.write_file",
            '{"path":"C:\\\\tmp\\\\note.txt","content":"hello"}',
        ]
    )

    asyncio.run(handlers.handle_pc_run(update, context))

    assert hub.executed == [(101, "default", "filesystem.write_file")]
    assert "Remote command result:" in update.effective_message.replies[0]


def test_handle_pc_run_sends_telegram_document_from_remote_result() -> None:
    assistant = FakeAssistantService()
    permissions = FakePermissionChecker(
        allowed={
            (101, "general", "usage"),
            (101, "command", "pc_run"),
            (101, "assistant", "remote.filesystem.read_file"),
        }
    )
    hub = FakeRemoteHubWithDocument()
    handlers = TelegramHandlers(
        assistant_service=assistant,
        permission_checker=permissions,
        remote_ws_hub=hub,
    )
    update = FakeUpdate(user_id=101)
    context = SimpleNamespace(
        args=[
            "filesystem.send_file",
            '{"path":"C:\\\\tmp\\\\hello.txt"}',
        ]
    )

    asyncio.run(handlers.handle_pc_run(update, context))

    assert hub.executed == [(101, "default", "filesystem.send_file")]
    assert len(update.effective_message.documents) == 1
    assert update.effective_message.documents[0]["filename"] == "hello.txt"
    assert "telegram_documents_sent" in update.effective_message.replies[0]
    assert "content_base64" not in update.effective_message.replies[0]
