from __future__ import annotations

from typing import Protocol

from ai_assistant.core.models import (
    ConversationMessage,
    SettingChoiceOption,
    SettingDefinition,
    TerminalCommandResult,
    UserMessage,
)


class LLMProvider(Protocol):
    async def generate_reply(self, message: UserMessage) -> str:
        ...


class MemoryStore(Protocol):
    async def save_user_message(self, message: UserMessage) -> None:
        ...

    async def save_assistant_message(self, user_id: int, text: str) -> None:
        ...

    async def get_conversation(
        self, user_id: int, limit: int | None = None
    ) -> list[ConversationMessage]:
        ...

    async def clear_conversation(self, user_id: int) -> None:
        ...


class UserSettingsStore(Protocol):
    async def set_setting(self, user_id: int, key: str, value: str) -> None:
        ...

    async def get_setting(self, user_id: int, key: str) -> str | None:
        ...

    async def get_all_settings(self, user_id: int) -> dict[str, str]:
        ...

    async def get_setting_definitions(
        self,
        locale: str | None = None,
    ) -> list[SettingDefinition]:
        ...

    async def get_setting_choice_options(
        self,
        setting_id: str,
        locale: str | None = None,
    ) -> list[SettingChoiceOption]:
        ...


class TranslationService(Protocol):
    def get_default_locale(self) -> str:
        ...

    def resolve_locale(self, locale: str | None) -> str:
        ...

    def translate(self, message_key: str, locale: str | None = None, **params: object) -> str:
        ...


class PermissionChecker(Protocol):
    async def has_permission(self, user_id: int, permission_type: str, name: str) -> bool:
        ...


class PermissionAdminStore(PermissionChecker, Protocol):
    async def set_user_permission(
        self,
        user_id: int,
        permission_type: str,
        name: str,
        is_active: bool,
    ) -> None:
        ...

    async def create_role(self, role_name: str) -> None:
        ...

    async def assign_role(self, user_id: int, role_name: str) -> None:
        ...

    async def grant_role_permission(
        self,
        role_name: str,
        permission_type: str,
        name: str,
    ) -> None:
        ...

    async def revoke_role_permission(
        self,
        role_name: str,
        permission_type: str,
        name: str,
    ) -> None:
        ...

    async def get_user_roles(self, user_id: int) -> list[str]:
        ...

    async def get_user_permission_report(
        self,
        user_id: int,
    ) -> dict[str, list[dict[str, object]]]:
        ...


class AssistantCommandExecutor(Protocol):
    def get_command_catalog(self) -> list[dict[str, object]]:
        ...

    def execute_command(self, command: str, args: dict[str, object]) -> dict[str, object]:
        ...


class OutputController(Protocol):
    def enable_output(self) -> bool:
        ...

    def disable_output(self) -> bool:
        ...

    def toggle_output(self) -> bool:
        ...

    def is_output_enabled(self) -> bool:
        ...


class TerminalCommandExecutor(Protocol):
    async def start_session(self, session_id: int) -> None:
        ...

    async def close_session(self, session_id: int) -> None:
        ...

    def is_session_active(self, session_id: int) -> bool:
        ...

    async def run_command(self, session_id: int, command: str) -> TerminalCommandResult:
        ...

    def describe_shell(self) -> str:
        ...


class ChannelModule(Protocol):
    def run(self) -> None:
        ...


class MediaController(Protocol):
    def play_pause(self) -> None:
        ...

    def previous_track(self) -> None:
        ...

    def next_track(self) -> None:
        ...


class MPCController(Protocol):
    def audio_next(self) -> bool:
        ...

    def audio_previous(self) -> bool:
        ...

    def subtitle_next(self) -> bool:
        ...

    def subtitle_previous(self) -> bool:
        ...

    def audio_set_language(self, language: str) -> bool:
        ...

    def subtitle_set_language(self, language: str) -> bool:
        ...
