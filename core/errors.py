"""Error types and process-wide exception handling for SeekR."""

from __future__ import annotations

import logging
import traceback
from typing import Callable

from .logging_setup import get_logger

log = get_logger(__name__)


class SeekRError(Exception):
    """Base class for all SeekR errors."""


class ConfigError(SeekRError):
    """Raised when the configuration file cannot be read or validated."""


class DatabaseError(SeekRError):
    """Raised when a database operation fails."""


class ProviderError(SeekRError):
    """Raised by a search provider that cannot answer a query."""


class FeatureUnavailable(SeekRError):
    """Raised when a feature is not supported on the current platform."""


def describe_error(exc: BaseException) -> str:
    """Return a short, user-facing description without a stack trace."""
    name = type(exc).__name__
    message = str(exc).strip()
    return f"{name}: {message}" if message else name


#: Previous ``sys.excepthook``; set by :func:`install_excepthook`.
sys_hook: Callable = lambda *args: None


def install_excepthook(on_error: Callable[[str, str], None] | None = None) -> None:
    """Install an excepthook that logs unexpected errors.

    *on_error* receives ``(summary, traceback_text)`` so the UI can surface a
    non-fatal message instead of the application dying silently.
    """

    def _hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys_hook(exc_type, exc_value, exc_tb)
            return
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        log.error("Unhandled exception:\n%s", text)
        if on_error is not None:
            try:
                on_error(describe_error(exc_value), text)
            except Exception:  # pragma: no cover - defensive
                log.exception("Error handler failed")

    global sys_hook
    import sys

    if sys.excepthook is not _hook:
        sys_hook = sys.excepthook
    sys.excepthook = _hook


__all__ = [
    "SeekRError",
    "ConfigError",
    "DatabaseError",
    "ProviderError",
    "FeatureUnavailable",
    "describe_error",
    "install_excepthook",
]
