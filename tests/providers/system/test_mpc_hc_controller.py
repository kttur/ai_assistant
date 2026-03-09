from ai_assistant.providers.system.mpc_hc_controller import (
    VK_RETURN,
    WM_SYSKEYDOWN,
    WM_SYSKEYUP,
    MpcHcController,
    _MenuEntry,
)


def _controller() -> MpcHcController:
    return object.__new__(MpcHcController)


def test_is_fullscreen_entry_by_keyword() -> None:
    controller = _controller()
    entry = _MenuEntry(
        command_id=1,
        text="Fullscreen\tAlt+Enter",
        path=("View",),
        checked=False,
    )

    assert controller._is_fullscreen_entry(entry) is True


def test_is_fullscreen_entry_by_hotkey_fallback() -> None:
    controller = _controller()
    entry = _MenuEntry(
        command_id=2,
        text="Plein ecran\tAlt+Enter",
        path=("Affichage",),
        checked=False,
    )

    assert controller._is_fullscreen_entry(entry) is True


def test_find_fullscreen_entry_prefers_view_hotkey_candidate() -> None:
    controller = _controller()
    entries = [
        _MenuEntry(command_id=1, text="Fullscreen", path=("Play",), checked=False),
        _MenuEntry(command_id=2, text="Plein ecran\tAlt+Enter", path=("Affichage",), checked=False),
        _MenuEntry(
            command_id=3,
            text="Fullscreen\tAlt+Enter",
            path=("View",),
            checked=False,
        ),
    ]

    best = controller._find_fullscreen_entry(entries)
    assert best is not None
    assert best.command_id == 3


def test_set_fullscreen_uses_hotkey_fallback_when_entry_missing() -> None:
    controller = _controller()
    controller._find_target_window = lambda: 42
    controller._collect_menu_entries = lambda hwnd: [_MenuEntry(1, "Any", ("View",), False)]
    controller._find_fullscreen_entry = lambda entries: None
    controller._send_command = lambda hwnd, command_id: False

    states = iter((False, False, True))
    controller._is_window_fullscreen = lambda hwnd: next(states)
    sent: list[int] = []
    controller._send_alt_enter = lambda hwnd: sent.append(hwnd) or True

    assert controller.set_fullscreen(True) is True
    assert sent == [42]


def test_set_fullscreen_hotkey_fallback_returns_false_when_state_not_changed() -> None:
    controller = _controller()
    controller._find_target_window = lambda: 42
    controller._collect_menu_entries = lambda hwnd: [_MenuEntry(1, "Any", ("View",), False)]
    controller._find_fullscreen_entry = lambda entries: None
    controller._send_command = lambda hwnd, command_id: False

    states = iter((False, False, False))
    controller._is_window_fullscreen = lambda hwnd: next(states)
    controller._send_alt_enter = lambda hwnd: True

    assert controller.set_fullscreen(True) is False


def test_set_fullscreen_uses_hotkey_fallback_when_menu_is_unavailable() -> None:
    controller = _controller()
    controller._find_target_window = lambda: 42
    controller._collect_menu_entries = lambda hwnd: []
    controller._send_command = lambda hwnd, command_id: False

    states = iter((False, False, True))
    controller._is_window_fullscreen = lambda hwnd: next(states)
    sent: list[int] = []
    controller._send_alt_enter = lambda hwnd: sent.append(hwnd) or True

    assert controller.set_fullscreen(True) is True
    assert sent == [42]


class _User32FocusDenied:
    def __init__(self) -> None:
        self.sent_messages: list[tuple[int, int, int, int]] = []

    def ShowWindow(self, hwnd: int, mode: int) -> int:
        del hwnd, mode
        return 1

    def BringWindowToTop(self, hwnd: int) -> int:
        del hwnd
        return 1

    def SetForegroundWindow(self, hwnd: int) -> int:
        del hwnd
        return 0

    def GetForegroundWindow(self) -> int:
        return 777

    def SendMessageW(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        self.sent_messages.append((hwnd, msg, wparam, lparam))
        return 1

    def PostMessageW(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        self.sent_messages.append((hwnd, msg, wparam, lparam))
        return 1

    def keybd_event(self, b_vk: int, b_scan: int, dw_flags: int, dw_extra_info: int) -> None:
        del b_vk, b_scan, dw_flags, dw_extra_info


def test_send_alt_enter_falls_back_to_syskey_messages_when_focus_denied() -> None:
    controller = _controller()
    user32 = _User32FocusDenied()
    controller._user32 = user32

    assert controller._send_alt_enter(42) is True
    assert len(user32.sent_messages) >= 4
    syskey_messages = [item for item in user32.sent_messages if item[1] in {WM_SYSKEYDOWN, WM_SYSKEYUP}]
    assert len(syskey_messages) == 2
    assert syskey_messages[0][1] == WM_SYSKEYDOWN
    assert syskey_messages[0][2] == VK_RETURN
    assert syskey_messages[1][1] == WM_SYSKEYUP
    assert syskey_messages[1][2] == VK_RETURN
