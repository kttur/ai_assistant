from __future__ import annotations

import ctypes
import os
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

T = TypeVar("T")


class VoicemeeterOutputController:
    def __init__(
        self,
        strip_index: int,
        bus: str = "A1",
        output_param: str = "",
        remote_dll_path: str = "",
    ) -> None:
        if sys.platform != "win32":
            raise RuntimeError("VoicemeeterOutputController is only supported on Windows.")
        if strip_index < 0:
            raise ValueError("strip_index must be >= 0")

        normalized_bus = bus.strip().upper()
        if normalized_bus not in {"A1", "A2", "A3", "A4", "A5"}:
            raise ValueError("voicemeeter bus must be one of: A1, A2, A3, A4, A5")

        self._param_candidates = self._build_param_candidates(
            strip_index=strip_index,
            bus=normalized_bus,
            output_param=output_param,
        )
        self._active_param_name: str | None = None
        self._last_known_state: bool | None = None
        self._last_write_monotonic: float = 0.0
        self._external_sync_interval_s = 8.0
        self._lock = threading.Lock()
        self._dll = ctypes.WinDLL(str(self._resolve_dll_path(remote_dll_path)))
        self._configure_api()

    def enable_output(self) -> bool:
        with self._lock:
            return self._set_param(1.0)

    def disable_output(self) -> bool:
        with self._lock:
            return self._set_param(0.0)

    def toggle_output(self) -> bool:
        with self._lock:
            current = self._get_current_state_for_toggle()
            return self._set_param(0.0 if current else 1.0)

    def is_output_enabled(self) -> bool:
        with self._lock:
            value = self._get_param()
            enabled = value >= 0.5
            self._last_known_state = enabled
            return enabled

    def _configure_api(self) -> None:
        self._dll.VBVMR_Login.argtypes = []
        self._dll.VBVMR_Login.restype = ctypes.c_long

        self._dll.VBVMR_Logout.argtypes = []
        self._dll.VBVMR_Logout.restype = ctypes.c_long

        self._dll.VBVMR_GetParameterFloat.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_float)]
        self._dll.VBVMR_GetParameterFloat.restype = ctypes.c_long

        self._dll.VBVMR_SetParameterFloat.argtypes = [ctypes.c_char_p, ctypes.c_float]
        self._dll.VBVMR_SetParameterFloat.restype = ctypes.c_long

        self._dll.VBVMR_SetParameters.argtypes = [ctypes.c_char_p]
        self._dll.VBVMR_SetParameters.restype = ctypes.c_long

    def _resolve_dll_path(self, remote_dll_path: str) -> Path:
        if remote_dll_path.strip():
            path = Path(remote_dll_path).expanduser()
            if not path.exists():
                raise RuntimeError(f"Voicemeeter DLL not found: {path}")
            return path

        candidates = [
            Path(os.environ.get("ProgramFiles", "")) / "VB" / "Voicemeeter" / "VoicemeeterRemote64.dll",
            Path(os.environ.get("ProgramFiles(x86)", "")) / "VB" / "Voicemeeter" / "VoicemeeterRemote64.dll",
            Path(os.environ.get("ProgramFiles", "")) / "VB" / "Voicemeeter" / "VoicemeeterRemote.dll",
            Path(os.environ.get("ProgramFiles(x86)", "")) / "VB" / "Voicemeeter" / "VoicemeeterRemote.dll",
        ]

        for path in candidates:
            if path.exists():
                return path
        raise RuntimeError(
            "VoicemeeterRemote DLL not found. Set VOICEMEETER_REMOTE_DLL_PATH in .env."
        )

    def _with_session(self, action: Callable[[], T]) -> T:
        login_result = int(self._dll.VBVMR_Login())
        if login_result != 0:
            raise RuntimeError(
                f"VBVMR_Login failed with code {login_result}. "
                "Make sure Voicemeeter is running and API is accessible."
            )
        try:
            return action()
        finally:
            self._dll.VBVMR_Logout()

    @staticmethod
    def _build_param_candidates(strip_index: int, bus: str, output_param: str) -> list[str]:
        defaults = [
            f"Strip[{strip_index}].{bus}",
            f"Strip({strip_index}).{bus}",
        ]
        if not output_param.strip():
            return defaults

        # Explicit override is treated as strict source of truth.
        # This avoids false-positive writes to a different parameter alias.
        return [output_param.strip()]

    def _set_active_param_if_works(self) -> str:
        if self._active_param_name:
            return self._active_param_name

        for candidate in self._param_candidates:
            result, _ = self._read_param_float(candidate)
            if result >= 0:
                self._active_param_name = candidate
                return candidate

        raise RuntimeError(
            "Could not resolve Voicemeeter output parameter. "
            "Set VOICEMEETER_OUTPUT_PARAM explicitly (example: Strip[5].A1)."
        )

    def _read_param_float(self, param_name: str) -> tuple[int, float]:
        value = ctypes.c_float(0.0)
        result = int(
            self._dll.VBVMR_GetParameterFloat(param_name.encode("utf-8"), ctypes.byref(value))
        )
        return result, float(value.value)

    def _read_param_verified(self, param_name: str) -> float:
        result, value = self._read_param_float(param_name)
        if result < 0:
            raise RuntimeError(
                f"VBVMR_GetParameterFloat failed for {param_name} with code {result}"
            )
        return value

    def _read_with_retry(self, param_name: str, retries: int = 6, delay_s: float = 0.03) -> float:
        last_value = self._read_param_verified(param_name)
        for _ in range(retries):
            time.sleep(delay_s)
            last_value = self._read_param_verified(param_name)
        return last_value

    def _get_param(self) -> float:
        def action() -> float:
            param_name = self._set_active_param_if_works()
            return self._read_param_verified(param_name)

        return self._with_session(action)

    def _get_current_state_for_toggle(self) -> bool:
        # Prefer cached state for stability during normal toggle usage.
        # Voicemeeter readback can lag and cause every-second toggle misses.
        if self._last_known_state is not None and (
            time.monotonic() - self._last_write_monotonic
        ) < self._external_sync_interval_s:
            return self._last_known_state

        # After a longer idle period, resync from live state to catch external changes.
        try:
            current = self._get_param() >= 0.5
            self._last_known_state = current
            return current
        except Exception:
            if self._last_known_state is not None:
                return self._last_known_state
            return False

    def _set_param(self, value: float) -> bool:
        def action() -> None:
            target = 1.0 if value >= 0.5 else 0.0
            preferred = self._active_param_name or self._set_active_param_if_works()
            ordered_params = [preferred] + [
                p for p in self._param_candidates if p != preferred
            ]
            errors: list[str] = []
            write_succeeded = False

            for attempt in range(1, 4):
                for param_name in ordered_params:
                    try:
                        before = self._read_param_verified(param_name)
                    except RuntimeError as exc:
                        errors.append(str(exc))
                        continue

                    result = int(
                        self._dll.VBVMR_SetParameterFloat(
                            param_name.encode("utf-8"), ctypes.c_float(target)
                        )
                    )
                    if result >= 0:
                        write_succeeded = True
                        after_float = self._read_with_retry(param_name)
                        if int(round(after_float)) == int(target):
                            self._active_param_name = param_name
                            self._last_known_state = bool(target)
                            self._last_write_monotonic = time.monotonic()
                            return
                    else:
                        errors.append(
                            f"VBVMR_SetParameterFloat failed for {param_name} with code {result}"
                        )
                        after_float = before

                    script = f"{param_name}={int(target)};"
                    script_result = int(self._dll.VBVMR_SetParameters(script.encode("utf-8")))
                    if script_result < 0:
                        errors.append(
                            f"VBVMR_SetParameters failed for {param_name} with code {script_result}"
                        )
                        continue

                    write_succeeded = True
                    after_script = self._read_with_retry(param_name)
                    if int(round(after_script)) == int(target):
                        self._active_param_name = param_name
                        self._last_known_state = bool(target)
                        self._last_write_monotonic = time.monotonic()
                        return

                    errors.append(
                        f"attempt={attempt} no-change for {param_name} (before={before:.3f}, "
                        f"after_float={after_float:.3f}, after_script={after_script:.3f}, "
                        f"target={target:.0f})"
                    )

                time.sleep(0.05)

            if write_succeeded:
                self._last_known_state = bool(target)
                self._last_write_monotonic = time.monotonic()
                return

            raise RuntimeError(
                "Voicemeeter parameter did not change for any candidate: "
                + ", ".join(ordered_params)
                + ". Details: "
                + " | ".join(errors[-4:])
            )

        self._with_session(action)
        return bool(value >= 0.5)
