"""Start with Windows / desktop session integration."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .logging_setup import get_logger
from .version import APP_EXE_NAME, APP_NAME

log = get_logger(__name__)

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = APP_NAME


def _launch_command() -> str:
    """Return the command Windows should run at login."""
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable).resolve()}"'
    executable = Path(sys.executable)
    if os.name == "nt":
        windowless = executable.with_name("pythonw.exe")
        if windowless.exists():
            executable = windowless
    script = Path(sys.argv[0]).resolve()
    return f'"{executable}" "{script}"'


def _linux_desktop_file() -> Path:
    config_home = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return config_home / "autostart" / f"{APP_EXE_NAME.lower()}.desktop"


def is_enabled() -> bool:
    """Return True when SeekR is configured to start at login."""
    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
                value, _ = winreg.QueryValueEx(key, VALUE_NAME)
                return bool(value)
        except FileNotFoundError:
            return False
        except OSError as exc:
            log.warning("Could not read startup registry key: %s", exc)
            return False
    if sys.platform.startswith("linux"):
        return _linux_desktop_file().exists()
    return False


def set_enabled(enabled: bool) -> tuple[bool, str]:
    """Enable or disable launching at login.

    Returns ``(success, message)``; the message explains failures so the
    settings window can show something meaningful.
    """
    if os.name == "nt":
        try:
            import winreg

            with winreg.CreateKeyEx(
                winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
            ) as key:
                if enabled:
                    winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, _launch_command())
                else:
                    try:
                        winreg.DeleteValue(key, VALUE_NAME)
                    except FileNotFoundError:
                        pass
            return True, "SeekR will start with Windows" if enabled else "Startup entry removed"
        except OSError as exc:
            log.error("Could not update startup registry: %s", exc)
            return False, f"Could not update the Windows startup entry: {exc}"

    if sys.platform.startswith("linux"):
        desktop = _linux_desktop_file()
        try:
            if enabled:
                desktop.parent.mkdir(parents=True, exist_ok=True)
                desktop.write_text(
                    "[Desktop Entry]\n"
                    "Type=Application\n"
                    f"Name={APP_NAME}\n"
                    f"Exec={_launch_command()}\n"
                    "X-GNOME-Autostart-enabled=true\n"
                    "Terminal=false\n",
                    encoding="utf-8",
                )
                return True, "SeekR will start with your desktop session"
            if desktop.exists():
                desktop.unlink()
            return True, "Startup entry removed"
        except OSError as exc:
            return False, f"Could not update the autostart entry: {exc}"

    return False, "Startup integration is only supported on Windows and Linux"


def launch_at_login_supported() -> bool:
    return os.name == "nt" or sys.platform.startswith("linux")


__all__ = ["is_enabled", "set_enabled", "launch_at_login_supported", "RUN_KEY", "VALUE_NAME"]
