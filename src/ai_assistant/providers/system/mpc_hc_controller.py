from __future__ import annotations

import ctypes
import re
import sys
from dataclasses import dataclass
from typing import Literal

if sys.platform == "win32":
    from ctypes import wintypes

WM_COMMAND = 0x0111
MF_BYPOSITION = 0x0400
MF_DISABLED = 0x0002
MF_GRAYED = 0x0001
MF_SEPARATOR = 0x0800
MFS_CHECKED = 0x0008
INVALID_MENU_ID = 0xFFFFFFFF
MAX_MENU_TEXT = 512

# Stable MPC-HC command IDs (work in typical Home Cinema builds).
CMD_AUDIO_NEXT = 952
CMD_AUDIO_PREV = 953
CMD_SUB_NEXT = 954
CMD_SUB_PREV = 955

AUDIO_KEYWORDS = ("audio", "sound", "dub", "дорож", "озвуч", "ауди")
SUBTITLE_KEYWORDS = ("subtitle", "subtitles", "subs", "субтит", "сабы")

RU_KEYWORDS = (" russian", "рус", " русск", " ru ", "(ru", "[ru", "rus")
EN_KEYWORDS = (" english", "англ", " англий", " en ", "(en", "[en", "eng")

AUDIO_STREAM_HINTS = ("ac3", "aac", "eac3", "dts", "flac", "truehd", "stereo", "mono", "5.1", "7.1")
SUBTITLE_STREAM_HINTS = ("sub ", " srt", " ass", " ssa", "pgs", "vobsub", "cc", "captions")
FULLSCREEN_KEYWORDS = (
    "fullscreen",
    "full screen",
    "full-screen",
    "во весь экран",
    "полноэкран",
    "полный экран",
)
FULLSCREEN_PATH_HINTS = ("view", "вид")


@dataclass(slots=True)
class _MenuEntry:
    command_id: int
    text: str
    path: tuple[str, ...]
    checked: bool


class MpcHcController:
    def __init__(
        self,
        audio_next_cmd: int = CMD_AUDIO_NEXT,
        audio_prev_cmd: int = CMD_AUDIO_PREV,
        subtitle_next_cmd: int = CMD_SUB_NEXT,
        subtitle_prev_cmd: int = CMD_SUB_PREV,
    ) -> None:
        if sys.platform != "win32":
            raise RuntimeError("MpcHcController is only supported on Windows.")
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._audio_next_cmd = audio_next_cmd
        self._audio_prev_cmd = audio_prev_cmd
        self._subtitle_next_cmd = subtitle_next_cmd
        self._subtitle_prev_cmd = subtitle_prev_cmd

    def audio_next(self) -> bool:
        return self._send_direct(self._audio_next_cmd)

    def audio_previous(self) -> bool:
        return self._send_direct(self._audio_prev_cmd)

    def subtitle_next(self) -> bool:
        return self._send_direct(self._subtitle_next_cmd)

    def subtitle_previous(self) -> bool:
        return self._send_direct(self._subtitle_prev_cmd)

    def audio_set_language(self, language: str) -> bool:
        return self._set_stream_language(stream_type="audio", language=language)

    def subtitle_set_language(self, language: str) -> bool:
        return self._set_stream_language(stream_type="subtitle", language=language)

    def set_fullscreen(self, enabled: bool) -> bool:
        hwnd = self._find_target_window()
        if not hwnd:
            return False

        entries = self._collect_menu_entries(hwnd)
        if not entries:
            return False

        entry = self._find_fullscreen_entry(entries)
        if entry is None:
            return False

        if entry.checked == enabled:
            return True
        return self._send_command(hwnd, entry.command_id)

    @staticmethod
    def _normalize_text(text: str) -> str:
        cleaned = text.replace("&", " ")
        cleaned = cleaned.split("\t", 1)[0]
        cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
        return f" {cleaned} "

    @staticmethod
    def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
        return any(keyword in text for keyword in keywords)

    def _find_target_window(self) -> int | None:
        enum_windows = self._user32.EnumWindows
        is_window_visible = self._user32.IsWindowVisible
        get_class_name = self._user32.GetClassNameW
        get_window_text = self._user32.GetWindowTextW

        exact_matches: list[int] = []
        loose_matches: list[int] = []

        enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def callback(hwnd: int, lparam: int) -> bool:
            del lparam
            if not is_window_visible(hwnd):
                return True

            class_buf = ctypes.create_unicode_buffer(256)
            get_class_name(hwnd, class_buf, len(class_buf))
            class_name = class_buf.value
            class_lower = class_name.lower()

            title_buf = ctypes.create_unicode_buffer(256)
            get_window_text(hwnd, title_buf, len(title_buf))
            title_lower = title_buf.value.lower()

            if class_name == "MediaPlayerClassicW":
                exact_matches.append(hwnd)
            elif (
                "mediaplayerclassic" in class_lower
                or "mpc-hc" in title_lower
                or "media player classic" in title_lower
                or "home cinema" in title_lower
            ):
                loose_matches.append(hwnd)
            return True

        callback_ref = enum_proc(callback)
        enum_windows(callback_ref, 0)

        if exact_matches:
            return exact_matches[0]
        if loose_matches:
            return loose_matches[0]
        return None

    def _send_command(self, hwnd: int, command_id: int) -> bool:
        self._user32.SendMessageW(hwnd, WM_COMMAND, command_id, 0)
        return True

    def _send_direct(self, command_id: int) -> bool:
        hwnd = self._find_target_window()
        if not hwnd:
            return False
        return self._send_command(hwnd, command_id)

    def _get_menu_text(self, menu: int, index: int) -> str:
        buf = ctypes.create_unicode_buffer(MAX_MENU_TEXT)
        self._user32.GetMenuStringW(menu, index, buf, len(buf), MF_BYPOSITION)
        return buf.value

    def _collect_menu_entries(self, hwnd: int) -> list[_MenuEntry]:
        root_menu = self._user32.GetMenu(hwnd)
        if not root_menu:
            return []

        get_menu_item_count = self._user32.GetMenuItemCount
        get_sub_menu = self._user32.GetSubMenu
        get_menu_item_id = self._user32.GetMenuItemID
        get_menu_state = self._user32.GetMenuState

        entries: list[_MenuEntry] = []

        def walk(menu: int, path: tuple[str, ...]) -> None:
            count = get_menu_item_count(menu)
            if count <= 0:
                return

            for i in range(count):
                state = get_menu_state(menu, i, MF_BYPOSITION)
                if state == INVALID_MENU_ID:
                    continue
                if state & MF_SEPARATOR:
                    continue

                text = self._get_menu_text(menu, i)
                next_path = path + ((text,) if text else ())
                sub_menu = get_sub_menu(menu, i)
                if sub_menu:
                    walk(sub_menu, next_path)
                    continue

                if state & (MF_DISABLED | MF_GRAYED):
                    continue

                menu_id = get_menu_item_id(menu, i)
                if menu_id == INVALID_MENU_ID:
                    continue

                entries.append(
                    _MenuEntry(
                        command_id=int(menu_id),
                        text=text,
                        path=path,
                        checked=bool(state & MFS_CHECKED),
                    )
                )

        walk(root_menu, ())
        return entries

    def _is_stream_entry(self, entry: _MenuEntry, stream_type: Literal["audio", "subtitle"]) -> bool:
        path_text = self._normalize_text(" ".join((*entry.path, entry.text)))
        item_text = self._normalize_text(entry.text)

        if stream_type == "audio":
            if self._contains_any(path_text, SUBTITLE_KEYWORDS):
                return False
            if self._contains_any(path_text, AUDIO_KEYWORDS):
                return True
            if self._contains_any(item_text, AUDIO_STREAM_HINTS):
                return True
            return False

        if self._contains_any(path_text, AUDIO_KEYWORDS):
            return False
        if self._contains_any(path_text, SUBTITLE_KEYWORDS):
            return True
        if self._contains_any(item_text, SUBTITLE_STREAM_HINTS):
            return True
        return False

    def _is_fullscreen_entry(self, entry: _MenuEntry) -> bool:
        item_text = self._normalize_text(entry.text)
        if not self._contains_any(item_text, FULLSCREEN_KEYWORDS):
            return False

        path_text = self._normalize_text(" ".join(entry.path))
        if not path_text.strip():
            return True
        return self._contains_any(path_text, FULLSCREEN_PATH_HINTS)

    def _find_fullscreen_entry(self, entries: list[_MenuEntry]) -> _MenuEntry | None:
        candidates: list[tuple[int, _MenuEntry]] = []
        for entry in entries:
            if not self._is_fullscreen_entry(entry):
                continue

            path_text = self._normalize_text(" ".join(entry.path))
            score = 0
            if self._contains_any(path_text, FULLSCREEN_PATH_HINTS):
                score += 10
            if entry.checked:
                score += 1
            candidates.append((score, entry))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    def _set_stream_language(self, stream_type: Literal["audio", "subtitle"], language: str) -> bool:
        hwnd = self._find_target_window()
        if not hwnd:
            return False

        normalized_language = language.strip().lower()
        if normalized_language in {"ru", "rus", "russian", "рус", "русский"}:
            language_keywords = RU_KEYWORDS
        elif normalized_language in {"en", "eng", "english", "англ", "английский"}:
            language_keywords = EN_KEYWORDS
        else:
            return False

        entries = self._collect_menu_entries(hwnd)
        if not entries:
            return False

        candidates: list[tuple[int, _MenuEntry]] = []
        for entry in entries:
            if not self._is_stream_entry(entry, stream_type=stream_type):
                continue
            text = self._normalize_text(entry.text)
            if not self._contains_any(text, language_keywords):
                continue

            score = 0
            if entry.checked:
                score += 100
            if self._contains_any(text, RU_KEYWORDS + EN_KEYWORDS):
                score += 5
            candidates.append((score, entry))

        if not candidates:
            return False

        candidates.sort(key=lambda x: x[0], reverse=True)
        return self._send_command(hwnd, candidates[0][1].command_id)
