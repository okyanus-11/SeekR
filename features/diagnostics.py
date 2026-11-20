"""Explicit, local-only diagnostic report generation with best-effort redaction."""

from __future__ import annotations

import os
import platform
import re
import sys
from pathlib import Path

from core import paths
from core.version import APP_VERSION


def redact_diagnostic_text(value: str) -> str:
    """Remove common personal identifiers and secret-shaped values from log text."""
    text = str(value)
    home = str(Path.home())
    if home:
        text = re.sub(re.escape(home), "<HOME>", text, flags=re.IGNORECASE if os.name == "nt" else 0)
    text = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+", "Bearer <REDACTED>", text)
    text = re.sub(
        r"(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|password|passwd|secret)\b(\s*[:=]\s*)[^\s,;]+",
        r"\1\2<REDACTED>",
        text,
    )
    text = re.sub(r"\b(?:gh[pousr]_[A-Za-z0-9_]{12,}|sk-[A-Za-z0-9_-]{16,})\b", "<REDACTED_TOKEN>", text)
    text = re.sub(r"([?&][A-Za-z0-9_.-]+=)[^&\s]+", r"\1<REDACTED>", text)
    text = re.sub(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "<EMAIL>", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "<IP_ADDRESS>", text)
    text = re.sub(r"(?i)\b[A-Z]:\\Users\\[^\\\s]+", "<USER_PATH>", text)
    text = re.sub(r"(?<!\w)/home/[^/\s]+", "<HOME>", text)
    text = re.sub(r"(?<!\w)/Users/[^/\s]+", "<HOME>", text)
    # Search failures can include the user's query in quotes. Keep the
    # diagnostic event and module name, but remove quoted free-form content.
    text = re.sub(r'"[^"\r\n]{1,256}"', '"<REDACTED_TEXT>"', text)
    text = re.sub(r"'[^'\r\n]{1,256}'", "'<REDACTED_TEXT>'", text)
    return text


def build_diagnostic_report(include_logs: bool = False) -> str:
    """Build a report for the user to review and save locally; never uploads it."""
    try:
        import PySide6
        qt_version = getattr(PySide6, "__version__", "unknown")
    except Exception:
        qt_version = "unavailable"
    try:
        import psutil
        psutil_version = getattr(psutil, "__version__", "unknown")
    except Exception:
        psutil_version = "unavailable"

    lines = [
        "SeekR diagnostic report",
        f"SeekR version: {APP_VERSION}",
        f"Platform: {platform.system()} {platform.release()} ({platform.machine()})",
        f"Python: {sys.version.split()[0]}",
        f"PySide6: {qt_version}",
        f"psutil: {psutil_version}",
        "",
        "Privacy: no clipboard contents, notes, indexed file lists, or search history are collected.",
        "This report is generated locally. SeekR does not transmit it.",
    ]
    if include_logs:
        lines.extend(["", "Recent application logs (best-effort redaction; review before sharing):"])
        log_root = paths.log_dir()
        remaining = 2_000_000
        try:
            candidates = sorted(
                (path for path in log_root.glob("seekr.log*") if path.is_file()),
                key=lambda path: path.name,
                reverse=True,
            )
            for path in candidates:
                if remaining <= 0:
                    break
                try:
                    size = min(path.stat().st_size, remaining)
                    if size <= 0:
                        continue
                    with path.open("rb") as stream:
                        stream.seek(max(0, path.stat().st_size - size))
                        raw = stream.read(size)
                    decoded = raw.decode("utf-8", errors="replace")
                    lines.extend(["", f"--- {path.name} ---", redact_diagnostic_text(decoded)])
                    remaining -= len(raw)
                except OSError:
                    lines.extend(["", f"--- {path.name}: unreadable ---"])
        except OSError:
            lines.extend(["", "Log directory unavailable."])
    return "\n".join(lines).rstrip() + "\n"


__all__ = ["build_diagnostic_report", "redact_diagnostic_text"]
