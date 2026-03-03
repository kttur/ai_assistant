from __future__ import annotations

import os
import shlex
import shutil

from ai_assistant.providers.terminal.shell_terminal_types import _ResolvedShell


def build_shell_order(preferred_shell: str) -> list[str]:
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


def resolve_shell(shell_order: list[str]) -> _ResolvedShell | None:
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


def build_interactive_argv(shell: _ResolvedShell) -> list[str]:
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


def build_command_block(shell_name: str, command: str, start_marker: str, exit_prefix: str) -> str:
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


def parse_exit_marker(line: str, exit_prefix: str) -> int | None:
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


def is_ssh_command(command: str) -> bool:
    tokens = split_command_tokens(command)
    if not tokens:
        return False
    return tokens[0].lower() == "ssh"


def has_pty_option(args: list[str]) -> bool:
    for arg in args:
        if arg in {"-t", "-tt", "-T"}:
            return True
        if arg.startswith("-") and "t" in arg[1:].lower():
            return True
    return False


def split_command_tokens(command: str) -> list[str]:
    try:
        return shlex.split(command, posix=False)
    except ValueError:
        return command.strip().split()
