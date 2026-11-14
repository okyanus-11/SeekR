"""Small platform and formatting helpers shared by features."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

from core.logging_setup import get_logger

log = get_logger(__name__)


def format_bytes(size: float | int | None) -> str:
    if size is None:
        return "—"
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if abs(value) < 1024.0 or unit == "PB":
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{value:.1f} PB"


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    seconds = int(max(0, seconds))
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    if days:
        return f"{days}d {hours}h {minutes}m"
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def format_ago(timestamp: float | None) -> str:
    if not timestamp:
        return "never"
    import time

    delta = time.time() - float(timestamp)
    if delta < 60:
        return "just now"
    if delta < 3600:
        return f"{int(delta // 60)} min ago"
    if delta < 86400:
        return f"{int(delta // 3600)} h ago"
    if delta < 86400 * 30:
        return f"{int(delta // 86400)} d ago"
    return "a while ago"


def truncate_middle(text: str, length: int = 60) -> str:
    if len(text) <= length:
        return text
    keep = max(1, (length - 1) // 2)
    return f"{text[:keep]}…{text[-keep:]}"


def _split_windows_args(text: str) -> list[str]:
    """Split a Windows command line using the same rules as the CRT.

    ``shlex`` in non-POSIX mode keeps the quote characters in the tokens, so
    custom commands such as ``--title "My Window"`` would receive literal
    quotes. ``CommandLineToArgvW`` is authoritative on Windows; the portable
    fallback below is used everywhere else (and by the tests).
    """
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            shell32 = ctypes.WinDLL("shell32", use_last_error=True)
            argv_func = shell32.CommandLineToArgvW
            argv_func.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
            argv_func.restype = ctypes.POINTER(ctypes.c_wchar_p)
            argc = ctypes.c_int(0)
            argv = argv_func(text, ctypes.byref(argc))
            if argv:
                try:
                    return [argv[index] for index in range(argc.value)]
                finally:
                    ctypes.windll.kernel32.LocalFree(ctypes.cast(argv, ctypes.c_void_p))
        except Exception:
            log.debug("CommandLineToArgvW unavailable; using the portable splitter", exc_info=True)

    arguments: list[str] = []
    current: list[str] = []
    in_quotes = False
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char == "\\":
            backslashes = 0
            while index < length and text[index] == "\\":
                backslashes += 1
                index += 1
            if index < length and text[index] == '"':
                current.append("\\" * (backslashes // 2))
                if backslashes % 2:
                    current.append('"')
                else:
                    in_quotes = not in_quotes
                index += 1
            else:
                current.append("\\" * backslashes)
            continue
        if char == '"':
            in_quotes = not in_quotes
            index += 1
            continue
        if char in " \t" and not in_quotes:
            if current:
                arguments.append("".join(current))
                current = []
            index += 1
            continue
        current.append(char)
        index += 1
    if current:
        arguments.append("".join(current))
    return arguments


def split_args(text: str, windows: bool | None = None) -> list[str]:
    """Split a command line into arguments without invoking a shell."""
    if not text or not text.strip():
        return []
    is_windows = os.name == "nt" if windows is None else windows
    if is_windows:
        return _split_windows_args(text)
    try:
        return shlex.split(text, posix=True)
    except ValueError:
        return text.split()


def _expand_target(path: str | os.PathLike[str]) -> str:
    """Expand ``~`` and environment variables for a user-supplied path."""
    from core.paths import expand_path

    return str(expand_path(path))


def open_path_platform(path: str | os.PathLike[str]) -> tuple[bool, str]:
    """Open a file or folder with the OS default handler."""
    target = _expand_target(path)
    if not target:
        return False, "Nothing to open"
    try:
        if os.name == "nt":
            if not Path(target).exists():
                return False, f"Path does not exist: {target}"
            os.startfile(target)  # type: ignore[attr-defined]
            return True, f"Opened {target}"
        if sys.platform == "darwin":
            subprocess.Popen(["open", target])
            return True, f"Opened {target}"
        if not Path(target).exists():
            return False, f"Path does not exist: {target}"
        launchers = (["xdg-open", target], ["gio", "open", target], ["kde-open5", target])
        for launcher in launchers:
            try:
                subprocess.Popen(
                    launcher,
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                )
                return True, f"Opened {target}"
            except FileNotFoundError:
                continue
        return False, "No file handler found (install xdg-utils or gio)"
    except OSError as exc:
        log.error("Could not open %s: %s", target, exc)
        return False, f"Could not open {target}: {exc}"


def explorer_select_command(target: str | os.PathLike[str]) -> str:
    """Return the Explorer command line that selects *target*.

    Explorer only understands ``/select,"path"`` when the path stays quoted
    as one token, which is why this is built as a single CreateProcess command
    line instead of an argument list.
    """
    path = str(target)
    if '"' in path:
        raise ValueError("A Windows path cannot contain a double quote")
    return f'explorer.exe /select,"{path}"'


def reveal_path_platform(path: str | os.PathLike[str]) -> tuple[bool, str]:
    """Show a file in the OS file manager."""
    target = Path(_expand_target(path))
    try:
        if os.name == "nt":
            if not target.exists():
                return False, f"Path does not exist: {target}"
            if target.is_file():
                subprocess.Popen(explorer_select_command(target))
            else:
                os.startfile(str(target))  # type: ignore[attr-defined]
            return True, "Opened location"
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(target)])
            return True, "Opened location"
        directory = target if target.is_dir() else target.parent
        if not directory.exists():
            return False, f"Folder does not exist: {directory}"
        return open_path_platform(directory)
    except OSError as exc:
        log.error("Could not reveal %s: %s", target, exc)
        return False, f"Could not open the containing folder: {exc}"
    except ValueError as exc:
        return False, str(exc)


def run_detached(args: list[str], cwd: str | None = None) -> tuple[bool, str]:
    """Start a process without waiting and without a shell."""
    if not args:
        return False, "No command given"
    creationflags = 0
    kwargs: dict = {}
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(
            subprocess, "DETACHED_PROCESS", 0
        )
    else:
        kwargs["start_new_session"] = True
    try:
        subprocess.Popen(
            args,
            cwd=str(cwd) if cwd else None,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
            close_fds=True,
            **kwargs,
        )
        return True, f"Started {args[0]}"
    except OSError as exc:
        log.error("Could not start %s: %s", args, exc)
        return False, f"Could not start {args[0]}: {exc}"


def force_foreground(hwnd: int) -> bool:
    """Bring a native window to the foreground, working around Windows' rules.

    ``SetForegroundWindow`` is refused unless the calling process owns the
    foreground or was allowed to change it. Attaching to the foreground
    thread's input queue is the standard fallback and is what launchers use
    to focus their window from a global hotkey.
    """
    if os.name != "nt" or not hwnd:
        return False
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        user32.SetForegroundWindow.restype = wintypes.BOOL
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.BringWindowToTop.argtypes = [wintypes.HWND]
        user32.BringWindowToTop.restype = wintypes.BOOL
        user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
        user32.AttachThreadInput.restype = wintypes.BOOL
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        user32.IsIconic.argtypes = [wintypes.HWND]
        user32.IsIconic.restype = wintypes.BOOL
        user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.ShowWindow.restype = wintypes.BOOL
        kernel32.GetCurrentThreadId.restype = wintypes.DWORD

        target = int(hwnd)
        if user32.IsIconic(target):
            user32.ShowWindow(target, 9)  # SW_RESTORE
        foreground = user32.GetForegroundWindow()
        if foreground == target:
            return True
        foreground_thread = (
            user32.GetWindowThreadProcessId(foreground, None) if foreground else 0
        )
        own_thread = kernel32.GetCurrentThreadId()
        attached = False
        if foreground_thread and foreground_thread != own_thread:
            attached = bool(user32.AttachThreadInput(foreground_thread, own_thread, True))
        try:
            if user32.SetForegroundWindow(target):
                return True
            user32.BringWindowToTop(target)
            return user32.GetForegroundWindow() == target
        finally:
            if attached:
                user32.AttachThreadInput(foreground_thread, own_thread, False)
    except Exception:
        log.debug("Could not force the window to the foreground", exc_info=True)
        return False


def which(program: str) -> str | None:
    import shutil

    return shutil.which(program)


def is_windows() -> bool:
    return os.name == "nt"


def hidden_process_flags() -> int:
    """Creation flags that keep console windows hidden."""
    if os.name == "nt":
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return 0


__all__ = [
    "format_bytes",
    "format_duration",
    "format_ago",
    "truncate_middle",
    "split_args",
    "open_path_platform",
    "reveal_path_platform",
    "explorer_select_command",
    "run_detached",
    "force_foreground",
    "which",
    "is_windows",
    "hidden_process_flags",
]
