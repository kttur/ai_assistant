from __future__ import annotations

import ctypes
import sys

KEYEVENTF_KEYUP = 0x0002
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_PLAY_PAUSE = 0xB3


class WindowsMediaController:
    def __init__(self) -> None:
        if sys.platform != "win32":
            raise RuntimeError("WindowsMediaController is only supported on Windows.")
        self._user32 = ctypes.windll.user32

    def _tap(self, vk_code: int) -> None:
        self._user32.keybd_event(vk_code, 0, 0, 0)
        self._user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)

    def play_pause(self) -> None:
        self._tap(VK_MEDIA_PLAY_PAUSE)

    def previous_track(self) -> None:
        self._tap(VK_MEDIA_PREV_TRACK)

    def next_track(self) -> None:
        self._tap(VK_MEDIA_NEXT_TRACK)

