from ai_assistant.providers.terminal.shell_terminal_executor import ShellTerminalExecutor


def test_shell_order_default_and_variants() -> None:
    assert ShellTerminalExecutor._build_shell_order("powershell") == [
        "powershell",
        "wsl",
        "cmd",
    ]
    assert ShellTerminalExecutor._build_shell_order("wsl") == ["wsl", "cmd", "powershell"]
    assert ShellTerminalExecutor._build_shell_order("cmd") == ["cmd", "powershell", "wsl"]
    assert ShellTerminalExecutor._build_shell_order("auto") == ["powershell", "wsl", "cmd"]


def test_parse_exit_marker_empty_defaults_to_zero() -> None:
    prefix = "__AIA_EXIT_token_"
    assert ShellTerminalExecutor._parse_exit_marker("__AIA_EXIT_token___", prefix) == 0
    assert ShellTerminalExecutor._parse_exit_marker("__AIA_EXIT_token_1__", prefix) == 1


def test_parse_exit_marker_with_leading_noise() -> None:
    prefix = "__AIA_EXIT_token_"
    line = "PS C:\\> __AIA_EXIT_token_0__"
    assert ShellTerminalExecutor._parse_exit_marker(line, prefix) == 0


def test_is_ssh_command() -> None:
    assert ShellTerminalExecutor._is_ssh_command("ssh deu")
    assert ShellTerminalExecutor._is_ssh_command("ssh deu \"ls\"")
    assert not ShellTerminalExecutor._is_ssh_command("python")
    assert not ShellTerminalExecutor._is_ssh_command("ls")


def test_has_pty_option() -> None:
    assert ShellTerminalExecutor._has_pty_option(["-tt", "deu"])
    assert ShellTerminalExecutor._has_pty_option(["-t", "deu"])
    assert ShellTerminalExecutor._has_pty_option(["-T", "deu"])
    assert not ShellTerminalExecutor._has_pty_option(["deu"])
