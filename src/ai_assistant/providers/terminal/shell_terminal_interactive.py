from __future__ import annotations

import asyncio
import shutil
import time

from ai_assistant.core.models import TerminalCommandResult
from ai_assistant.providers.terminal.shell_terminal_helpers import has_pty_option, split_command_tokens
from ai_assistant.providers.terminal.shell_terminal_types import _InteractiveSession


async def close_interactive_session(interactive: _InteractiveSession | None) -> None:
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


async def start_interactive_ssh(
    shell_name: str,
    command: str,
) -> tuple[_InteractiveSession | None, TerminalCommandResult]:
    tokens = split_command_tokens(command)
    if not tokens:
        return None, TerminalCommandResult(
            shell=shell_name,
            command=command,
            exit_code=1,
            stdout="",
            stderr="",
            error="Empty ssh command.",
        )

    ssh_executable = shutil.which("ssh") or tokens[0]
    argv = [ssh_executable, *tokens[1:]]
    if not has_pty_option(tokens[1:]):
        argv = [ssh_executable, "-tt", *tokens[1:]]

    try:
        process = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except Exception as exc:
        return None, TerminalCommandResult(
            shell=shell_name,
            command=command,
            exit_code=None,
            stdout="",
            stderr="",
            error=f"Failed to start ssh: {exc}",
        )

    if not process.stdin or not process.stdout or not process.stderr:
        process.kill()
        await process.wait()
        return None, TerminalCommandResult(
            shell=shell_name,
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
        _pump_stream_chunks(process.stdout, interactive.stdout_queue)
    )
    interactive.stderr_task = asyncio.create_task(
        _pump_stream_chunks(process.stderr, interactive.stderr_queue)
    )

    stdout, stderr = await collect_interactive_output(
        interactive,
        idle_timeout=0.5,
        max_wait=2.0,
    )
    running = process.returncode is None
    exit_code = process.returncode
    if not running:
        await close_interactive_session(interactive)
        interactive = None

    return interactive, TerminalCommandResult(
        shell=shell_name,
        command=command,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        running=running,
    )


async def send_to_interactive(
    shell_name: str,
    interactive: _InteractiveSession,
    command: str,
    timeout_seconds: int,
) -> TerminalCommandResult:
    async with interactive.lock:
        process = interactive.process
        if process.returncode is not None:
            return TerminalCommandResult(
                shell=shell_name,
                command=command,
                exit_code=process.returncode,
                stdout="",
                stderr="",
                running=False,
            )
        if not process.stdin:
            return TerminalCommandResult(
                shell=shell_name,
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
                shell=shell_name,
                command=command,
                exit_code=None,
                stdout="",
                stderr="",
                error=f"Failed to send input: {exc}",
            )

        stdout, stderr = await collect_interactive_output(
            interactive,
            idle_timeout=0.5,
            max_wait=max(2.0, timeout_seconds),
        )
        running = process.returncode is None
        exit_code = process.returncode
        return TerminalCommandResult(
            shell=shell_name,
            command=command,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            running=running,
        )


async def collect_interactive_output(
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


async def _pump_stream_chunks(stream: asyncio.StreamReader, queue: asyncio.Queue[str]) -> None:
    while True:
        chunk = await stream.read(1024)
        if not chunk:
            break
        await queue.put(chunk.decode("utf-8", errors="replace"))
