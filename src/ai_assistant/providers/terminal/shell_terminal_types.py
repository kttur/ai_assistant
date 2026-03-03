from __future__ import annotations

import asyncio
from dataclasses import dataclass, field


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
