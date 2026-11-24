"""Single-instance enforcement using a local socket."""

from __future__ import annotations

import os
import time

from PySide6.QtCore import QCoreApplication, QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from .logging_setup import get_logger
from .version import APP_NAME

log = get_logger(__name__)

#: ``AllowSetForegroundWindow`` constant that grants the permission to any
#: process (``ASFW_ANY``).
_ASFW_ANY = 0xFFFFFFFF


def _allow_foreground_transfer() -> None:
    """Let the primary instance foreground its window on our behalf.

    Windows only lets a process set the foreground window if it received the
    last input event. The process the user just launched has that permission,
    so it hands it to the already-running instance before asking it to show;
    without this the primary can end up visible but un-focused (or hidden
    again by its focus-loss timer). Best effort: older systems and restrictive
    policies simply refuse the call.
    """
    if os.name != "nt":
        return
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.AllowSetForegroundWindow.argtypes = [wintypes.DWORD]
        user32.AllowSetForegroundWindow.restype = wintypes.BOOL
        user32.AllowSetForegroundWindow(wintypes.DWORD(_ASFW_ANY))
    except Exception:  # pragma: no cover - best effort, Windows only
        log.debug("Could not grant the running instance foreground rights", exc_info=True)


class SingleInstance(QObject):
    """Ensure only one SeekR process owns the launcher.

    The first process listens on a local socket; later processes send
    ``show`` and exit, letting the running instance surface its window.
    """

    show_requested = Signal()

    def __init__(self, key: str = f"{APP_NAME}.Launcher", parent: QObject | None = None):
        super().__init__(parent)
        self.key = key
        self._server: QLocalServer | None = None
        self._sockets: list[QLocalSocket] = []
        #: Partial payloads per connection. A show request can arrive in more
        #: than one chunk, so the server buffers instead of blocking the GUI
        #: thread waiting for the rest of the message.
        self._buffers: dict[QLocalSocket, bytes] = {}

    def notify_existing(self, timeout_ms: int = 1000) -> bool:
        """Return True if an existing instance accepted our message."""
        _allow_foreground_transfer()
        deadline = time.monotonic() + (timeout_ms / 1000.0)
        # The connect itself can spuriously fail under offscreen QPA even though
        # the request is delivered. Retry within the overall timeout budget.
        while True:
            socket = QLocalSocket()
            socket.connectToServer(self.key)
            remaining = max(1, int((deadline - time.monotonic()) * 1000))
            if socket.waitForConnected(remaining):
                break
            if time.monotonic() >= deadline:
                return False
            # Brief spin before retrying.
            time.sleep(0.01)
        # Allow the listener process to finish accepting the connection before we
        # send the payload. On Windows, a write issued immediately after the
        # connection handshake can be lost if the server hasn't processed the
        # pending socket yet.
        QCoreApplication.processEvents()
        socket.write(b"show")
        # The payload is tiny. waitForBytesWritten can report False spuriously
        # on Windows (offscreen QPA pumps pipe events slowly) even though the
        # bytes are queued for delivery; the frozen end-to-end run proved that.
        # Never treat its return value as failure.
        socket.waitForBytesWritten(max(1, int((deadline - time.monotonic()) * 1000)))
        QCoreApplication.processEvents()
        socket.disconnectFromServer()
        return True

    def listen(self) -> bool:
        """Become the primary instance. Returns False if listening failed."""
        if self._server is not None:
            return True
        QLocalServer.removeServer(self.key)
        self._server = QLocalServer(self)
        self._server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self._server.newConnection.connect(self._accept_connection)
        if not self._server.listen(self.key):
            log.warning("Could not start single-instance server: %s", self._server.errorString())
            self._server = None
            return False
        return True

    def _accept_connection(self) -> None:
        if self._server is None:
            return
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            if socket is None:
                return
            self._sockets.append(socket)
            socket.readyRead.connect(lambda s=socket: self._read_request(s))
            socket.disconnected.connect(lambda s=socket: self._cleanup_socket(s))
            # Read only what has already arrived. Never wait here: this slot
            # runs on the GUI thread, and a client that connects without
            # sending a payload must not freeze the launcher. Remaining bytes
            # arrive through the readyRead connection above.
            self._read_request(socket)

    def _read_request(self, socket: QLocalSocket) -> None:
        try:
            data = bytes(socket.readAll())
        except Exception:  # pragma: no cover - defensive
            return
        if not data:
            return
        buffer = self._buffers.get(socket, b"") + data
        # A valid request is tiny; keep a bounded tail so a misbehaving client
        # cannot grow memory indefinitely.
        buffer = buffer[-64:]
        # Only an explicit "show" request is honoured, and only once per
        # payload; a later empty read or a disconnect must not raise the
        # launcher again.
        if b"show" in buffer:
            self._buffers.pop(socket, None)
            self.show_requested.emit()
        else:
            self._buffers[socket] = buffer

    def _cleanup_socket(self, socket: QLocalSocket) -> None:
        if socket in self._sockets:
            self._sockets.remove(socket)
        self._buffers.pop(socket, None)
        socket.deleteLater()

    def close(self) -> None:
        if self._server is not None:
            self._server.close()
            QLocalServer.removeServer(self.key)
            self._server = None
        self._buffers.clear()
        for socket in list(self._sockets):
            self._sockets.remove(socket)
            socket.abort()
            socket.deleteLater()


__all__ = ["SingleInstance"]
