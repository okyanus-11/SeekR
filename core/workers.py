"""Threading helpers: cancellable workers and debounced callbacks."""

from __future__ import annotations

import threading
import traceback
from typing import Any, Callable, Optional

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal

from .errors import describe_error
from .logging_setup import get_logger

log = get_logger(__name__)


class CancelToken:
    """A cooperative cancellation flag shared with worker threads."""

    __slots__ = ("_event",)

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    def reset(self) -> None:
        self._event.clear()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()


class WorkerSignals(QObject):
    """Signals emitted by :class:`FunctionWorker`."""

    finished = Signal(object)
    failed = Signal(str, str)
    progress = Signal(int, str)


class FunctionWorker(QRunnable):
    """Runs a callable on the global thread pool and reports the outcome."""

    def __init__(
        self,
        fn: Callable[..., Any],
        *args: Any,
        on_cleanup: Optional[Callable[[], None]] = None,
        **kwargs: Any,
    ):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self._on_cleanup = on_cleanup
        self.signals = WorkerSignals()
        self.setAutoDelete(True)

    def run(self) -> None:  # pragma: no cover - executed on a worker thread
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as exc:
            text = traceback.format_exc()
            log.error("Background task failed: %s\n%s", describe_error(exc), text)
            self.signals.failed.emit(describe_error(exc), text)
        else:
            self.signals.finished.emit(result)
        finally:
            if self._on_cleanup is not None:
                try:
                    self._on_cleanup()
                except Exception:
                    log.exception("Background task cleanup failed")


def run_async(
    fn: Callable[..., Any],
    *args: Any,
    on_finished: Optional[Callable[[Any], None]] = None,
    on_failed: Optional[Callable[[str, str], None]] = None,
    on_progress: Optional[Callable[[int, str], None]] = None,
    on_cleanup: Optional[Callable[[], None]] = None,
    pool: QThreadPool | None = None,
    **kwargs: Any,
) -> FunctionWorker:
    """Run *fn* off the GUI thread, wiring optional callbacks."""
    worker = FunctionWorker(fn, *args, on_cleanup=on_cleanup, **kwargs)
    if on_finished is not None:
        worker.signals.finished.connect(on_finished)
    if on_failed is not None:
        worker.signals.failed.connect(on_failed)
    if on_progress is not None:
        worker.signals.progress.connect(on_progress)
    (pool or QThreadPool.globalInstance()).start(worker)
    return worker


class Debouncer(QObject):
    """Call a slot once after input stops for *delay_ms* milliseconds."""

    def __init__(self, delay_ms: int = 150, parent: QObject | None = None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fire)
        self._callback: Optional[Callable[[], None]] = None
        self._timer.setInterval(max(0, delay_ms))

    def set_delay(self, delay_ms: int) -> None:
        self._timer.setInterval(max(0, delay_ms))

    def call_later(self, callback: Callable[[], None], delay_ms: int | None = None) -> None:
        self._callback = callback
        if delay_ms is not None:
            self._timer.setInterval(max(0, delay_ms))
        self._timer.start()

    def cancel(self) -> None:
        self._timer.stop()

    def _fire(self) -> None:
        callback = self._callback
        self._callback = None
        if callback is not None:
            try:
                callback()
            except Exception:
                log.exception("Debounced callback failed")


__all__ = ["CancelToken", "WorkerSignals", "FunctionWorker", "run_async", "Debouncer"]
