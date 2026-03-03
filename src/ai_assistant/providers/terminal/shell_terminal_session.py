from __future__ import annotations

import asyncio
import uuid

from ai_assistant.providers.terminal.shell_terminal_helpers import (
    build_command_block,
    build_interactive_argv,
    parse_exit_marker,
)
from ai_assistant.providers.terminal.shell_terminal_types import _ResolvedShell, _TerminalSession


async def create_session(resolved_shell: _ResolvedShell) -> _TerminalSession:
    argv = build_interactive_argv(resolved_shell)
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
    session.stdout_task = asyncio.create_task(_pump_stdout(process.stdout, session.stdout_queue))
    session.stderr_task = asyncio.create_task(_pump_stderr(process.stderr, session.stderr_lines))
    return session


async def close_session(session: _TerminalSession | None) -> None:
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


async def warmup_session(
    session: _TerminalSession,
    shell_name: str,
    timeout_seconds: int,
) -> None:
    # Warm up marker parsing and stream pumps before first user command.
    async with session.lock:
        try:
            exit_code, _, _ = await asyncio.wait_for(
                run_command_in_session(session, shell_name, "echo __AIA_READY__"),
                timeout=min(10, timeout_seconds),
            )
        except asyncio.TimeoutError as exc:
            raise RuntimeError("Terminal session initialization timed out.") from exc
        if exit_code not in (None, 0):
            raise RuntimeError(f"Terminal session initialization failed (exit code {exit_code}).")


async def run_command_in_session(
    session: _TerminalSession,
    shell_name: str,
    command: str,
) -> tuple[int | None, str, str]:
    process = session.process
    if not process.stdin:
        raise RuntimeError("Terminal stdin is not available.")

    token = uuid.uuid4().hex
    start_marker = f"__AIA_START_{token}__"
    exit_prefix = f"__AIA_EXIT_{token}_"
    block = build_command_block(shell_name, command, start_marker, exit_prefix)
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

        parsed_exit = parse_exit_marker(stripped, exit_prefix)
        if parsed_exit is not None:
            exit_code = parsed_exit
            break
        stdout_lines.append(line)

    await asyncio.sleep(0.03)
    stderr = "".join(session.stderr_lines[stderr_start:])
    stdout = "\n".join(stdout_lines).rstrip("\n")
    return exit_code, stdout, stderr.rstrip("\n")


async def _pump_stdout(stream: asyncio.StreamReader, queue: asyncio.Queue[str]) -> None:
    while True:
        chunk = await stream.readline()
        if not chunk:
            break
        await queue.put(chunk.decode("utf-8", errors="replace").rstrip("\r\n"))


async def _pump_stderr(stream: asyncio.StreamReader, buffer: list[str]) -> None:
    while True:
        chunk = await stream.readline()
        if not chunk:
            break
        buffer.append(chunk.decode("utf-8", errors="replace"))
        if len(buffer) > 5000:
            del buffer[:2500]
