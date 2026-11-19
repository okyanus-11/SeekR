"""Safe Windows window-management helpers exposed through explicit commands."""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

from core.config_manager import ConfigManager
from core.database import Database
from core.models import SearchResult
from core.search_engine import SearchProvider
from core.logging_setup import get_logger

log = get_logger(__name__)
SUPPORTED = os.name == "nt"
MONITOR_DEFAULTTONEAREST = 2
SW_MINIMIZE = 6
WM_CLOSE = 0x0010
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
HWND_TOP = 0
PROTECTED_PROCESS_NAMES = {
    "explorer.exe", "dwm.exe", "winlogon.exe", "csrss.exe",
    "sihost.exe", "startmenuexperiencehost.exe", "searchhost.exe",
    "shellexperiencehost.exe", "applicationframehost.exe",
}


class RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                ("right", wintypes.LONG), ("bottom", wintypes.LONG)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", RECT),
                ("rcWork", RECT), ("dwFlags", wintypes.DWORD)]


def _user32():
    if not SUPPORTED:
        raise OSError("Windows API is unavailable")
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.MonitorFromWindow.restype = wintypes.HANDLE
    user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFO)]
    user32.GetMonitorInfoW.restype = wintypes.BOOL
    user32.SetWindowPos.argtypes = [
        wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, ctypes.c_int, wintypes.UINT,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL
    user32.EnumWindows.argtypes = [ctypes.c_void_p, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.PostMessageW.restype = wintypes.BOOL
    return user32


def tile_window(hwnd: int, side: str) -> tuple[bool, str]:
    if not SUPPORTED:
        return False, "Window tiling is only supported on Windows"
    if side not in {"left", "right"}:
        return False, "Choose left or right"
    try:
        user32 = _user32()
        target = int(hwnd or 0)
        if not target or not user32.IsWindow(target):
            return False, "That window is no longer available"
        monitor = user32.MonitorFromWindow(target, MONITOR_DEFAULTTONEAREST)
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if not monitor or not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return False, "Could not determine that monitor's work area"
        work = info.rcWork
        width = work.right - work.left
        height = work.bottom - work.top
        if width < 2 or height < 2:
            return False, "That monitor has an invalid work area"
        left_width = width // 2
        x = work.left if side == "left" else work.left + left_width
        w = left_width if side == "left" else width - left_width
        ok = user32.SetWindowPos(
            target, HWND_TOP, x, work.top, w, height,
            SWP_NOZORDER | SWP_NOACTIVATE,
        )
        return (True, f"Window tiled {side}") if ok else (False, "Windows rejected the tile request")
    except Exception as exc:
        log.warning("Window tiling failed: %s", exc)
        return False, f"Could not tile window: {exc}"


def close_window(hwnd: int) -> tuple[bool, str]:
    if not SUPPORTED:
        return False, "Window closing is only supported on Windows"
    try:
        user32 = _user32()
        target = int(hwnd or 0)
        if not target or not user32.IsWindow(target):
            return False, "That window is no longer available"
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(target, ctypes.byref(pid))
        if pid.value == os.getpid():
            return False, "SeekR's own windows are protected"
        try:
            import psutil
            process_name = psutil.Process(pid.value).name().lower()
        except Exception:
            return False, "Could not verify the target process; close request was blocked"
        if process_name in PROTECTED_PROCESS_NAMES:
            return False, "Windows shell and system windows are protected"
        if not user32.PostMessageW(target, WM_CLOSE, 0, 0):
            return False, "Windows rejected the close request"
        return True, "Close request sent; the application may ask you to save changes"
    except Exception as exc:
        log.warning("Window close request failed: %s", exc)
        return False, f"Could not close window: {exc}"


def minimize_all_windows() -> tuple[bool, str, int]:
    """Minimize visible app windows, excluding SeekR and known Windows shell processes."""
    if not SUPPORTED:
        return False, "Minimize all is only supported on Windows", 0
    try:
        import psutil

        user32 = _user32()
        protected = PROTECTED_PROCESS_NAMES
        own_pid = os.getpid()
        count = 0

        def visit(hwnd, _lparam):
            nonlocal count
            try:
                if not user32.IsWindowVisible(hwnd):
                    return True
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value == own_pid:
                    return True
                try:
                    process = psutil.Process(pid.value)
                    name = process.name().lower()
                except (psutil.Error, OSError):
                    return True
                if name in protected:
                    return True
                user32.ShowWindow(hwnd, SW_MINIMIZE)
                count += 1
            except Exception:
                log.debug("Skipping a window that could not be minimized", exc_info=True)
            return True

        callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(visit)
        user32.EnumWindows(callback, 0)
        return True, f"Minimized {count} application windows", count
    except Exception as exc:
        log.warning("Minimize all failed: %s", exc)
        return False, f"Could not minimize windows: {exc}", 0


class WindowManagerProvider(SearchProvider):
    """Explicit wm: commands for system-wide window management."""

    id = "window_manager"
    title = "Window management"
    keyword = "wm"
    weight = 0.9
    auto = False

    def search(self, query: str, limit: int) -> list[SearchResult]:
        text = (query or "").strip().lower()
        if not SUPPORTED:
            return [self.make_result(
                title="Window management is Windows-only",
                subtitle="Tiling and minimize-all commands require Windows 10 or 11",
                category="Window management", score=1.0, icon_glyph="▣",
            )]
        if not text or "minimize" in text or "all" in text:
            return [self.make_result(
                title="Minimize all application windows",
                subtitle="Minimizes visible app windows; SeekR and Windows shell windows are protected",
                category="Window management", score=0.95,
                primary=self._minimize_all, icon_glyph="▣",
            )]
        return [self.make_result(
            title="Window management",
            subtitle="Try wm: minimize all, or use win: to select a window and tile it left/right",
            category="Window management", score=0.8,
            icon_glyph="▣",
        )]

    def _minimize_all(self) -> None:
        ok, message, _count = minimize_all_windows()
        self.hooks.notify(message, "info" if ok else "error")

    def empty_help(self) -> SearchResult | None:
        return self.make_result(
            title="Window management",
            subtitle="Use wm: minimize all. Search win: for per-window tiling and switching.",
            category="Window management", score=1.0,
            primary=lambda: self.hooks.fill_query("wm: minimize all"),
            icon_glyph="▣",
        )


__all__ = [
    "SUPPORTED", "PROTECTED_PROCESS_NAMES", "tile_window", "close_window", "minimize_all_windows",
    "WindowManagerProvider",
]
