"""Opt-in local text snippets with explicit copy/expansion actions."""
from __future__ import annotations

import json
from typing import Any

from core.config_manager import ConfigManager
from core.database import Database, DatabaseError
from core.fuzzy import fuzzy_score
from core.logging_setup import get_logger
from core.models import ResultAction, SearchResult
from core.search_engine import SearchProvider

log = get_logger(__name__)
MAX_SNIPPET_CHARS = 50_000
SNIPPET_SCHEMA_VERSION = 1
MAX_SNIPPET_IMPORT_BYTES = 2_000_000
MAX_IMPORTED_SNIPPETS = 200


def validate_snippet(data: Any) -> tuple[bool, str]:
    if not isinstance(data, dict):
        return False, "Snippet data must be an object"
    title = str(data.get("title", "")).strip()
    content = data.get("content")
    if not title:
        return False, "A snippet title is required"
    if len(title) > 100:
        return False, "Snippet titles must be 100 characters or fewer"
    if not isinstance(content, str) or not content.strip():
        return False, "Snippet content is required"
    if len(content) > MAX_SNIPPET_CHARS:
        return False, f"Snippet content must be at most {MAX_SNIPPET_CHARS} characters"
    for field in ("category", "shortcut"):
        if len(str(data.get(field, ""))) > 80:
            return False, f"Snippet {field} must be 80 characters or fewer"
    return True, ""


class SnippetService:
    def __init__(self, config: ConfigManager, db: Database, hooks):
        self.config = config
        self.db = db
        self.hooks = hooks

    def snippets(self) -> list[dict[str, Any]]:
        return self.db.list_snippets()

    def save(self, data: dict[str, Any]) -> tuple[bool, str]:
        ok, message = validate_snippet(data)
        if not ok:
            return False, message
        self.db.upsert_snippet({
            "id": data.get("id"),
            "title": str(data["title"]).strip(),
            "category": str(data.get("category", "")).strip(),
            "shortcut": str(data.get("shortcut", "")).strip(),
            "content": data["content"],
        })
        return True, ""

    def delete(self, snippet_id: int) -> None:
        self.db.delete_snippet(snippet_id)

    def export_json(self) -> str:
        return json.dumps({
            "schema_version": SNIPPET_SCHEMA_VERSION,
            "snippets": [
                {key: row.get(key, "") for key in ("title", "category", "shortcut", "content")}
                for row in self.snippets()
            ],
        }, ensure_ascii=False, indent=2)

    def import_json(self, content: str) -> tuple[bool, str, int]:
        if not isinstance(content, str):
            return False, "Snippet export must be UTF-8 text", 0
        try:
            if len(content.encode("utf-8")) > MAX_SNIPPET_IMPORT_BYTES:
                return False, "Snippet export is too large", 0
        except UnicodeEncodeError:
            return False, "Snippet export contains invalid Unicode text", 0
        try:
            payload = json.loads(content)
        except (TypeError, ValueError):
            return False, "The snippet file is not valid JSON", 0
        if not isinstance(payload, dict) or payload.get("schema_version") != SNIPPET_SCHEMA_VERSION:
            return False, "Unsupported snippet export version", 0
        rows = payload.get("snippets")
        if not isinstance(rows, list) or len(rows) > MAX_IMPORTED_SNIPPETS:
            return False, f"Snippet export must contain at most {MAX_IMPORTED_SNIPPETS} entries", 0
        prepared = []
        for index, row in enumerate(rows, 1):
            ok, message = validate_snippet(row)
            if not ok:
                return False, f"Snippet {index}: {message}", 0
            prepared.append({
                "title": str(row["title"]).strip(),
                "category": str(row.get("category", "")).strip(),
                "shortcut": str(row.get("shortcut", "")).strip(),
                "content": row["content"],
            })
        try:
            self.db.insert_snippets_atomic(prepared)
        except DatabaseError as exc:
            log.exception("Snippet import failed")
            return False, str(exc), 0
        return True, "Snippets imported", len(prepared)

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        text = (query or "").strip()
        rows = self.snippets()
        if not text:
            return rows[:limit]
        scored = []
        for row in rows:
            haystack = " ".join((row["title"], row.get("category", ""), row.get("shortcut", "")))
            score = fuzzy_score(text, haystack, typo_tolerance=True)
            if score > 0:
                scored.append((score, row))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [row for score, row in scored[:limit] if score >= 0.35]

    def copy(self, snippet: dict[str, Any]) -> bool:
        # Expansion is always an explicit user action; no background text injection.
        return bool(self.hooks.copy_text(str(snippet.get("content", ""))))


class SnippetProvider(SearchProvider):
    """Explicit snippet search via the snip: keyword."""

    id = "snippets"
    title = "Text snippets"
    keyword = "snip"
    weight = 0.9
    auto = False

    def __init__(self, config, db, hooks, service: SnippetService | None = None):
        super().__init__(config, db, hooks)
        self.service = service or SnippetService(config, db, hooks)

    def search(self, query: str, limit: int) -> list[SearchResult]:
        rows = self.service.search(query, limit)
        return [self._result(row, 0.9 - index * 0.02) for index, row in enumerate(rows)]

    def _result(self, snippet: dict[str, Any], score: float) -> SearchResult:
        preview = " ".join(snippet["content"].split())
        return self.make_result(
            title=snippet["title"],
            subtitle=f"{snippet.get('category') or 'Snippet'}  ·  {preview[:100]}",
            category="Snippet",
            score=score,
            primary=lambda: self._copy(snippet),
            actions=[
                ResultAction("Copy snippet", lambda: self._copy(snippet)),
                ResultAction("Manage snippets", lambda: self.hooks.open_tools("snippets")),
            ],
            copy_text=snippet["content"],
            icon_glyph="¶",
            meta={"snippet": snippet},
        )

    def _copy(self, snippet: dict[str, Any]) -> None:
        if self.service.copy(snippet):
            self.hooks.notify(f"Copied snippet: {snippet['title']}")
            self.hooks.hide_launcher()
        else:
            self.hooks.notify("Could not copy snippet", "error")

    def empty_help(self) -> SearchResult | None:
        return self.make_result(
            title="No snippets found",
            subtitle="Create reusable text in Tools → Snippets, then search with snip:",
            category="Snippet",
            score=1.0,
            primary=lambda: self.hooks.open_tools("snippets"),
            icon_glyph="¶",
        )


__all__ = ["SnippetService", "SnippetProvider", "validate_snippet", "MAX_SNIPPET_CHARS",
    "SNIPPET_SCHEMA_VERSION", "MAX_SNIPPET_IMPORT_BYTES", "MAX_IMPORTED_SNIPPETS"]
