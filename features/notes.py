"""Quick notes."""

from __future__ import annotations

from core.config_manager import ConfigManager
from core.database import Database
from core.logging_setup import get_logger
from core.models import ResultAction, SearchResult
from core.search_engine import SearchProvider

from . import util

log = get_logger(__name__)


class NotesService:
    """CRUD operations for local notes."""

    def __init__(self, config: ConfigManager, db: Database):
        self.config = config
        self.db = db

    def create(self, title: str = "", body: str = "") -> int:
        if not title.strip() and body.strip():
            title = body.strip().splitlines()[0][:80]
        return self.db.create_note(title, body)

    def update(self, note_id: int, title: str | None = None, body: str | None = None) -> None:
        self.db.update_note(note_id, title=title, body=body)

    def delete(self, note_id: int) -> None:
        self.db.delete_note(note_id)

    def get(self, note_id: int) -> dict | None:
        return self.db.get_note(note_id)

    def list(self, search: str = "", limit: int = 200) -> list[dict]:
        return self.db.notes(search, limit)

    def toggle_pin(self, note_id: int) -> bool:
        note = self.db.get_note(note_id)
        if note is None:
            return False
        new_state = not bool(note["pinned"])
        self.db.update_note(note_id, pinned=new_state)
        return new_state

    def count(self) -> int:
        return self.db.note_count()


class NotesProvider(SearchProvider):
    """The ``note:`` keyword plus automatic note results."""

    id = "notes"
    title = "Quick notes"
    keyword = "note"
    weight = 0.85
    auto = True

    def __init__(self, config, db, hooks, service: NotesService | None = None):
        super().__init__(config, db, hooks)
        self.service = service or NotesService(config, db)

    def search(self, query: str, limit: int) -> list[SearchResult]:
        term = (query or "").strip()
        if not term:
            return self.suggestions(limit)
        rows = self.service.list(term, limit)
        return [self._result(row, 0.92 - index * 0.04) for index, row in enumerate(rows)]

    def _result(self, note: dict, score: float) -> SearchResult:
        body = note.get("body", "") or ""
        preview = " ".join(body.split())[:80]
        title = note.get("title") or "Untitled note"
        actions = [
            ResultAction("Copy note text", lambda: self.hooks.copy_text(body)),
            ResultAction("Delete note", lambda: self._delete(note)),
        ]
        return self.make_result(
            title=title,
            subtitle=(f"{preview}  ·  " if preview else "") + f"Updated {util.format_ago(note.get('updated'))}",
            category="Note",
            score=score,
            primary=lambda: self.hooks.open_notes(note["id"]),
            actions=actions,
            copy_text=body,
            icon_glyph="📝",
            meta={"note": note},
        )

    def _delete(self, note: dict) -> None:
        if self.hooks.confirm("Delete note", f"Delete “{note.get('title', 'note')}”?"):
            self.service.delete(note["id"])
            self.hooks.notify("Note deleted")

    def suggestions(self, limit: int) -> list[SearchResult]:
        rows = self.service.list("", max(2, min(limit, 2)))
        return [self._result(row, 0.55 - index * 0.03) for index, row in enumerate(rows)]

    def empty_help(self) -> SearchResult | None:
        return self.make_result(
            title="No notes match",
            subtitle="Open Quick Notes to create one",
            category="Note",
            score=1.0,
            primary=lambda: self.hooks.open_notes(),
            icon_glyph="📝",
        )


__all__ = ["NotesService", "NotesProvider"]
