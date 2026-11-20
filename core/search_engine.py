"""Search orchestration.

Every capability registers a :class:`SearchProvider`. The engine resolves
keyword prefixes (``calc:``, ``file:`` ...), runs automatic providers, ranks
and de-duplicates their results. New providers (including future plugins) only
need the small provider interface below, which is why plugin support can be
added later without rewriting the engine.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional

from PySide6.QtCore import QObject, Signal

from .config_manager import ConfigManager
from .constants import KEYWORDS
from .database import Database
from .hooks import UIHooks
from .logging_setup import get_logger
from .models import ResultAction, SearchResult

log = get_logger(__name__)

_KEYWORD_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", re.DOTALL)


class SearchProvider:
    """Base class for a search capability."""

    id: str = "provider"
    title: str = ""
    keyword: Optional[str] = None
    weight: float = 1.0
    auto: bool = True

    def __init__(self, config: ConfigManager, db: Database, hooks: UIHooks):
        self.config = config
        self.db = db
        self.hooks = hooks

    # ------------------------------------------------------------------ state
    def is_enabled(self) -> bool:
        disabled = self.config.get("search.disabled_providers", []) or []
        return self.id not in disabled

    @property
    def typo_tolerance(self) -> bool:
        return bool(self.config.get("search.typo_tolerance", True))

    @property
    def fuzzy_enabled(self) -> bool:
        return bool(self.config.get("search.fuzzy", True))

    def aliases(self) -> list[str]:
        """Return the configured aliases for this provider's keyword."""
        keyword = (self.keyword or "").lower()
        if not keyword:
            return []
        aliases = self.config.get("search.keyword_aliases", {}) or {}
        if not isinstance(aliases, dict):
            return []
        return [
            str(alias).lower()
            for alias, target in aliases.items()
            if str(target).lower() == keyword
        ]

    # ---------------------------------------------------------------- queries
    def search(self, query: str, limit: int) -> list[SearchResult]:
        """Return results for *query* (the text after the keyword, if any)."""
        return []

    def suggestions(self, limit: int) -> list[SearchResult]:
        """Return results for an empty query (recent items, pinned items...)."""
        return []

    def empty_help(self) -> SearchResult | None:
        """Optional hint shown when a keyword is used with no arguments."""
        return None

    # --------------------------------------------------------------- helpers
    def make_result(self, **kwargs) -> SearchResult:
        result = SearchResult(**kwargs)
        result.provider = self.id
        return result


class SearchEngine(QObject):
    """Aggregates providers, resolves keywords and ranks results."""

    results_ready = Signal(str, list)

    def __init__(self, config: ConfigManager, db: Database, hooks: UIHooks, parent: QObject | None = None):
        super().__init__(parent)
        self.config = config
        self.db = db
        self.hooks = hooks
        self._providers: dict[str, SearchProvider] = {}
        self._keyword_map_cache: dict[str, SearchProvider] | None = None
        config.subscribe(self._on_config_changed)
        self.destroyed.connect(
            lambda _obj=None: config.unsubscribe(self._on_config_changed)
        )

    # ------------------------------------------------------------- providers
    def _on_config_changed(self, key: str, _value=None) -> None:
        if key == "*" or key == "search.keyword_aliases":
            self._keyword_map_cache = None

    def register(self, provider: SearchProvider) -> None:
        self._providers[provider.id] = provider
        self._keyword_map_cache = None
        log.debug("Registered search provider %s", provider.id)

    def unregister(self, provider_id: str) -> None:
        self._providers.pop(provider_id, None)
        self._keyword_map_cache = None

    @property
    def providers(self) -> list[SearchProvider]:
        return list(self._providers.values())

    def provider(self, provider_id: str) -> SearchProvider | None:
        return self._providers.get(provider_id)

    def keyword_map(self) -> dict[str, SearchProvider]:
        """Map keywords and aliases, reusing the map until providers/settings change."""
        if self._keyword_map_cache is not None:
            return self._keyword_map_cache
        mapping: dict[str, SearchProvider] = {}
        for provider in self._providers.values():
            if provider.keyword:
                mapping[provider.keyword.lower()] = provider
            for alias in provider.aliases():
                mapping[alias.lower()] = provider
        # User aliases: {"w": "web"}.
        aliases = self.config.get("search.keyword_aliases", {}) or {}
        if isinstance(aliases, dict):
            for alias, target in aliases.items():
                provider = mapping.get(str(target).lower())
                if provider is not None and str(alias).strip():
                    mapping[str(alias).strip().lower()] = provider
        self._keyword_map_cache = mapping
        return mapping

    def resolve(self, text: str) -> tuple[SearchProvider, str] | None:
        """Split keyword queries and the leading-> command-center mode."""
        cleaned = (text or "").lstrip()
        if cleaned.startswith(">"):
            provider = self._providers.get("command_center")
            if provider is not None:
                return provider, cleaned[1:].strip()
        match = _KEYWORD_RE.match(text)
        if not match:
            return None
        word = match.group(1).lower()
        provider = self.keyword_map().get(word)
        if provider is None:
            return None
        return provider, match.group(2)

    # ---------------------------------------------------------------- search
    def search(self, text: str, limit: int | None = None) -> list[SearchResult]:
        limit = int(limit or self.config.get("search.max_results", 12) or 12)
        cleaned = (text or "").strip()
        if not cleaned:
            return self.suggestions(limit)

        resolved = self.resolve(cleaned)
        if resolved is not None:
            provider, remainder = resolved
            if not provider.is_enabled():
                return [self._disabled_notice(provider)]
            try:
                results = provider.search(remainder.strip(), limit)
            except Exception as exc:
                log.exception("Provider %s failed", provider.id)
                return [
                    SearchResult(
                        title=f"{provider.title or provider.id} is unavailable",
                        subtitle=str(exc) or "The provider raised an error",
                        category="System",
                        provider=provider.id,
                        score=1.0,
                    )
                ]
            results = self._apply_weight(results, provider)
            if not results:
                hint = provider.empty_help()
                if hint is not None:
                    hint.provider = provider.id
                    results = [hint]
            return self._finalize(results, limit)

        results: list[SearchResult] = []
        for provider in self._providers.values():
            if not provider.auto or not provider.is_enabled():
                continue
            try:
                produced = provider.search(cleaned, limit)
            except Exception:
                log.exception("Automatic provider %s failed", provider.id)
                continue
            results.extend(self._apply_weight(produced, provider))

        if self.config.get("search.auto_detect", True):
            results.extend(self._keyword_hints(cleaned))

        return self._finalize(results, limit)

    def suggestions(self, limit: int | None = None) -> list[SearchResult]:
        """Results shown before the user types anything."""
        limit = int(limit or self.config.get("search.max_results", 12) or 12)
        results: list[SearchResult] = []
        for provider in self._providers.values():
            if not provider.auto or not provider.is_enabled():
                continue
            try:
                results.extend(self._apply_weight(provider.suggestions(limit), provider))
            except Exception:
                log.exception("Suggestions from %s failed", provider.id)
        return self._finalize(results, limit)

    def keyword_reference(self) -> list[SearchResult]:
        """A result row for every registered keyword (used by ``help:``)."""
        results: list[SearchResult] = []
        for keyword, description in KEYWORDS.items():
            provider = self.keyword_map().get(keyword)
            if provider is None:
                continue
            results.append(
                SearchResult(
                    title=f"{keyword}:",
                    subtitle=description,
                    category="Keyword",
                    provider=provider.id,
                    score=0.5,
                    primary=lambda k=keyword: self.hooks.fill_query(f"{k}: "),
                    copy_text=f"{keyword}:",
                    icon_glyph="⌨",
                )
            )
        center = self._providers.get("command_center")
        if center is not None and center.is_enabled():
            results.append(
                SearchResult(
                    title=">  Command Center",
                    subtitle="Search settings, system tools, workflows, tasks, snippets and widgets",
                    category="Command Center",
                    provider=center.id,
                    score=1.0,
                    primary=lambda: self.hooks.fill_query("> "),
                    copy_text=">",
                    icon_glyph="⌘",
                )
            )
        return results

    def record_search(self, text: str) -> None:
        if not self.config.get("privacy.save_search_history", True):
            return
        cleaned = (text or "").strip()
        if not cleaned or self.resolve(cleaned) is not None:
            return
        self.db.add_history("search", cleaned)
        limit = max(1, int(self.config.get("search.history_limit", 300) or 300))
        self.db.prune_history(int(self.config.get("privacy.retention_days", 90) or 90))
        self._trim_search_history(limit)

    def _trim_search_history(self, limit: int) -> None:
        # Delete in one indexed SQLite statement. Fetching only limit + 200 rows
        # left older history behind forever once the table grew beyond that window.
        self.db._write(
            """DELETE FROM history
               WHERE kind = ? AND id NOT IN (
                   SELECT id FROM history
                   WHERE kind = ?
                   ORDER BY created DESC, id DESC
                   LIMIT ?
               )""",
            ("search", "search", max(1, int(limit))),
        )

    # --------------------------------------------------------------- helpers
    def _apply_weight(self, results: Iterable[SearchResult], provider: SearchProvider) -> list[SearchResult]:
        weighted: list[SearchResult] = []
        for result in results:
            result.provider = provider.id
            result.score = max(0.0, min(1.0, float(result.score))) * provider.weight
            weighted.append(result)
        return weighted

    def _keyword_hints(self, query: str) -> list[SearchResult]:
        """Suggest a keyword when the typed text is a prefix of one."""
        lowered = query.lower().strip()
        if not lowered or " " in lowered or ":" in lowered:
            return []
        hints: list[SearchResult] = []
        for keyword, provider in sorted(self.keyword_map().items(), key=lambda pair: len(pair[0])):
            if keyword.startswith(lowered) and keyword != lowered:
                description = KEYWORDS.get(keyword, provider.title)
                hints.append(
                    SearchResult(
                        title=f"{keyword}: {description}",
                        subtitle=f"Press Tab or Enter to use the {keyword}: keyword",
                        category="Keyword",
                        provider=provider.id,
                        score=0.42,
                        primary=lambda k=keyword: self.hooks.fill_query(f"{k}: "),
                        copy_text=f"{keyword}:",
                        icon_glyph="⌨",
                        actions=[
                            ResultAction(
                                "Use keyword",
                                lambda k=keyword: self.hooks.fill_query(f"{k}: "),
                            )
                        ],
                    )
                )
                if len(hints) >= 2:
                    break
        return hints

    def _disabled_notice(self, provider: SearchProvider) -> SearchResult:
        return SearchResult(
            title=f"{provider.title or provider.id} is disabled",
            subtitle="Enable it in Settings → Search → Providers",
            category="System",
            provider=provider.id,
            score=1.0,
            primary=lambda: self.hooks.open_settings("search"),
        )

    def _finalize(self, results: Iterable[SearchResult], limit: int) -> list[SearchResult]:
        seen: set[tuple[str, str, str]] = set()
        unique: list[SearchResult] = []
        for result in results:
            if not result.title:
                continue
            key = (result.category, result.title.lower(), result.subtitle.lower())
            if key in seen:
                continue
            seen.add(key)
            unique.append(result)
        unique.sort(key=lambda item: item.score, reverse=True)
        return unique[:limit]


__all__ = ["SearchProvider", "SearchEngine"]
