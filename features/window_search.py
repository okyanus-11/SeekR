"""Open window search (Windows)."""

from __future__ import annotations

import ctypes
import os
from typing import Any

from core.config_manager import ConfigManager
from core.database import Database
from core.fuzzy import fuzzy_score
from core.logging_setup import get_logger
from core.models import ResultAction, SearchResult
from core.search_engine import SearchProvider

from . import util

log = get_logger(__name__)

SW_RESTORE = 9
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080

SUPPORTED = os.name == "nt"

if os.name == "nt":  # pragma: no cover - Windows only
    from ctypes import wintypes

    _WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
else:  # A distinct type keeps the annotations importable off Windows.
    _WNDENUMPROC = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)


def _user32():
    """Load user32 with pointer-sized signatures (HWND is 64-bit on x64)."""
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.EnumWindows.argtypes = [_WNDENUMPROC, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    get_long = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
    get_long.argtypes = [wintypes.HWND, ctypes.c_int]
    get_long.restype = ctypes.c_ssize_t
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.IsIconic.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.SwitchToThisWindow.argtypes = [wintypes.HWND, wintypes.BOOL]
    user32.SwitchToThisWindow.restype = None
    user32.GetForegroundWindow.restype = wintypes.HWND
    return user32


def list_windows() -> list[dict[str, Any]]:
    """Return visible top-level windows with titles."""
    if not SUPPORTED:
        return []
    try:
        user32 = _user32()
    except OSError as exc:  # pragma: no cover - Windows only
        log.warning("Could not load user32: %s", exc)
        return []

    windows: list[dict[str, Any]] = []

    def _callback(hwnd, _lparam):  # pragma: no cover - native callback
        try:
            if not user32.IsWindowVisible(hwnd):
                return True
            style = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)(hwnd, GWL_EXSTYLE)
            if style & WS_EX_TOOLWINDOW:
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value.strip()
            if not title:
                return True
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            process_name = ""
            try:
                import psutil

                process_name = psutil.Process(pid.value).name()
            except Exception:
                process_name = ""
            windows.append(
                {
                    "hwnd": int(hwnd),
                    "title": title,
                    "pid": int(pid.value),
                    "process": process_name,
                }
            )
        except Exception:
            log.debug("Window enumeration callback failed", exc_info=True)
        return True

    # Keep a reference to the callback for the whole enumeration; freeing it with
    # GlobalFree (as the previous implementation did) was invalid.
    callback = _WNDENUMPROC(_callback)
    try:
        user32.EnumWindows(callback, 0)
    except Exception as exc:  # pragma: no cover
        log.warning("EnumWindows failed: %s", exc)
    return windows


def switch_to_window(hwnd: int) -> tuple[bool, str]:
    """Bring a window to the foreground."""
    if not SUPPORTED:
        return False, "Window switching is only supported on Windows"
    target = int(hwnd or 0)
    if target <= 0:
        return False, "This window is no longer available"
    try:
        user32 = _user32()
        if user32.IsIconic(target):
            user32.ShowWindow(target, SW_RESTORE)
        if util.force_foreground(target):
            return True, "Switched window"
        user32.SwitchToThisWindow(target, True)
        if user32.GetForegroundWindow() == target:
            return True, "Switched window"
        return False, "Windows blocked switching to that window; try clicking it directly"
    except Exception as exc:  # pragma: no cover
        log.warning("Could not switch to window %s: %s", hwnd, exc)
        return False, f"Could not switch to the window: {exc}"


class WindowProvider(SearchProvider):
    """The ``win:`` keyword."""

    id = "windows"
    title = "Open windows"
    keyword = "win"
    weight = 0.9
    auto = False

    def search(self, query: str, limit: int) -> list[SearchResult]:
        if not SUPPORTED:
            return [
                self.make_result(
                    title="Window search is only available on Windows",
                    subtitle="SeekR can list open windows on Windows 10 and 11",
                    category="Window",
                    score=0.9,
                    icon_glyph="▭",
                )
            ]
        windows = list_windows()
        text = (query or "").strip()
        if text:
            scored = []
            for window in windows:
                score = fuzzy_score(text, window["title"], typo_tolerance=True)
                score = max(score, fuzzy_score(text, window.get("process", ""), typo_tolerance=True) * 0.9)
                if score > 0:
                    scored.append((score, window))
            scored.sort(key=lambda pair: pair[0], reverse=True)
            windows = [window for _, window in scored[:limit]]
        else:
            windows = windows[:limit]
        return [self._result(window, 0.9 - index * 0.02) for index, window in enumerate(windows)]

    def _result(self, window: dict, score: float) -> SearchResult:
        return self.make_result(
            title=window.get("title", "Untitled window"),
            subtitle=f"{window.get('process') or 'Unknown process'}  ·  PID {window.get('pid')}",
            category="Window",
            score=score,
            primary=lambda: self._switch(window),
            actions=[
                ResultAction("Copy window title", lambda: self.hooks.copy_text(window.get("title", ""))),
                ResultAction("Open process manager", lambda: self.hooks.open_tools("processes")),
            ],
            copy_text=window.get("title", ""),
            icon_glyph="▭",
            meta={"window": window},
        )

    def _switch(self, window: dict) -> None:
        ok, message = switch_to_window(int(window.get("hwnd", 0)))
        self.hooks.notify(message, "info" if ok else "error")
        if ok:
            self.hooks.hide_launcher()

    def empty_help(self) -> SearchResult | None:
        return self.make_result(
            title="Window search",
            subtitle="Type part of a window title to switch to it",
            category="Window",
            score=1.0,
            icon_glyph="▭",
        )


__all__ = ["list_windows", "switch_to_window", "WindowProvider", "SUPPORTED"]
