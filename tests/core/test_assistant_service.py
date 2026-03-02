import asyncio

from ai_assistant.core.service import AssistantService
from ai_assistant.providers.memory.in_memory_store import InMemoryStore


class RecordingLLMProvider:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate_reply(self, message) -> str:
        self.prompts.append(message.text)
        return f"llm: {len(self.prompts)}"


class SequencedLLMProvider:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.prompts: list[str] = []

    async def generate_reply(self, message) -> str:
        self.prompts.append(message.text)
        if not self._responses:
            return "no-response"
        return self._responses.pop(0)


class FakeCommandExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get_command_catalog(self) -> list[dict[str, object]]:
        return [
            {
                "command": "media.play_pause",
                "description": "Toggle playback.",
                "args": {},
            }
        ]

    def execute_command(self, command: str, args: dict[str, object]) -> dict[str, object]:
        self.calls.append((command, args))
        return {"ok": True, "message": "Playback toggled."}


class FakePermissionChecker:
    def __init__(self, allowed: set[tuple[int, str, str]] | None = None) -> None:
        self.allowed = allowed or set()
        self.calls: list[tuple[int, str, str]] = []

    async def has_permission(self, user_id: int, permission_type: str, name: str) -> bool:
        key = (user_id, permission_type, name)
        self.calls.append(key)
        return key in self.allowed


class FakeUserSettingsStore:
    def __init__(self, values: dict[tuple[int, str], str] | None = None) -> None:
        self.values = values or {}

    async def set_setting(self, user_id: int, key: str, value: str) -> None:
        self.values[(user_id, key)] = value

    async def get_setting(self, user_id: int, key: str) -> str | None:
        return self.values.get((user_id, key))

    async def get_all_settings(self, user_id: int) -> dict[str, str]:
        return {
            k: v
            for (uid, k), v in self.values.items()
            if uid == user_id
        }

    async def get_setting_definitions(self, locale: str | None = None):
        del locale
        return []

    async def get_setting_choice_options(self, setting_id: str, locale: str | None = None):
        del setting_id, locale
        return []


def test_service_uses_history_and_clear_context() -> None:
    llm = RecordingLLMProvider()
    store = InMemoryStore()
    service = AssistantService(llm_provider=llm, memory_store=store, history_limit_messages=20)

    first_reply = asyncio.run(service.process_text(user_id=11, text="Привет"))
    second_reply = asyncio.run(service.process_text(user_id=11, text="Как дела?"))

    assert first_reply.text == "llm: 1"
    assert second_reply.text == "llm: 2"
    assert llm.prompts[0] == "Привет"
    assert "Пользователь: Привет" in llm.prompts[1]
    assert "Ассистент: llm: 1" in llm.prompts[1]
    assert "Пользователь: Как дела?" in llm.prompts[1]

    asyncio.run(service.clear_context(user_id=11))
    third_reply = asyncio.run(service.process_text(user_id=11, text="Новый диалог"))

    assert third_reply.text == "llm: 3"
    assert llm.prompts[2] == "Новый диалог"


def test_service_executes_tool_call_and_requests_final_answer() -> None:
    llm = SequencedLLMProvider(
        responses=[
            '<tool_call>{"command":"media.play_pause","args":{}}</tool_call>',
            "Done. Playback toggled.",
        ]
    )
    store = InMemoryStore()
    executor = FakeCommandExecutor()
    service = AssistantService(
        llm_provider=llm,
        memory_store=store,
        command_executor=executor,
    )

    reply = asyncio.run(service.process_text(user_id=21, text="pause music"))

    assert reply.text == "Done. Playback toggled."
    assert executor.calls == [("media.play_pause", {})]
    assert len(llm.prompts) == 2
    assert "Available commands JSON" in llm.prompts[0]
    assert "Результаты выполнения команд" in llm.prompts[1]


def test_service_applies_user_language_from_settings_to_prompt() -> None:
    llm = RecordingLLMProvider()
    store = InMemoryStore()
    user_settings = FakeUserSettingsStore(values={(55, "language"): "en"})
    service = AssistantService(
        llm_provider=llm,
        memory_store=store,
        user_settings_store=user_settings,
    )

    reply = asyncio.run(service.process_text(user_id=55, text="Привет"))

    assert reply.text == "llm: 1"
    assert "Preferred response language: English (en)." in llm.prompts[0]
    assert "Пользователь: Привет" in llm.prompts[0]
    assert len(llm.prompts) == 1
    assert "Available commands JSON" not in llm.prompts[0]


def test_service_denies_tool_call_without_assistant_permission() -> None:
    llm = SequencedLLMProvider(
        responses=[
            '<tool_call>{"command":"media.play_pause","args":{}}</tool_call>',
            "Denied by policy.",
        ]
    )
    store = InMemoryStore()
    executor = FakeCommandExecutor()
    permission_checker = FakePermissionChecker(allowed=set())
    service = AssistantService(
        llm_provider=llm,
        memory_store=store,
        command_executor=executor,
        permission_checker=permission_checker,
    )

    reply = asyncio.run(service.process_text(user_id=77, text="pause music"))

    assert reply.text == "Denied by policy."
    assert executor.calls == []
    assert "Permission denied for assistant action: media.play_pause" in llm.prompts[1]


def test_service_filters_catalog_by_assistant_permissions() -> None:
    llm = SequencedLLMProvider(
        responses=[
            "No tool needed.",
        ]
    )
    store = InMemoryStore()
    executor = FakeCommandExecutor()
    permission_checker = FakePermissionChecker(
        allowed={(88, "assistant", "media.play_pause")}
    )
    service = AssistantService(
        llm_provider=llm,
        memory_store=store,
        command_executor=executor,
        permission_checker=permission_checker,
    )

    asyncio.run(service.process_text(user_id=88, text="music"))

    assert "Available commands JSON" in llm.prompts[0]
    assert '"media.play_pause"' in llm.prompts[0]


def test_admin_telegram_id_bypasses_assistant_permissions() -> None:
    llm = SequencedLLMProvider(
        responses=[
            '<tool_call>{"command":"media.play_pause","args":{}}</tool_call>',
            "Done for admin.",
        ]
    )
    store = InMemoryStore()
    executor = FakeCommandExecutor()
    permission_checker = FakePermissionChecker(allowed=set())
    service = AssistantService(
        llm_provider=llm,
        memory_store=store,
        command_executor=executor,
        permission_checker=permission_checker,
        admin_telegram_id=999,
    )

    reply = asyncio.run(service.process_text(user_id=999, text="pause music"))

    assert reply.text == "Done for admin."
    assert executor.calls == [("media.play_pause", {})]
