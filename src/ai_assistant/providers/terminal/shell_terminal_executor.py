from __future__ import annotations

import asyncio
import os
import shlex
import shutil
import time
import uuid
from dataclasses import dataclass, field

from ai_assistant.core.models import TerminalCommandResult


@dataclass(slots=True, frozen=True)
class _ResolvedShell:
    name: str
    executable: str


@dataclass(slots=True)
class _TerminalSession:
    process: asyncio.subprocess.Process
    stdout_queue: asyncio.Queue[str]
    stderr_lines: list[str] = field(default_factory=list)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    stdout_task: asyncio.Task | None = None
    stderr_task: asyncio.Task | None = None


@dataclass(slots=True)
class _InteractiveSession:
    command: str
    process: asyncio.subprocess.Process
    stdout_queue: asyncio.Queue[str]
    stderr_queue: asyncio.Queue[str]
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    stdout_task: asyncio.Task | None = None
    stderr_task: asyncio.Task | None = None


class ShellTerminalExecutor:
    def __init__(self, preferred_shell: str = "powershell", timeout_seconds: int = 60) -> None:
        self._timeout_seconds = max(1, int(timeout_seconds))
        shell_order = self._build_shell_order(preferred_shell)
        self._resolved_shell = self._resolve_shell(shell_order)
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
        session = await self._create_session()
        self._sessions[session_id] = session
        try:
            await self._warmup_session(session)
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
                    self._run_command_in_session(session, command),
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

    async def _create_session(self) -> _TerminalSession:
        argv = self._build_interactive_argv(self._resolved_shell)
        process = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        if not process.stdin or not process.stdout or not process.stderr:
            process.kill()
            await process.wait()
            raise RuntimeError("Failed to create terminal session pipes.")

        session = _TerminalSession(
            process=process,
            stdout_queue=asyncio.Queue(),
        )
        session.stdout_task = asyncio.create_task(
            self._pump_stdout(process.stdout, session.stdout_queue)
        )
        session.stderr_task = asyncio.create_task(
            self._pump_stderr(process.stderr, session.stderr_lines)
        )
        return session

    async def _close_session_internal(self, session_id: int) -> None:
        session = self._sessions.pop(session_id, None)
        if not session:
            return

        process = session.process
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=2)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()

        for task in (session.stdout_task, session.stderr_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    async def _close_interactive_internal(self, session_id: int) -> None:
        interactive = self._interactive_sessions.pop(session_id, None)
        if not interactive:
            return

        process = interactive.process
        if process.returncode is None:
            if process.stdin:
                try:
                    process.stdin.write(b"\n")
                    await process.stdin.drain()
                except Exception:
                    pass
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=2)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()

        for task in (interactive.stdout_task, interactive.stderr_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    def _has_running_interactive(self, session_id: int) -> bool:
        interactive = self._interactive_sessions.get(session_id)
        return bool(interactive and interactive.process.returncode is None)

    async def _start_interactive_ssh(
        self, session_id: int, command: str
    ) -> TerminalCommandResult:
        tokens = self._split_command_tokens(command)
        if not tokens:
            return TerminalCommandResult(
                shell=self._resolved_shell.name,
                command=command,
                exit_code=1,
                stdout="",
                stderr="",
                error="Empty ssh command.",
            )

        ssh_executable = shutil.which("ssh") or tokens[0]
        argv = [ssh_executable, *tokens[1:]]
        if not self._has_pty_option(tokens[1:]):
            argv = [ssh_executable, "-tt", *tokens[1:]]

        try:
            process = await asyncio.create_subprocess_exec(
                *argv,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except Exception as exc:
            return TerminalCommandResult(
                shell=self._resolved_shell.name,
                command=command,
                exit_code=None,
                stdout="",
                stderr="",
                error=f"Failed to start ssh: {exc}",
            )

        if not process.stdin or not process.stdout or not process.stderr:
            process.kill()
            await process.wait()
            return TerminalCommandResult(
                shell=self._resolved_shell.name,
                command=command,
                exit_code=None,
                stdout="",
                stderr="",
                error="Failed to create ssh pipes.",
            )

        interactive = _InteractiveSession(
            command=command,
            process=process,
            stdout_queue=asyncio.Queue(),
            stderr_queue=asyncio.Queue(),
        )
        interactive.stdout_task = asyncio.create_task(
            self._pump_stream_chunks(process.stdout, interactive.stdout_queue)
        )
        interactive.stderr_task = asyncio.create_task(
            self._pump_stream_chunks(process.stderr, interactive.stderr_queue)
        )
        self._interactive_sessions[session_id] = interactive

        stdout, stderr = await self._collect_interactive_output(
            interactive,
            idle_timeout=0.5,
            max_wait=2.0,
        )
        running = process.returncode is None
        exit_code = process.returncode
        if not running:
            await self._close_interactive_internal(session_id)

        return TerminalCommandResult(
            shell=self._resolved_shell.name,
            command=command,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            running=running,
        )

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

        async with interactive.lock:
            process = interactive.process
            if process.returncode is not None:
                await self._close_interactive_internal(session_id)
                return TerminalCommandResult(
                    shell=self._resolved_shell.name,
                    command=command,
                    exit_code=process.returncode,
                    stdout="",
                    stderr="",
                    running=False,
                )
            if not process.stdin:
                return TerminalCommandResult(
                    shell=self._resolved_shell.name,
                    command=command,
                    exit_code=None,
                    stdout="",
                    stderr="",
                    error="Interactive stdin is not available.",
                )

            try:
                process.stdin.write((command + "\n").encode("utf-8"))
                await process.stdin.drain()
            except Exception as exc:
                return TerminalCommandResult(
                    shell=self._resolved_shell.name,
                    command=command,
                    exit_code=None,
                    stdout="",
                    stderr="",
                    error=f"Failed to send input: {exc}",
                )

            stdout, stderr = await self._collect_interactive_output(
                interactive,
                idle_timeout=0.5,
                max_wait=max(2.0, self._timeout_seconds),
            )
            running = process.returncode is None
            exit_code = process.returncode
            if not running:
                await self._close_interactive_internal(session_id)

            return TerminalCommandResult(
                shell=self._resolved_shell.name,
                command=command,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                running=running,
            )

    async def _warmup_session(self, session: _TerminalSession) -> None:
        # Execute a trivial command once to ensure marker parsing/session I/O is ready
        # before first user command.
        async with session.lock:
            try:
                exit_code, _, _ = await asyncio.wait_for(
                    self._run_command_in_session(session, "echo __AIA_READY__"),
                    timeout=min(10, self._timeout_seconds),
                )
            except asyncio.TimeoutError as exc:
                raise RuntimeError("Terminal session initialization timed out.") from exc
            if exit_code not in (None, 0):
                raise RuntimeError(f"Terminal session initialization failed (exit code {exit_code}).")

    async def _run_command_in_session(
        self, session: _TerminalSession, command: str
    ) -> tuple[int | None, str, str]:
        process = session.process
        if not process.stdin:
            raise RuntimeError("Terminal stdin is not available.")

        token = uuid.uuid4().hex
        start_marker = f"__AIA_START_{token}__"
        exit_prefix = f"__AIA_EXIT_{token}_"

        block = self._build_command_block(self._resolved_shell.name, command, start_marker, exit_prefix)
        stderr_start = len(session.stderr_lines)

        process.stdin.write(block.encode("utf-8"))
        await process.stdin.drain()

        stdout_lines: list[str] = []
        started = False
        exit_code: int | None = None
        while True:
            line = await session.stdout_queue.get()
            stripped = line.strip()
            if not started:
                if start_marker in stripped:
                    started = True
                continue

            parsed_exit = self._parse_exit_marker(stripped, exit_prefix)
            if parsed_exit is not None:
                exit_code = parsed_exit
                break
            stdout_lines.append(line)

        await asyncio.sleep(0.03)
        stderr = "".join(session.stderr_lines[stderr_start:])
        stdout = "\n".join(stdout_lines).rstrip("\n")
        return exit_code, stdout, stderr.rstrip("\n")

    @staticmethod
    async def _pump_stdout(stream: asyncio.StreamReader, queue: asyncio.Queue[str]) -> None:
        while True:
            chunk = await stream.readline()
            if not chunk:
                break
            await queue.put(chunk.decode("utf-8", errors="replace").rstrip("\r\n"))

    @staticmethod
    async def _pump_stderr(stream: asyncio.StreamReader, buffer: list[str]) -> None:
        while True:
            chunk = await stream.readline()
            if not chunk:
                break
            buffer.append(chunk.decode("utf-8", errors="replace"))
            if len(buffer) > 5000:
                del buffer[:2500]

    @staticmethod
    async def _pump_stream_chunks(stream: asyncio.StreamReader, queue: asyncio.Queue[str]) -> None:
        while True:
            chunk = await stream.read(1024)
            if not chunk:
                break
            await queue.put(chunk.decode("utf-8", errors="replace"))

    async def _collect_interactive_output(
        self,
        interactive: _InteractiveSession,
        idle_timeout: float,
        max_wait: float,
    ) -> tuple[str, str]:
        stdout_parts: list[str] = []
        stderr_parts: list[str] = []

        start = time.monotonic()
        last_activity = start
        while True:
            now = time.monotonic()
            if now - start >= max_wait:
                break

            got_data = False
            while not interactive.stdout_queue.empty():
                stdout_parts.append(interactive.stdout_queue.get_nowait())
                got_data = True
            while not interactive.stderr_queue.empty():
                stderr_parts.append(interactive.stderr_queue.get_nowait())
                got_data = True

            if got_data:
                last_activity = now
            elif now - last_activity >= idle_timeout:
                break

            if interactive.process.returncode is not None:
                if interactive.stdout_queue.empty() and interactive.stderr_queue.empty():
                    break

            await asyncio.sleep(0.05)

        return "".join(stdout_parts).rstrip("\n"), "".join(stderr_parts).rstrip("\n")

    @staticmethod
    def _build_shell_order(preferred_shell: str) -> list[str]:
        preferred = preferred_shell.strip().lower() or "powershell"
        if preferred == "auto":
            return ["powershell", "wsl", "cmd"]
        if preferred == "powershell":
            return ["powershell", "wsl", "cmd"]
        if preferred == "wsl":
            return ["wsl", "cmd", "powershell"]
        if preferred == "cmd":
            return ["cmd", "powershell", "wsl"]
        return ["powershell", "wsl", "cmd"]

    @staticmethod
    def _resolve_shell(shell_order: list[str]) -> _ResolvedShell | None:
        for shell_name in shell_order:
            if shell_name == "powershell":
                for candidate in ("powershell", "pwsh"):
                    path = shutil.which(candidate)
                    if path:
                        return _ResolvedShell(name="powershell", executable=path)
            elif shell_name == "wsl":
                path = shutil.which("wsl")
                if path:
                    return _ResolvedShell(name="wsl", executable=path)
            elif shell_name == "cmd":
                comspec = os.environ.get("ComSpec", "cmd.exe")
                path = shutil.which(comspec) or shutil.which("cmd.exe") or shutil.which("cmd")
                if path:
                    return _ResolvedShell(name="cmd", executable=path)
        return None

    @staticmethod
    def _build_interactive_argv(shell: _ResolvedShell) -> list[str]:
        if shell.name == "powershell":
            return [
                shell.executable,
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                "-",
            ]
        if shell.name == "wsl":
            return [shell.executable, "bash", "-s"]
        return [shell.executable, "/Q", "/K"]

    @staticmethod
    def _build_command_block(shell_name: str, command: str, start_marker: str, exit_prefix: str) -> str:
        if shell_name == "powershell":
            return (
                f'Write-Output "{start_marker}"\n'
                f"{command}\n"
                "$__aia_code = if ($LASTEXITCODE -ne $null) { [int]$LASTEXITCODE } elseif ($?) { 0 } else { 1 }\n"
                f'Write-Output ("{exit_prefix}" + $__aia_code + "__")\n'
            )
        if shell_name == "wsl":
            return (
                f'printf "{start_marker}\\n"\n'
                f"{command}\n"
                f'printf "{exit_prefix}%s__\\n" "$?"\n'
            )
        return (
            f"echo {start_marker}\r\n"
            f"{command}\r\n"
            f"echo {exit_prefix}%ERRORLEVEL%__\r\n"
        )

    @staticmethod
    def _parse_exit_marker(line: str, exit_prefix: str) -> int | None:
        marker_start = line.find(exit_prefix)
        if marker_start < 0:
            return None
        payload = line[marker_start + len(exit_prefix) :]
        marker_end = payload.find("__")
        if marker_end < 0:
            return None
        code_part = payload[:marker_end].strip()
        if code_part == "":
            return 0
        try:
            return int(code_part)
        except ValueError:
            return None

    @staticmethod
    def _is_ssh_command(command: str) -> bool:
        tokens = ShellTerminalExecutor._split_command_tokens(command)
        if not tokens:
            return False
        return tokens[0].lower() == "ssh"

    @staticmethod
    def _has_pty_option(args: list[str]) -> bool:
        for arg in args:
            if arg in {"-t", "-tt", "-T"}:
                return True
            if arg.startswith("-") and "t" in arg[1:].lower():
                return True
        return False

    @staticmethod
    def _split_command_tokens(command: str) -> list[str]:
        try:
            return shlex.split(command, posix=False)
        except ValueError:
            return command.strip().split()
