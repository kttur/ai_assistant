from __future__ import annotations

from ai_assistant.config.settings import Settings
from ai_assistant.core.interfaces import TerminalCommandExecutor
from ai_assistant.providers.terminal.shell_terminal_executor import ShellTerminalExecutor


def build_terminal_executor(settings: Settings) -> TerminalCommandExecutor | None:
    try:
        return ShellTerminalExecutor(
            preferred_shell=settings.terminal_shell,
            timeout_seconds=settings.terminal_timeout_seconds,
        )
    except RuntimeError:
        return None
