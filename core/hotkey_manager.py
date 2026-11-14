"""Global hotkey registration.

On Windows the launcher is summoned through ``RegisterHotKey`` so the shortcut
works system-wide. Other platforms fall back to a clear, non-blocking error so
the rest of the application keeps working.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import sys
from typing import Optional

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication, QObject, Signal

from .hotkeys import MOD_NOREPEAT, HotkeyError, normalize_hotkey, parse_hotkey
from .logging_setup import get_logger

log = get_logger(__name__)

WM_HOTKEY = 0x0312

_ERROR_MESSAGES = {
    1409: "That hotkey is already registered by another application.",
    5: "Access denied while registering the hotkey.",
    87: "The hotkey combination is not valid.",
}


class _NativeEventFilter(QAbstractNativeEventFilter):
    """Receives ``WM_HOTKEY`` messages from the Windows message loop."""

    def __init__(self, on_hotkey):
        super().__init__()
        self._on_hotkey = on_hotkey

    def nativeEventFilter(self, event_type, message):  # noqa: N802 (Qt API)
        try:
            if event_type in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
                # PySide6 passes the native MSG pointer as an integer-like object.
                msg = ctypes.wintypes.MSG.from_address(int(message))
                if msg.message == WM_HOTKEY:
                    self._on_hotkey(int(msg.wParam))
                    return True, 0
        except Exception:  # pragma: no cover - defensive around ctypes
            log.debug("Native hotkey event could not be parsed", exc_info=True)
        return False, 0


class HotkeyManager(QObject):
    """Registers and unregisters the global launcher shortcut."""

    activated = Signal()
    registered = Signal(str)
    failed = Signal(str)
    unavailable = Signal(str)

    HOTKEY_ID = 0x5EA1

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._user32 = None
        self._filter: Optional[_NativeEventFilter] = None
        self._current: Optional[str] = None
        self._installed = False
        self.available = sys.platform == "win32"
        if self.available:
            try:
                self._user32 = ctypes.WinDLL("user32", use_last_error=True)
            except OSError as exc:  # pragma: no cover - Windows only
                log.error("Could not load user32: %s", exc)
                self.available = False
        else:
            log.info("Global hotkeys are only available on Windows; using in-app shortcuts")

    # ---------------------------------------------------------------- setup
    def install(self) -> None:
        """Install the native event filter (idempotent)."""
        if not self.available or self._installed:
            return
        app = QCoreApplication.instance()
        if app is None:
            return
        self._filter = _NativeEventFilter(self._handle_hotkey)
        app.installNativeEventFilter(self._filter)
        self._installed = True

    def _handle_hotkey(self, hotkey_id: int) -> None:
        if hotkey_id == self.HOTKEY_ID:
            self.activated.emit()

    # ------------------------------------------------------------- register
    def register(self, hotkey: str) -> bool:
        """Register *hotkey* globally, replacing any previous registration."""
        if not self.available or self._user32 is None:
            message = "Global hotkeys require Windows. The launcher can be opened from the tray icon."
            self.unavailable.emit(message)
            return False
        self.install()
        try:
            normalized = normalize_hotkey(hotkey)
            modifiers, virtual_key = parse_hotkey(hotkey)
        except HotkeyError as exc:
            self.failed.emit(str(exc))
            return False

        self.unregister()
        ctypes.set_last_error(0)
        success = self._user32.RegisterHotKey(None, self.HOTKEY_ID, modifiers | MOD_NOREPEAT, virtual_key)
        if not success:
            error_code = ctypes.get_last_error()
            message = _ERROR_MESSAGES.get(
                error_code, f"Could not register {normalized} (Windows error {error_code})."
            )
            log.warning("Hotkey registration failed: %s", message)
            self.failed.emit(message)
            return False
        self._current = normalized
        log.info("Registered global hotkey %s", normalized)
        self.registered.emit(normalized)
        return True

    def unregister(self) -> None:
        if self._user32 is not None and self._current is not None:
            try:
                self._user32.UnregisterHotKey(None, self.HOTKEY_ID)
            except Exception:  # pragma: no cover - defensive
                log.debug("UnregisterHotKey failed", exc_info=True)
            self._current = None

    @property
    def current(self) -> Optional[str]:
        return self._current

    def cleanup(self) -> None:
        self.unregister()
        app = QCoreApplication.instance()
        if self._filter is not None and app is not None:
            try:
                app.removeNativeEventFilter(self._filter)
            except Exception:  # pragma: no cover - defensive
                pass
        self._filter = None
        self._installed = False


__all__ = ["HotkeyManager", "WM_HOTKEY"]
