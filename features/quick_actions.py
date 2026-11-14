"""Quick actions: folders, websites, applications and text snippets."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.config_manager import ConfigManager
from core.database import Database
from core.fuzzy import fuzzy_score
from core.logging_setup import get_logger
from core.models import ResultAction, SearchResult
from core.paths import known_folder
from core.search_engine import SearchProvider

from . import util

log = get_logger(__name__)

KINDS = {
    "open_dir": "Open folder",
    "open_url": "Open website",
    "launch_app": "Launch application",
    "copy_text": "Copy text",
}

KIND_GLYPHS = {"open_dir": "📁", "open_url": "🌐", "launch_app": "▣", "copy_text": "📋"}


def validate_action(data: dict[str, Any]) -> tuple[bool, str]:
    title = str(data.get("title", "")).strip()
    kind = str(data.get("kind", "")).strip()
    target = str(data.get("target", "")).strip()
    if not title:
        return False, "A title is required"
    if kind not in KINDS:
        return False, f"Unknown action type: {kind}"
    if not target:
        return False, "A target is required"
    if kind == "open_dir":
        if not Path(target).expanduser().is_dir():
            return False, f"Folder not found: {target}"
    if kind == "open_url":
        if not target.lower().startswith(("http://", "https://")):
            return False, "Websites must start with http:// or https://"
    if kind == "launch_app":
        parts = util.split_args(target)
        if not parts:
            return False, "No application given"
        candidate = Path(parts[0]).expanduser()
        if not candidate.exists() and util.which(parts[0]) is None:
            return False, f"Application not found: {parts[0]}"
    return True, ""


class QuickActionService:
    """CRUD and execution for user-defined quick actions."""

    def __init__(self, config: ConfigManager, db: Database, hooks):
        self.config = config
        self.db = db
        self.hooks = hooks

    def actions(self) -> list[dict]:
        return self.db.list_quick_actions()

    def seed_defaults(self) -> None:
        """Create a few real, path-based actions on first run."""
        if self.db.list_quick_actions():
            return
        home = Path.home()
        desktop = known_folder("desktop") or home / "Desktop"
        downloads = known_folder("downloads") or home / "Downloads"
        defaults = [
            ("Home folder", "open_dir", str(home), "Open your home directory"),
            ("Desktop", "open_dir", str(desktop), "Open the desktop folder"),
            ("Downloads", "open_dir", str(downloads), "Open the downloads folder"),
        ]
        for title, kind, target, description in defaults:
            if Path(target).is_dir():
                self.db.upsert_quick_action(
                    {"title": title, "kind": kind, "target": target, "description": description}
                )

    def save(self, data: dict) -> tuple[bool, str]:
        ok, message = validate_action(data)
        if not ok:
            return False, message
        result = self.db.upsert_quick_action(data)
        if result < 0:
            return False, "Could not save the action"
        return True, ""

    def delete(self, action_id: int) -> None:
        self.db.delete_quick_action(action_id)

    def execute(self, action: dict) -> tuple[bool, str]:
        kind = action.get("kind")
        target = str(action.get("target", ""))
        if kind == "open_dir":
            return self.hooks.open_path(target), f"Opened {target}"
        if kind == "open_url":
            ok = self.hooks.open_url(target)
            return ok, f"Opened {target}" if ok else f"Could not open {target}"
        if kind == "launch_app":
            parts = util.split_args(target)
            if not parts:
                return False, "No application given"
            candidate = Path(parts[0]).expanduser()
            argv = [str(candidate)] if candidate.exists() else [parts[0]]
            return util.run_detached([*argv, *parts[1:]])
        if kind == "copy_text":
            self.hooks.copy_text(target)
            return True, "Copied to clipboard"
        return False, f"Unknown action type: {kind}"

    def search(self, query: str, limit: int = 8) -> list[dict]:
        actions = self.actions()
        text = (query or "").strip()
        if not text:
            return actions[:limit]
        scored = []
        for action in actions:
            haystack = f"{action['title']} {action.get('description', '')}"
            score = fuzzy_score(text, haystack, typo_tolerance=True)
            if score > 0:
                scored.append((score, action))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [action for _, action in scored[:limit]]


class QuickActionsProvider(SearchProvider):
    """Quick actions, searchable automatically and via ``act:``."""

    id = "quick_actions"
    title = "Quick actions"
    keyword = "act"
    weight = 0.9
    auto = True

    def __init__(self, config, db, hooks, service: QuickActionService | None = None):
        super().__init__(config, db, hooks)
        self.service = service or QuickActionService(config, db, hooks)

    def search(self, query: str, limit: int) -> list[SearchResult]:
        if not self.config.get("quick_actions.enabled", True):
            return []
        text = (query or "").strip()
        if not text:
            return self.suggestions(limit)
        actions = self.service.search(text, limit)
        results = []
        for index, action in enumerate(actions):
            score = fuzzy_score(text, action["title"], typo_tolerance=True)
            if score < 0.55:
                continue
            results.append(self._result(action, score))
        return results[:limit]

    def _result(self, action: dict, score: float) -> SearchResult:
        kind = action.get("kind", "open_dir")
        return self.make_result(
            title=action.get("title", "Quick action"),
            subtitle=f"{KINDS.get(kind, kind)}  ·  {action.get('target', '')}",
            category="Action",
            score=score,
            primary=lambda: self._run(action),
            actions=[
                ResultAction("Copy target", lambda: self.hooks.copy_text(action.get("target", ""))),
                ResultAction("Edit quick actions", lambda: self.hooks.open_tools("actions")),
            ],
            copy_text=action.get("target", ""),
            icon_glyph=KIND_GLYPHS.get(kind, "⚡"),
            meta={"action": action},
        )

    def _run(self, action: dict) -> None:
        ok, message = self.service.execute(action)
        self.hooks.notify(message, "info" if ok else "error")
        if ok:
            self.hooks.hide_launcher()

    def suggestions(self, limit: int) -> list[SearchResult]:
        if not self.config.get("quick_actions.enabled", True):
            return []
        actions = self.service.actions()[: min(3, limit)]
        return [self._result(action, 0.52 - index * 0.02) for index, action in enumerate(actions)]

    def empty_help(self) -> SearchResult | None:
        return self.make_result(
            title="Quick actions",
            subtitle="Create folders, websites, apps or text snippets in Tools → Quick Actions",
            category="Action",
            score=1.0,
            primary=lambda: self.hooks.open_tools("actions"),
            icon_glyph="⚡",
        )


__all__ = ["KINDS", "QuickActionService", "QuickActionsProvider", "validate_action"]
