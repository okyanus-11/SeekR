"""Single-instance enforcement using a local socket."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from .logging_setup import get_logger
from .version import APP_NAME

log = get_logger(__name__)


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

    def notify_existing(self, timeout_ms: int = 300) -> bool:
        """Return True if an existing instance accepted our message."""
        socket = QLocalSocket()
        socket.connectToServer(self.key)
        if not socket.waitForConnected(timeout_ms):
            return False
        socket.write(b"show")
        socket.waitForBytesWritten(timeout_ms)
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
            socket.readyRead.connect(lambda s=socket: self._read_request(s))
            socket.disconnected.connect(lambda s=socket: self._cleanup_socket(s))
            socket.waitForReadyRead(200)
            self._read_request(socket)

    def _read_request(self, socket: QLocalSocket) -> None:
        try:
            message = bytes(socket.readAll()).decode("utf-8", "ignore").strip()
        except Exception:  # pragma: no cover - defensive
            message = ""
        if message in {"show", ""}:
            self.show_requested.emit()

    def _cleanup_socket(self, socket: QLocalSocket) -> None:
        if socket in self._sockets:
            self._sockets.remove(socket)
        socket.deleteLater()

    def close(self) -> None:
        if self._server is not None:
            self._server.close()
            QLocalServer.removeServer(self.key)
            self._server = None
        for socket in list(self._sockets):
            socket.deleteLater()
        self._sockets.clear()


__all__ = ["SingleInstance"]
