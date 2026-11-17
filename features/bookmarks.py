"""Browser bookmark search."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from core.config_manager import ConfigManager
from core.database import Database
from core.fuzzy import fuzzy_score
from core.logging_setup import get_logger
from core.models import ResultAction, SearchResult
from core.search_engine import SearchProvider

log = get_logger(__name__)

_CACHE: dict[str, Any] = {"loaded_at": 0.0, "bookmarks": []}
_CACHE_TTL = 60.0


def _chromium_roots() -> list[tuple[str, Path]]:
    roots: list[tuple[str, Path]] = []
    if os.name == "nt":
        local_appdata = os.environ.get("LOCALAPPDATA", "").strip()
        roaming_appdata = os.environ.get("APPDATA", "").strip()
        local = Path(local_appdata) if local_appdata else None
        roaming = Path(roaming_appdata) if roaming_appdata else None
        candidates: list[tuple[str, Path]] = []
        if local is not None:
            candidates.extend(
                [
                    ("Chrome", local / "Google" / "Chrome" / "User Data"),
                    ("Edge", local / "Microsoft" / "Edge" / "User Data"),
                    ("Brave", local / "BraveSoftware" / "Brave-Browser" / "User Data"),
                    ("Vivaldi", local / "Vivaldi" / "User Data"),
                ]
            )
        if roaming is not None:
            candidates.append(("Opera", roaming / "Opera Software" / "Opera Stable"))
    elif sys.platform == "darwin":
        support = Path.home() / "Library" / "Application Support"
        candidates = [
            ("Chrome", support / "Google" / "Chrome"),
            ("Edge", support / "Microsoft Edge"),
            ("Brave", support / "BraveSoftware" / "Brave-Browser"),
        ]
    else:
        config = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
        candidates = [
            ("Chrome", config / "google-chrome"),
            ("Chromium", config / "chromium"),
            ("Edge", config / "microsoft-edge"),
            ("Brave", config / "BraveSoftware" / "Brave-Browser"),
        ]
    for browser, root in candidates:
        if root.is_dir():
            roots.append((browser, root))
    return roots


def _firefox_roots() -> list[Path]:
    if os.name == "nt":
        appdata = os.environ.get("APPDATA", "").strip()
        if not appdata:
            return []
        base = Path(appdata) / "Mozilla" / "Firefox" / "Profiles"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "Firefox" / "Profiles"
    else:
        base = Path.home() / ".mozilla" / "firefox"
    if not base.is_dir():
        return []
    return [path for path in base.iterdir() if path.is_dir()]


def _walk_chromium_node(node: dict, browser: str, output: list[dict]) -> None:
    if not isinstance(node, dict):
        return
    node_type = node.get("type")
    if node_type == "url" and node.get("url"):
        output.append(
            {
                "browser": browser,
                "title": node.get("name") or node.get("url"),
                "url": node["url"],
            }
        )
    for child in node.get("children", []) or []:
        _walk_chromium_node(child, browser, output)


def _read_chromium_bookmarks(browser: str, root: Path) -> list[dict]:
    """Read a Chromium bookmark file, falling back to its last good backup."""
    bookmarks: list[dict] = []
    profiles = [root] if (root / "Bookmarks").exists() or (root / "Bookmarks.bak").exists() else []
    if not profiles:
        try:
            profiles = [
                path for path in root.iterdir()
                if path.is_dir() and ((path / "Bookmarks").exists() or (path / "Bookmarks.bak").exists())
            ]
        except OSError:
            profiles = []
    for profile in profiles:
        file = profile / "Bookmarks"
        payload = None
        for candidate in (file, profile / "Bookmarks.bak"):
            try:
                candidate_payload = json.loads(candidate.read_text(encoding="utf-8", errors="replace"))
                if isinstance(candidate_payload, dict):
                    payload = candidate_payload
                    break
                log.debug("Ignoring invalid %s bookmark snapshot %s", browser, candidate)
            except (OSError, json.JSONDecodeError) as exc:
                log.debug("Could not read %s bookmark snapshot %s: %s", browser, candidate, exc)
        if not isinstance(payload, dict):
            log.info("No readable %s bookmark snapshot at %s", browser, profile)
            continue
        roots = payload.get("roots", {})
        if isinstance(roots, dict):
            for node in roots.values():
                _walk_chromium_node(node, browser, bookmarks)
    return bookmarks

def _read_firefox_bookmarks(profile: Path) -> list[dict]:
    """Read a consistent Firefox bookmark snapshot, including live WAL data.

    SQLite's backup API provides a transactionally consistent snapshot while
    Firefox is running. It is safer than copying the database and WAL files
    separately, which can race with browser writes.
    """
    source = profile / "places.sqlite"
    if not source.is_file():
        return []
    bookmarks: list[dict] = []
    temporary: str | None = None
    for attempt in range(3):
        source_connection = None
        snapshot_connection = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite") as handle:
                temporary = handle.name
            source_connection = sqlite3.connect(
                source.as_uri() + "?mode=ro", uri=True, timeout=3.0
            )
            snapshot_connection = sqlite3.connect(temporary, timeout=3.0)
            source_connection.backup(snapshot_connection, pages=256, sleep=0.05)
            rows = snapshot_connection.execute(
                "SELECT b.title, p.url FROM moz_bookmarks b "
                "JOIN moz_places p ON b.fk = p.id "
                "WHERE b.type = 1 AND p.url IS NOT NULL"
            ).fetchall()
            for title, url in rows:
                if url:
                    bookmarks.append({"browser": "Firefox", "title": title or url, "url": url})
            return bookmarks
        except (OSError, sqlite3.Error) as exc:
            if attempt == 2:
                log.info("Could not snapshot Firefox bookmarks at %s: %s", source, exc)
            else:
                time.sleep(0.12 * (attempt + 1))
        finally:
            if snapshot_connection is not None:
                snapshot_connection.close()
            if source_connection is not None:
                source_connection.close()
            if temporary:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass
                temporary = None
    return bookmarks

def load_bookmarks(refresh: bool = False) -> list[dict]:
    """Load bookmarks from all detected browsers (cached for 60 s)."""
    now = time.time()
    if not refresh and _CACHE["bookmarks"] and now - _CACHE["loaded_at"] < _CACHE_TTL:
        return list(_CACHE["bookmarks"])
    bookmarks: list[dict] = []
    for browser, root in _chromium_roots():
        bookmarks.extend(_read_chromium_bookmarks(browser, root))
    for profile in _firefox_roots():
        bookmarks.extend(_read_firefox_bookmarks(profile))
    seen: set[str] = set()
    unique = []
    for bookmark in bookmarks:
        url = bookmark.get("url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        unique.append(bookmark)
    _CACHE["bookmarks"] = unique
    _CACHE["loaded_at"] = now
    return list(unique)


def search_bookmarks(query: str, limit: int = 10) -> list[dict]:
    bookmarks = load_bookmarks()
    text = (query or "").strip()
    if not text:
        return bookmarks[:limit]
    scored = []
    for bookmark in bookmarks:
        score = fuzzy_score(text, bookmark["title"], typo_tolerance=True)
        if score <= 0:
            score = fuzzy_score(text, bookmark["url"], typo_tolerance=False) * 0.7
        if score > 0:
            scored.append((score, bookmark))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [bookmark for _, bookmark in scored[:limit]]


class BookmarksProvider(SearchProvider):
    """The ``bm`` keyword."""

    id = "bookmarks"
    title = "Bookmarks"
    keyword = "bm"
    weight = 0.9
    auto = False

    def search(self, query: str, limit: int) -> list[SearchResult]:
        bookmarks = search_bookmarks(query, limit)
        if not bookmarks:
            return [
                self.make_result(
                    title="No bookmarks found",
                    subtitle="SeekR reads Chrome, Edge, Brave, Vivaldi and Firefox bookmark files",
                    category="Bookmark",
                    score=0.75,
                    actions=[ResultAction("Open bookmark manager", lambda: self.hooks.open_tools("bookmarks"))],
                    icon_glyph="🔖",
                )
            ]
        return [self._result(bookmark, 0.9 - index * 0.02) for index, bookmark in enumerate(bookmarks)]

    def _result(self, bookmark: dict, score: float) -> SearchResult:
        return self.make_result(
            title=bookmark.get("title", bookmark.get("url", "")),
            subtitle=f"{bookmark.get('browser', 'Browser')}  ·  {bookmark.get('url', '')}",
            category="Bookmark",
            score=score,
            primary=lambda: self._open(bookmark),
            actions=[
                ResultAction("Copy URL", lambda: self.hooks.copy_text(bookmark.get("url", ""))),
                ResultAction("Open bookmark manager", lambda: self.hooks.open_tools("bookmarks")),
            ],
            copy_text=bookmark.get("url", ""),
            icon_glyph="🔖",
            meta={"bookmark": bookmark},
        )

    def _open(self, bookmark: dict) -> None:
        if self.hooks.open_url(bookmark.get("url", "")):
            self.hooks.hide_launcher()
        else:
            self.hooks.show_error("Could not open bookmark", bookmark.get("url", ""))

    def empty_help(self) -> SearchResult | None:
        return self.make_result(
            title="Bookmark search",
            subtitle="Search bookmarks from installed browsers",
            category="Bookmark",
            score=1.0,
            primary=lambda: self.hooks.open_tools("bookmarks"),
            icon_glyph="🔖",
        )


__all__ = ["load_bookmarks", "search_bookmarks", "BookmarksProvider"]
