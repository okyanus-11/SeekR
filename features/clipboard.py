"""Clipboard history."""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QGuiApplication

from core.config_manager import ConfigManager
from core.database import Database
from core.logging_setup import get_logger
from core.models import ResultAction, SearchResult
from core.search_engine import SearchProvider

from . import util

log = get_logger(__name__)

_MAX_ENTRY_CHARS = 200_000


class ClipboardService:
    """Stores clipboard text history in SQLite."""

    def __init__(self, config: ConfigManager, db: Database):
        self.config = config
        self.db = db

    @property
    def enabled(self) -> bool:
        return (
            bool(self.config.get("clipboard.enabled", False))
            and bool(self.config.get("privacy.clipboard_history", False))
            and bool(self.config.get("privacy.clipboard_history_consent", False))
        )

    def capture(self, text: str, source: str = "") -> dict | None:
        if not self.enabled:
            return None
        if not text or not text.strip() or len(text) > _MAX_ENTRY_CHARS:
            return None
        if self.config.get("clipboard.exclude_sensitive", True) and self._looks_sensitive(text):
            return None
        dedupe = bool(self.config.get("clipboard.ignore_duplicates", True))
        inserted = self.db.add_clipboard(text, source=source, dedupe=dedupe)
        if inserted is None:
            return None
        self.db.prune_clipboard(int(self.config.get("clipboard.limit", 200) or 200))
        return {"id": inserted, "text": text}

    @staticmethod
    def _looks_sensitive(text: str) -> bool:
        """Skip obvious secret-shaped single-line entries.

        This is a privacy heuristic for clipboard capture; entries that look
        like private keys are not stored.
        """
        lowered = text.lower()
        if "-----begin" in lowered and "private key" in lowered:
            return True
        return False

    def items(self, search: str = "", limit: int = 100) -> list[dict]:
        return self.db.clipboard_items(search, limit)

    def pin(self, item_id: int, pinned: bool) -> None:
        self.db.set_clipboard_pinned(item_id, pinned)

    def delete(self, item_id: int) -> None:
        self.db.delete_clipboard(item_id)

    def clear(self, keep_pinned: bool = True) -> None:
        self.db.clear_clipboard(keep_pinned=keep_pinned)

    def count(self) -> int:
        return self.db.clipboard_count()


class ClipboardMonitor(QObject):
    """Watches the system clipboard and records text entries."""

    captured = Signal(dict)

    def __init__(self, service: ClipboardService, parent: QObject | None = None):
        super().__init__(parent)
        self.service = service
        self._last_text = ""
        self._timer = QTimer(self)
        self._timer.setInterval(int(service.config.get("clipboard.poll_interval_ms", 600) or 600))
        self._timer.timeout.connect(self._poll)
        self._clipboard = None
        self._started = False

    def start(self) -> bool:
        if self._started:
            return True
        if QGuiApplication.instance() is None:
            return False
        clipboard = QGuiApplication.clipboard()
        if clipboard is None:
            return False
        self._clipboard = clipboard
        try:
            self._last_text = clipboard.text() or ""
        except Exception:
            self._last_text = ""
        clipboard.dataChanged.connect(self._poll)
        self._timer.start()
        self._started = True
        return True

    def stop(self) -> None:
        self._timer.stop()
        if self._clipboard is not None:
            try:
                self._clipboard.dataChanged.disconnect(self._poll)
            except (TypeError, RuntimeError):
                pass
        self._started = False

    def _poll(self) -> None:
        if not self.service.enabled or self._clipboard is None:
            return
        try:
            mime = self._clipboard.mimeData()
            if mime is None or not mime.hasText():
                return
            text = self._clipboard.text()
        except Exception:  # pragma: no cover - clipboard backends vary
            return
        if not text or text == self._last_text:
            return
        self._last_text = text
        stored = self.service.capture(text)
        if stored is not None:
            self.captured.emit(stored)


class ClipboardProvider(SearchProvider):
    """The ``clip:`` keyword."""

    id = "clipboard"
    title = "Clipboard history"
    keyword = "clip"
    weight = 0.8
    auto = False

    def __init__(self, config, db, hooks, service: ClipboardService | None = None):
        super().__init__(config, db, hooks)
        self.service = service or ClipboardService(config, db)

    def search(self, query: str, limit: int) -> list[SearchResult]:
        items = self.service.items((query or "").strip(), limit)
        if not items and not self.service.enabled:
            return [
                self.make_result(
                    title="Clipboard history is disabled",
                    subtitle="Enable clipboard history in Settings to start capture",
                    category="Clipboard",
                    score=1.0,
                    primary=lambda: self.hooks.open_settings("privacy"),
                    icon_glyph="⧉",
                )
            ]
        return [self._result(item, 0.9 - index * 0.02) for index, item in enumerate(items)]

    def _result(self, item: dict, score: float) -> SearchResult:
        text = item.get("text", "")
        preview = " ".join(text.split())
        title = preview[:120] + ("…" if len(preview) > 120 else "")
        pinned = bool(item.get("pinned"))
        subtitle = f"Copied {util.format_ago(item.get('created'))}" + ("  ·  pinned" if pinned else "")
        actions = [
            ResultAction(
                "Unpin" if pinned else "Pin",
                lambda: self._toggle_pin(item),
            ),
            ResultAction("Delete entry", lambda: self._delete(item)),
        ]
        return self.make_result(
            title=title or "(empty entry)",
            subtitle=subtitle,
            category="Clipboard",
            score=score,
            primary=lambda: self._copy(text),
            actions=actions,
            copy_text=text,
            icon_glyph="📋",
            meta={"clipboard": item},
        )

    def _copy(self, text: str) -> None:
        self.hooks.copy_text(text)
        self.hooks.notify("Copied from clipboard history")
        self.hooks.hide_launcher()

    def _toggle_pin(self, item: dict) -> None:
        self.service.pin(item["id"], not bool(item.get("pinned")))
        self.hooks.notify("Clipboard entry pinned" if not item.get("pinned") else "Clipboard entry unpinned")

    def _delete(self, item: dict) -> None:
        self.service.delete(item["id"])
        self.hooks.notify("Clipboard entry deleted")

    def empty_help(self) -> SearchResult | None:
        return self.make_result(
            title="No clipboard history yet",
            subtitle="Enable clipboard history and copy some text to show it here",
            category="Clipboard",
            score=1.0,
            primary=lambda: self.hooks.open_clipboard(),
            icon_glyph="📋",
        )


__all__ = ["ClipboardService", "ClipboardMonitor", "ClipboardProvider"]
