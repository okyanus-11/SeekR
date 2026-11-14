"""Filesystem locations used by SeekR.

The application never writes inside its own installation directory; all user
state lives in a per-user data directory so it survives upgrades.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

APP_DIR_NAME = "SeekR"

#: Windows Known Folder ids (stable across Windows versions and languages).
_KNOWN_FOLDER_IDS = {
    "desktop": "B4BFCC3A-DB2C-424C-B029-7FE99A87C641",
    "documents": "FDD39AD0-238F-46AF-ADB4-6C85480369C7",
    "downloads": "374DE290-123F-4565-9164-39C4925E467B",
    "pictures": "33E28130-4E1E-4676-835A-98395C3BC3BB",
}


def known_folder(name: str) -> Path | None:
    """Return a Windows Known Folder (respecting OneDrive redirection).

    ``Path.home() / "Documents"`` is wrong for redirected or localised
    profiles, so the shell API is used when available. Returns ``None`` off
    Windows or when the folder cannot be resolved.
    """
    if os.name != "nt":
        return None
    guid_text = _KNOWN_FOLDER_IDS.get(name.lower())
    if guid_text is None:
        return None
    try:
        import ctypes
        from ctypes import wintypes

        shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        ole32 = ctypes.WinDLL("ole32", use_last_error=True)
        shell32.SHGetKnownFolderPath.argtypes = [
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.HANDLE,
            ctypes.POINTER(ctypes.c_wchar_p),
        ]
        shell32.SHGetKnownFolderPath.restype = ctypes.c_long
        ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
        guid_buffer = ctypes.create_string_buffer(uuid.UUID(guid_text).bytes_le, 16)
        path_pointer = ctypes.c_wchar_p()
        result = shell32.SHGetKnownFolderPath(
            ctypes.byref(guid_buffer), 0, None, ctypes.byref(path_pointer)
        )
        if result != 0 or not path_pointer.value:
            return None
        try:
            return Path(path_pointer.value)
        finally:
            ole32.CoTaskMemFree(ctypes.cast(path_pointer, ctypes.c_void_p))
    except Exception:
        return None


def home() -> Path:
    """Return the current user's home directory."""
    return Path.home()


def app_data_dir() -> Path:
    """Return the per-user SeekR data directory.

    ``SEEKR_HOME`` overrides the location (used by the test suite and by
    portable installations).
    """
    override = os.environ.get("SEEKR_HOME")
    if override:
        return Path(override).expanduser()

    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(home() / "AppData" / "Roaming")
        return Path(base) / APP_DIR_NAME
    if sys.platform == "darwin":
        return home() / "Library" / "Application Support" / APP_DIR_NAME
    base = os.environ.get("XDG_CONFIG_HOME") or str(home() / ".config")
    return Path(base) / APP_DIR_NAME


def config_path() -> Path:
    return app_data_dir() / "config.json"


def database_path() -> Path:
    return app_data_dir() / "seekr.db"


def log_dir() -> Path:
    return app_data_dir() / "logs"


def log_path() -> Path:
    return log_dir() / "seekr.log"


def cache_dir() -> Path:
    return app_data_dir() / "cache"


def ensure_app_dirs() -> Path:
    """Create the data directories if they do not exist and return the root."""
    root = app_data_dir()
    for directory in (root, log_dir(), cache_dir()):
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError:
            # A read-only profile must not stop the application from starting;
            # logging falls back to stderr in that case.
            pass
    return root


def expand_path(value: str | os.PathLike[str]) -> Path:
    """Expand ``~`` and environment variables and return an absolute path."""
    text = os.path.expandvars(str(value)).strip().strip('"')
    return Path(os.path.expanduser(text))


def is_hidden(path: Path) -> bool:
    """Return True if *path* is hidden on the current platform."""
    name = path.name
    if name.startswith("."):
        return True
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.GetFileAttributesW.argtypes = [wintypes.LPCWSTR]
            kernel32.GetFileAttributesW.restype = wintypes.DWORD
            attrs = kernel32.GetFileAttributesW(str(path))
            if attrs != 0xFFFFFFFF and attrs & 0x2:  # FILE_ATTRIBUTE_HIDDEN
                return True
        except Exception:
            return False
    return False


def default_document_dirs() -> list[str]:
    """Return existing common user folders for the default file index."""
    if os.name == "nt":
        candidates = [known_folder(name) for name in ("desktop", "documents", "downloads")]
        resolved = [path for path in candidates if path is not None and path.is_dir()]
        if resolved:
            seen: set[str] = set()
            unique: list[str] = []
            for path in resolved:
                key = str(path).lower()
                if key not in seen:
                    seen.add(key)
                    unique.append(str(path))
            return unique
    candidates = [home() / "Desktop", home() / "Documents", home() / "Downloads"]
    return [str(path) for path in candidates if path.is_dir()]


def default_screenshot_dir() -> str:
    pictures = known_folder("pictures") if os.name == "nt" else home() / "Pictures"
    base = pictures if pictures is not None and pictures.is_dir() else home()
    return str(base / "SeekR")


def default_notes_dir() -> str:
    return str(app_data_dir() / "notes")


__all__ = [
    "home",
    "app_data_dir",
    "config_path",
    "database_path",
    "log_dir",
    "log_path",
    "cache_dir",
    "ensure_app_dirs",
    "expand_path",
    "is_hidden",
    "known_folder",
    "default_document_dirs",
    "default_screenshot_dir",
]
