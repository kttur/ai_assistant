from __future__ import annotations

import asyncio

from ai_assistant.core.models import TerminalCommandResult
from ai_assistant.providers.terminal.shell_terminal_helpers import (
    build_shell_order,
    has_pty_option,
    is_ssh_command,
    parse_exit_marker,
    resolve_shell,
    split_command_tokens,
)
from ai_assistant.providers.terminal.shell_terminal_interactive import (
    close_interactive_session,
    send_to_interactive,
    start_interactive_ssh,
)
from ai_assistant.providers.terminal.shell_terminal_session import (
    close_session,
    create_session,
    run_command_in_session,
    warmup_session,
)
from ai_assistant.providers.terminal.shell_terminal_types import (
    _InteractiveSession,
    _TerminalSession,
)


class ShellTerminalExecutor:
    def __init__(self, preferred_shell: str = "powershell", timeout_seconds: int = 60) -> None:
        self._timeout_seconds = max(1, int(timeout_seconds))
        shell_order = self._build_shell_order(preferred_shell)
        self._resolved_shell = resolve_shell(shell_order)
        if not self._resolved_shell:
            raise RuntimeError("No supported terminal shell found (powershell/wsl/cmd).")
        self._sessions: dict[int, _TerminalSession] = {}
        self._interactive_sessions: dict[int, _InteractiveSession] = {}

    def describe_shell(self) -> str:
        return self._resolved_shell.name

    def is_session_active(self, session_id: int) -> bool:
        interactive = self._interactive_sessions.get(session_id)
        if interactive and interactive.process.returncode is None:
            return True
        session = self._sessions.get(session_id)
        return bool(session and session.process.returncode is None)

    async def start_session(self, session_id: int) -> None:
        if self.is_session_active(session_id):
            return
        await self._close_interactive_internal(session_id)
        await self._close_session_internal(session_id)
        session = await create_session(self._resolved_shell)
        self._sessions[session_id] = session
        try:
            await warmup_session(
                session=session,
                shell_name=self._resolved_shell.name,
                timeout_seconds=self._timeout_seconds,
            )
        except Exception:
            await self._close_session_internal(session_id)
            raise

    async def close_session(self, session_id: int) -> None:
        await self._close_interactive_internal(session_id)
        await self._close_session_internal(session_id)

    async def run_command(self, session_id: int, command: str) -> TerminalCommandResult:
        command = command.strip()
        if not command:
            return TerminalCommandResult(
                shell=self._resolved_shell.name,
                command=command,
                exit_code=0,
                stdout="",
                stderr="",
            )

        stale_interactive = self._interactive_sessions.get(session_id)
        if stale_interactive and stale_interactive.process.returncode is not None:
            await self._close_interactive_internal(session_id)

        if self._has_running_interactive(session_id):
            return await self._send_to_interactive(session_id, command)
        if self._is_ssh_command(command):
            return await self._start_interactive_ssh(session_id, command)

        if not self.is_session_active(session_id):
            await self.start_session(session_id)
        session = self._sessions[session_id]

        async with session.lock:
            try:
                exit_code, stdout, stderr = await asyncio.wait_for(
                    run_command_in_session(session, self._resolved_shell.name, command),
                    timeout=self._timeout_seconds,
                )
            except asyncio.TimeoutError:
                await self._close_session_internal(session_id)
                return TerminalCommandResult(
                    shell=self._resolved_shell.name,
                    command=command,
                    exit_code=None,
                    stdout="",
                    stderr="",
                    timed_out=True,
                    error=f"Command timed out after {self._timeout_seconds}s",
                )
            except Exception as exc:
                return TerminalCommandResult(
                    shell=self._resolved_shell.name,
                    command=command,
                    exit_code=None,
                    stdout="",
                    stderr="",
                    error=str(exc),
                )

        return TerminalCommandResult(
            shell=self._resolved_shell.name,
            command=command,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
        )

    async def _close_session_internal(self, session_id: int) -> None:
        await close_session(self._sessions.pop(session_id, None))

    async def _close_interactive_internal(self, session_id: int) -> None:
        await close_interactive_session(self._interactive_sessions.pop(session_id, None))

    def _has_running_interactive(self, session_id: int) -> bool:
        interactive = self._interactive_sessions.get(session_id)
        return bool(interactive and interactive.process.returncode is None)

    async def _start_interactive_ssh(
        self, session_id: int, command: str
    ) -> TerminalCommandResult:
        interactive, result = await start_interactive_ssh(
            shell_name=self._resolved_shell.name,
            command=command,
        )
        if interactive:
            self._interactive_sessions[session_id] = interactive
        return result

    async def _send_to_interactive(
        self, session_id: int, command: str
    ) -> TerminalCommandResult:
        interactive = self._interactive_sessions.get(session_id)
        if not interactive:
            return TerminalCommandResult(
                shell=self._resolved_shell.name,
                command=command,
                exit_code=None,
                stdout="",
                stderr="",
                error="Interactive process is not active.",
            )

        result = await send_to_interactive(
            shell_name=self._resolved_shell.name,
            interactive=interactive,
            command=command,
            timeout_seconds=self._timeout_seconds,
        )
        if not result.running:
            await self._close_interactive_internal(session_id)
        return result

    @staticmethod
    def _build_shell_order(preferred_shell: str) -> list[str]:
        return build_shell_order(preferred_shell)

    @staticmethod
    def _parse_exit_marker(line: str, exit_prefix: str) -> int | None:
        return parse_exit_marker(line, exit_prefix)

    @staticmethod
    def _is_ssh_command(command: str) -> bool:
        return is_ssh_command(command)

    @staticmethod
    def _has_pty_option(args: list[str]) -> bool:
        return has_pty_option(args)

    @staticmethod
    def _split_command_tokens(command: str) -> list[str]:
        return split_command_tokens(command)
