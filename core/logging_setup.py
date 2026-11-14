"""Centralized logging configuration."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from . import paths

_CONFIGURED = False
_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"


def setup_logging(debug: bool = False, log_to_file: bool = True) -> logging.Logger:
    """Configure the root logger once and return it."""
    global _CONFIGURED
    root = logging.getLogger()
    level = logging.DEBUG if debug else logging.INFO
    root.setLevel(level)

    if _CONFIGURED:
        for handler in root.handlers:
            handler.setLevel(level)
        return root

    formatter = logging.Formatter(_FORMAT, datefmt=_DATEFMT)

    console = logging.StreamHandler(stream=sys.stderr)
    console.setLevel(logging.DEBUG if debug else logging.WARNING)
    console.setFormatter(formatter)
    root.addHandler(console)

    if log_to_file:
        try:
            paths.ensure_app_dirs()
            file_handler = RotatingFileHandler(
                paths.log_path(), maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
        except OSError:
            root.warning("File logging unavailable; continuing with console logging only")

    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    _CONFIGURED = True
    return root


def get_logger(name: str) -> logging.Logger:
    """Return a module logger (does not configure handlers)."""
    return logging.getLogger(name)


def shutdown_logging() -> None:
    """Flush and detach all handlers (used on exit)."""
    logging.shutdown()


__all__ = ["setup_logging", "get_logger", "shutdown_logging"]
