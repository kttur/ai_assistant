import asyncio
from types import SimpleNamespace

from telegram.constants import ChatAction

from ai_assistant.modules.telegram.handlers import (
    MPC_AUDIO_PREVIOUS,
    MPC_AUDIO_NEXT,
    MPC_AUDIO_RU,
    MPC_SUBTITLE_NEXT,
    MPC_SUBTITLE_RU,
    PLAYER_NEXT,
    PLAYER_OUTPUT_TOGGLE,
    PLAYER_PLAY_PAUSE,
    PLAYER_PREVIOUS,
    SETTINGS_HOME,
    TelegramHandlers,
)
from ai_assistant.core.models import SettingChoiceOption, SettingDefinition, TerminalCommandResult


class FakeAssistantService:
    def __init__(self) -> None:
        self.process_calls: list[tuple[int, str]] = []
        self.cleared_users: list[int] = []

    async def process_text(self, user_id: int, text: str):
        self.process_calls.append((user_id, text))
        return SimpleNamespace(user_id=user_id, text=f"processed: {text}")

    async def clear_context(self, user_id: int) -> None:
        self.cleared_users.append(user_id)


class FakeMessage:
    def __init__(self, text: str = "") -> None:
        self.text = text
        self.reply_to_message = None
        self.replies: list[str] = []
        self.documents: list[dict[str, object]] = []
        self.reply_markup = None
        self.reply_kwargs: list[dict[str, object]] = []

    async def reply_text(self, text: str, reply_markup=None, **kwargs) -> None:
        self.replies.append(text)
        self.reply_markup = reply_markup
        self.reply_kwargs.append(kwargs)

    async def reply_document(self, document, caption: str | None = None, **kwargs) -> None:
        filename = str(getattr(document, "filename", "")).strip() or None
        self.documents.append(
            {
                "document": document,
                "filename": filename,
                "caption": caption,
                "kwargs": kwargs,
            }
        )


class FakeUser:
    def __init__(
        self,
        user_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> None:
        self.id = user_id
        self.username = username
        self.first_name = first_name
        self.last_name = last_name


class FakeChat:
    def __init__(self, chat_id: int) -> None:
        self.id = chat_id


class FakeUpdate:
    def __init__(self, user_id: int = 1, text: str = "") -> None:
        message = FakeMessage(text=text)
        self.effective_user = FakeUser(user_id)
        self.effective_chat = FakeChat(chat_id=user_id)
        self.effective_message = message
        self.message = message
        self.callback_query = None


class FakeCallbackQuery:
    def __init__(self, data: str, message: FakeMessage) -> None:
        self.data = data
        self.message = message
        self.answers: list[tuple[str | None, bool]] = []
        self.edits: list[tuple[str, object | None]] = []

    async def answer(self, text: str | None = None, show_alert: bool = False) -> None:
        self.answers.append((text, show_alert))

    async def edit_message_text(self, text: str, reply_markup=None, **kwargs) -> None:
        del kwargs
        self.edits.append((text, reply_markup))
        self.message.replies.append(text)
        self.message.reply_markup = reply_markup


class FakeMediaController:
    def __init__(self) -> None:
        self.actions: list[str] = []

    def play_pause(self) -> None:
        self.actions.append("play_pause")

    def previous_track(self) -> None:
        self.actions.append("previous")

    def next_track(self) -> None:
        self.actions.append("next")


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
    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled
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


class FakeBot:
    def __init__(self) -> None:
        self.actions: list[tuple[int, str]] = []

    async def send_chat_action(self, chat_id: int, action: str) -> None:
        self.actions.append((chat_id, action))


class FakeTerminalExecutor:
    def __init__(self, shell_name: str = "powershell") -> None:
        self.shell_name = shell_name
        self.commands: list[tuple[int, str]] = []
        self.active_sessions: set[int] = set()

    def describe_shell(self) -> str:
        return self.shell_name

    async def start_session(self, session_id: int) -> None:
        self.active_sessions.add(session_id)

    async def close_session(self, session_id: int) -> None:
        self.active_sessions.discard(session_id)

    def is_session_active(self, session_id: int) -> bool:
        return session_id in self.active_sessions

    async def run_command(self, session_id: int, command: str) -> TerminalCommandResult:
        self.commands.append((session_id, command))
        return TerminalCommandResult(
            shell=self.shell_name,
            command=command,
            exit_code=0,
            stdout=f"ran: {command}",
            stderr="",
        )


class FakeInteractiveTerminalExecutor(FakeTerminalExecutor):
    async def run_command(self, session_id: int, command: str) -> TerminalCommandResult:
        self.commands.append((session_id, command))
        return TerminalCommandResult(
            shell=self.shell_name,
            command=command,
            exit_code=None,
            stdout="password:",
            stderr="",
            running=True,
        )


class FakeUserSettingsStore:
    def __init__(self) -> None:
        self._data: dict[int, dict[str, str]] = {}
        self._definitions: list[SettingDefinition] = [
            SettingDefinition(
                key="language",
                value_type="choice",
                section="Assistant",
                title="Language",
                description="Preferred language.",
                is_shown_in_ui=True,
            ),
            SettingDefinition(
                key="tts",
                value_type="bool",
                section="Assistant",
                title="Voice replies",
                description="Toggle TTS replies.",
                is_shown_in_ui=True,
            ),
            SettingDefinition(
                key="signature",
                value_type="text",
                section="Assistant",
                title="Signature",
                description="Optional signature.",
                is_shown_in_ui=True,
            ),
            SettingDefinition(
                key="hidden_internal",
                value_type="text",
                section="Internal",
                title="Hidden",
                description="Should not be shown in UI.",
                is_shown_in_ui=False,
            ),
        ]
        self._choice_options: dict[str, list[SettingChoiceOption]] = {
            "language": [
                SettingChoiceOption(
                    setting_id="language",
                    name="ru",
                    description="Russian",
                ),
                SettingChoiceOption(
                    setting_id="language",
                    name="en",
                    description="English",
                ),
            ]
        }

    async def set_setting(self, user_id: int, key: str, value: str) -> None:
        if user_id not in self._data:
            self._data[user_id] = {}
        self._data[user_id][key] = value

    async def get_setting(self, user_id: int, key: str) -> str | None:
        return self._data.get(user_id, {}).get(key)

    async def get_all_settings(self, user_id: int) -> dict[str, str]:
        return dict(self._data.get(user_id, {}))

    async def get_setting_definitions(self, locale: str | None = None) -> list[SettingDefinition]:
        del locale
        return list(self._definitions)

    async def get_setting_choice_options(
        self,
        setting_id: str,
        locale: str | None = None,
    ) -> list[SettingChoiceOption]:
        del locale
        return list(self._choice_options.get(setting_id, []))


class FakePermissionChecker:
    def __init__(self, allowed: set[tuple[int, str, str]] | None = None) -> None:
        self.allowed = allowed or set()
        self.calls: list[tuple[int, str, str]] = []
        self.user_permission_updates: list[tuple[int, str, str, bool]] = []
        self.roles_created: list[str] = []
        self.role_assignments: list[tuple[int, str]] = []
        self.role_grants: list[tuple[str, str, str]] = []
        self.role_revokes: list[tuple[str, str, str]] = []
        self.user_roles_response: dict[int, list[str]] = {}
        self.user_permissions_response: dict[int, dict[str, list[dict[str, object]]]] = {}

    async def has_permission(self, user_id: int, permission_type: str, name: str) -> bool:
        key = (user_id, permission_type, name)
        self.calls.append(key)
        return key in self.allowed

    async def set_user_permission(
        self,
        user_id: int,
        permission_type: str,
        name: str,
        is_active: bool,
    ) -> None:
        self.user_permission_updates.append((user_id, permission_type, name, is_active))

    async def create_role(self, role_name: str) -> None:
        self.roles_created.append(role_name)

    async def assign_role(self, user_id: int, role_name: str) -> None:
        self.role_assignments.append((user_id, role_name))

    async def grant_role_permission(self, role_name: str, permission_type: str, name: str) -> None:
        self.role_grants.append((role_name, permission_type, name))

    async def revoke_role_permission(self, role_name: str, permission_type: str, name: str) -> None:
        self.role_revokes.append((role_name, permission_type, name))

    async def get_user_roles(self, user_id: int) -> list[str]:
        return list(self.user_roles_response.get(user_id, []))

    async def get_user_permission_report(
        self,
        user_id: int,
    ) -> dict[str, list[dict[str, object]]]:
        return dict(
            self.user_permissions_response.get(
                user_id,
                {"user_overrides": [], "role_permissions": [], "effective": []},
            )
        )


