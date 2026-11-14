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


def split_args(text: str) -> list[str]:
    """Split a command line into arguments without invoking a shell."""
    if not text or not text.strip():
        return []
    try:
        return shlex.split(text, posix=(os.name != "nt"))
    except ValueError:
        return text.split()


def open_path_platform(path: str | os.PathLike[str]) -> tuple[bool, str]:
    """Open a file or folder with the OS default handler."""
    target = str(path)
    if not target:
        return False, "Nothing to open"
    try:
        if os.name == "nt":
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


def reveal_path_platform(path: str | os.PathLike[str]) -> tuple[bool, str]:
    """Show a file in the OS file manager."""
    target = Path(path)
    try:
        if os.name == "nt":
            if target.is_file():
                subprocess.Popen(["explorer", f"/select,{target}"])
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
    "run_detached",
    "which",
    "is_windows",
    "hidden_process_flags",
]
