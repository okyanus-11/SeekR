"""Unified command-center palette entered with the leading > character."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from core.config_manager import ConfigManager
from core.database import Database
from core.fuzzy import fuzzy_score
from core.models import SearchResult
from core.search_engine import SearchProvider


@dataclass(frozen=True)
class CenterAction:
    title: str
    description: str
    category: str
    callback: Callable[[], None]


class CommandCenterProvider(SearchProvider):
    id = "command_center"
    title = "Command Center"
    keyword = None
    weight = 1.0
    auto = False

    def _actions(self) -> list[CenterAction]:
        def tools(tab: str):
            def open_page():
                self.hooks.open_tools(tab)
                self.hooks.hide_launcher()
            return open_page

        def settings(page: str):
            def open_page():
                self.hooks.open_settings(page)
                self.hooks.hide_launcher()
            return open_page

        def toggle_widget(widget: str):
            def toggle():
                key = f"widgets.{widget}_enabled"
                enabled = not bool(self.config.get(key, True))
                self.config.set(key, enabled)
                self.hooks.notify(f"{widget.title()} widget {'enabled' if enabled else 'disabled'}")
                self.hooks.hide_launcher()
            return toggle

        return [
            CenterAction("Open settings", "General preferences and application settings", "Settings", settings("general")),
            CenterAction("Search settings", "Configure providers, keywords and ranking", "Settings", settings("search")),
            CenterAction("File settings", "Indexed folders, content search and exclusions", "Settings", settings("files")),
            CenterAction("Privacy settings", "Clipboard, usage tracking and retention", "Settings", settings("privacy")),
            CenterAction("System monitor", "Live hardware and system information", "System", tools("system")),
            CenterAction("Running processes", "Inspect and manage running processes", "System", tools("processes")),
            CenterAction("Network connections", "Open saved connections and quick connect", "Network", tools("connections")),
            CenterAction("Workflow manager", "Create, edit, import and run workflows", "Productivity", tools("workflows")),
            CenterAction("Text snippets", "Manage reusable local text snippets", "Productivity", tools("snippets")),
            CenterAction("Clipboard history", "Browse pinned and recent clipboard entries", "Productivity", tools("clipboard")),
            CenterAction("Quick actions", "Manage shortcuts and custom actions", "Productivity", tools("actions")),
            CenterAction("Toggle clock widget", "Show or hide the launcher clock widget", "Widgets", toggle_widget("clock")),
            CenterAction("Toggle system widget", "Show or hide the system widget", "Widgets", toggle_widget("system")),
            CenterAction("Toggle weather widget", "Show or hide the weather widget", "Widgets", toggle_widget("weather")),
            CenterAction("Toggle daily widget", "Show or hide the daily widget", "Widgets", toggle_widget("meme")),
            CenterAction("Search files", "Jump to indexed file search", "Search", lambda: self._fill("file: ")),
            CenterAction("Search file contents", "Jump to opt-in local content search", "Search", lambda: self._fill("content: ")),
            CenterAction("Search open windows", "Find and arrange open application windows", "Search", lambda: self._fill("win: ")),
            CenterAction("Minimize all windows", "Minimize application windows while protecting the shell", "Windows", lambda: self._fill("wm: minimize all")),
        ]

    def _fill(self, query: str) -> None:
        self.hooks.fill_query(query)

    def search(self, query: str, limit: int) -> list[SearchResult]:
        actions = self._actions()
        text = (query or "").strip()
        scored = []
        for action in actions:
            score = 1.0 if not text else max(
                fuzzy_score(text, action.title, typo_tolerance=True),
                fuzzy_score(text, action.description, typo_tolerance=True) * 0.8,
                fuzzy_score(text, action.category, typo_tolerance=True) * 0.7,
            )
            if score > 0:
                scored.append((score, action))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [
            self.make_result(
                title=action.title,
                subtitle=action.description,
                category=action.category,
                score=score,
                primary=action.callback,
                icon_glyph="⌘",
            )
            for score, action in scored[:limit]
        ]

    def empty_help(self) -> SearchResult | None:
        return self.make_result(
            title="Command Center",
            subtitle="Search settings, system tools, workflows, snippets and widgets",
            category="Command Center",
            score=1.0,
            primary=lambda: self.hooks.fill_query("> "),
            icon_glyph="⌘",
        )


__all__ = ["CommandCenterProvider", "CenterAction"]
