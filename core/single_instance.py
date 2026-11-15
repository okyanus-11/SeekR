"""Single-instance enforcement using a local socket."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QObject, Signal
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

    def notify_existing(self, timeout_ms: int = 1000) -> bool:
        """Return True if an existing instance accepted our message."""
        socket = QLocalSocket()
        socket.connectToServer(self.key)
        if not socket.waitForConnected(timeout_ms):
            return False
        # Allow the listener process to finish accepting the connection before we
        # send the payload. On Windows, a write issued immediately after the
        # connection handshake can be lost if the server hasn't processed the
        # pending socket yet.
        QCoreApplication.processEvents()
        socket.write(b"show")
        if not socket.waitForBytesWritten(timeout_ms):
            socket.disconnectFromServer()
            return False
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
            if socket.bytesAvailable() == 0:
                socket.waitForReadyRead(500)
            self._read_request(socket)
            # On Windows the data may arrive slightly after the first read;
            # retry once after a short wait.
            if socket.bytesAvailable() > 0:
                self._read_request(socket)

    def _read_request(self, socket: QLocalSocket) -> None:
        try:
            if socket.bytesAvailable() <= 0:
                return
            message = bytes(socket.readAll()).decode("utf-8", "ignore").strip()
            # If the message is incomplete, wait briefly for more data.
            if message and message != "show" and socket.waitForReadyRead(200):
                extra = bytes(socket.readAll()).decode("utf-8", "ignore").strip()
                if extra:
                    message = (message + extra).strip()
        except Exception:  # pragma: no cover - defensive
            return
        # Only an explicit "show" request is honoured; an empty read (for
        # example a second readyRead after the payload was consumed) must not
        # raise the launcher a second time.
        if message == "show":
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
            self._sockets.remove(socket)
            socket.abort()
            socket.deleteLater()


__all__ = ["SingleInstance"]
