from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True, frozen=True)
class UserMessage:
    user_id: int
    text: str
    timestamp: datetime = field(default_factory=_utc_now)


@dataclass(slots=True, frozen=True)
class AssistantReply:
    user_id: int
    text: str
    timestamp: datetime = field(default_factory=_utc_now)


@dataclass(slots=True, frozen=True)
class ConversationMessage:
    user_id: int
    role: Literal["user", "assistant"]
    text: str
    timestamp: datetime = field(default_factory=_utc_now)


@dataclass(slots=True, frozen=True)
class TerminalCommandResult:
    shell: str
    command: str
    exit_code: int | None
    stdout: str
    stderr: str
    running: bool = False
    timed_out: bool = False
    error: str | None = None


@dataclass(slots=True, frozen=True)
class SettingChoiceOption:
    setting_id: str
    name: str
    display_name: str | None = None
    description: str = ""
    permission_type: str | None = None
    permission_name: str | None = None


@dataclass(slots=True, frozen=True)
class SettingDefinition:
    key: str
    value_type: Literal["text", "bool", "choice"]
    section: str
    title: str
    description: str = ""
    is_shown_in_ui: bool = True
    read_permission_type: str | None = None
    read_permission_name: str | None = None
    write_permission_type: str | None = None
    write_permission_name: str | None = None
