"""File and folder indexing and search."""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Callable, Iterable

from core.config_manager import ConfigManager
from core.database import Database
from core.fuzzy import fuzzy_score
from core.logging_setup import get_logger
from core.models import ResultAction, SearchResult
from core.search_engine import SearchProvider
from core.workers import CancelToken

from . import util

log = get_logger(__name__)

_EXT_TOKEN = re.compile(r"\bext:([A-Za-z0-9]+)\b", re.IGNORECASE)
_BATCH_SIZE = 400
_FILE_ATTRIBUTE_HIDDEN = 0x2
_FILE_ATTRIBUTE_SYSTEM = 0x4
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400


def _stat_attributes(stat_result) -> int:
    return int(getattr(stat_result, "st_file_attributes", 0) or 0)


def _windows_hidden(stat_result) -> bool:
    """True for hidden/system entries on Windows (dot-prefix handled elsewhere)."""
    attributes = _stat_attributes(stat_result)
    return bool(attributes & (_FILE_ATTRIBUTE_HIDDEN | _FILE_ATTRIBUTE_SYSTEM))


def _is_reparse_directory(entry) -> bool:
    """Detect junctions/symlinks so indexing cannot follow a cycle."""
    try:
        if entry.is_symlink():
            return True
        attributes = _stat_attributes(entry.stat(follow_symlinks=False))
        return bool(attributes & _FILE_ATTRIBUTE_REPARSE_POINT)
    except OSError:
        return True


class FileIndexer:
    """Walks configured directories and stores metadata in SQLite."""

    def __init__(self, config: ConfigManager, db: Database):
        self.config = config
        self.db = db

    def _excluded_dirs(self) -> set[str]:
        return {name.lower() for name in self.config.get("files.excluded_dirs", [])}

    def _excluded_extensions(self) -> set[str]:
        extensions = set()
        for extension in self.config.get("files.excluded_extensions", []):
            cleaned = str(extension).strip().lower()
            if not cleaned:
                continue
            if not cleaned.startswith("."):
                cleaned = f".{cleaned}"
            extensions.add(cleaned)
        return extensions

    def index(
        self,
        progress: Callable[[int, str], None] | None = None,
        token: CancelToken | None = None,
        clear: bool = True,
    ) -> dict:
        """Index every configured directory. Safe to run on a worker thread."""
        if not self.config.get("files.enabled", True):
            return {"indexed": 0, "directories": 0, "cancelled": False, "seconds": 0.0}

        directories = [d for d in self.config.get("files.directories", []) if d]
        include_hidden = bool(self.config.get("files.include_hidden", False))
        include_folders = bool(self.config.get("files.include_folders", True))
        max_depth = int(self.config.get("files.max_depth", 10) or 10)
        max_files = int(self.config.get("files.max_files", 200000) or 200000)
        excluded_dirs = self._excluded_dirs()
        excluded_extensions = self._excluded_extensions()

        started = time.perf_counter()
        if clear:
            self.db.clear_files()
        self.db.set_meta("files_index_started", started)

        inserted = 0
        batch: list[dict] = []
        cancelled = False
        limit_reached = False
        visited_dirs = 0

        def flush() -> None:
            nonlocal inserted
            if batch:
                self.db.upsert_files(batch)
                inserted += len(batch)
                batch.clear()

        for root_index, root in enumerate(directories):
            root_path = Path(root)
            if not root_path.is_dir():
                log.info("Skipping missing index directory %s", root)
                continue
            stack: list[tuple[str, int]] = [(str(root_path), 0)]
            while stack:
                if token is not None and token.cancelled:
                    cancelled = True
                    break
                directory, depth = stack.pop()
                visited_dirs += 1
                if progress and visited_dirs % 25 == 0:
                    percent = int((root_index / max(1, len(directories))) * 100)
                    progress(min(99, percent), f"Indexing {util.truncate_middle(directory, 70)}  ({inserted} items)")
                try:
                    iterator = os.scandir(directory)
                except OSError:
                    continue
                with iterator:
                    for entry in iterator:
                        if token is not None and token.cancelled:
                            cancelled = True
                            break
                        name = entry.name
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                lowered = name.lower()
                                if lowered in excluded_dirs:
                                    continue
                                if not include_hidden:
                                    if name.startswith("."):
                                        continue
                                    if os.name == "nt" and _windows_hidden(entry.stat(follow_symlinks=False)):
                                        continue
                                if include_folders:
                                    batch.append(
                                        {
                                            "path": entry.path,
                                            "name": name,
                                            "dir": directory,
                                            "ext": "",
                                            "is_dir": True,
                                            "size": 0,
                                            "mtime": 0.0,
                                        }
                                    )
                                if depth < max_depth and not _is_reparse_directory(entry):
                                    stack.append((entry.path, depth + 1))
                            elif entry.is_file(follow_symlinks=False):
                                extension = os.path.splitext(name)[1].lower()
                                if extension in excluded_extensions:
                                    continue
                                stat_result = entry.stat(follow_symlinks=False)
                                if not include_hidden:
                                    if name.startswith("."):
                                        continue
                                    if os.name == "nt" and _windows_hidden(stat_result):
                                        continue
                                batch.append(
                                    {
                                        "path": entry.path,
                                        "name": name,
                                        "dir": directory,
                                        "ext": extension,
                                        "is_dir": False,
                                        "size": stat_result.st_size,
                                        "mtime": stat_result.st_mtime,
                                    }
                                )
                        except OSError:
                            continue

                        if len(batch) >= _BATCH_SIZE:
                            flush()
                        if inserted + len(batch) >= max_files:
                            log.info("File index limit of %s entries reached", max_files)
                            if progress:
                                progress(100, f"Index limit reached ({max_files} entries)")
                            flush()
                            limit_reached = True
                            stack.clear()
                            break
                if cancelled or limit_reached:
                    break
            flush()
            if cancelled or limit_reached:
                break

        flush()
        elapsed = time.perf_counter() - started
        self.db.set_meta("files_last_index", time.time())
        self.db.set_meta("files_index_cancelled", "1" if cancelled else "0")
        stats = {
            "indexed": inserted,
            "directories": visited_dirs,
            "cancelled": cancelled,
            "limit_reached": limit_reached,
            "seconds": elapsed,
        }
        log.info("File index finished: %s", stats)
        if progress:
            message = f"Indexed {inserted} items in {elapsed:.1f}s"
            if limit_reached:
                message += f" (entry limit {max_files} reached)"
            progress(100, message)
        return stats


class FileService:
    """Searches the file index and opens results."""

    PREVIEW_EXTENSIONS = {
        ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", ".ico",
        ".txt", ".md", ".markdown", ".py", ".js", ".ts", ".json", ".xml",
        ".html", ".css", ".ini", ".cfg", ".log", ".csv", ".yml", ".yaml",
        ".toml", ".sh", ".bat", ".ps1", ".c", ".h", ".cpp", ".cs", ".java",
        ".rs", ".go", ".sql", ".gitignore",
    }

    def __init__(self, config: ConfigManager, db: Database):
        self.config = config
        self.db = db

    def index(self, progress=None, token: CancelToken | None = None) -> dict:
        return FileIndexer(self.config, self.db).index(progress=progress, token=token)

    def search(self, query: str, limit: int = 6) -> list[tuple[float, dict]]:
        text = (query or "").strip()
        extension = ""
        match = _EXT_TOKEN.search(text)
        if match:
            extension = match.group(1).lower()
            if not extension.startswith("."):
                extension = f".{extension}"
            text = _EXT_TOKEN.sub("", text).strip()

        if not text:
            if extension:
                rows = self.db.files_by_extension(extension, limit=limit * 20)
                return [(0.5, row) for row in rows[:limit]]
            return []

        term = text
        candidates = self.db.file_candidates(term[:40], limit=800, ext=extension or None)
        if len(candidates) < limit and len(term) >= 3:
            # Widen using the longest word to allow typo-tolerant ranking.
            longest = max(re.split(r"\s+", term), key=len)
            if len(longest) >= 3:
                candidates = self.db.file_candidates(longest[:12], limit=800, ext=extension or None)

        typo = bool(self.config.get("search.typo_tolerance", True))
        now = time.time()
        scored: list[tuple[float, dict]] = []
        for row in candidates:
            score = fuzzy_score(text, row["name"], typo_tolerance=typo)
            if score <= 0:
                continue
            mtime = float(row.get("mtime") or 0)
            if mtime:
                age_days = max(0.0, (now - mtime) / 86400)
                if age_days < 7:
                    score += 0.04
                elif age_days < 30:
                    score += 0.02
            if row.get("is_dir"):
                score *= 0.96
            scored.append((min(1.0, score), row))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return scored[:limit]

    def suggestions(self, limit: int = 3) -> list[dict]:
        if not self.config.get("smart_suggestions.enabled", True):
            return []
        directories = [str(d) for d in self.config.get("files.directories", [])]
        return self.db.recent_files(min(limit, 3), directories)

    def stats(self) -> dict:
        last = self.db.get_meta("files_last_index")
        try:
            last_value = float(last) if last else 0.0
        except ValueError:
            last_value = 0.0
        return {
            "count": self.db.count_files(),
            "last_index": last_value,
            "directories": list(self.config.get("files.directories", [])),
            "enabled": bool(self.config.get("files.enabled", True)),
        }

    def is_previewable(self, path: str) -> bool:
        return Path(path).suffix.lower() in self.PREVIEW_EXTENSIONS


class FilesProvider(SearchProvider):
    """File search: automatic plus the ``file:`` keyword."""

    id = "files"
    title = "Files"
    keyword = "file"
    weight = 1.0
    auto = True

    def __init__(self, config, db, hooks, service: FileService | None = None):
        super().__init__(config, db, hooks)
        self.service = service or FileService(config, db)

    def search(self, query: str, limit: int) -> list[SearchResult]:
        limit = min(limit, 6)
        if not query.strip():
            rows = self.service.suggestions(limit)
            return [self._result(row, 0.55 - index * 0.03) for index, row in enumerate(rows)]
        ranked = self.service.search(query, limit)
        return [self._result(row, score) for score, row in ranked]

    def _result(self, row: dict, score: float) -> SearchResult:
        path = row.get("path", "")
        name = row.get("name", os.path.basename(path))
        is_dir = bool(row.get("is_dir"))
        subtitle_parts = [row.get("dir", "")]
        if not is_dir:
            subtitle_parts.append(util.format_bytes(row.get("size")))
        if row.get("mtime"):
            subtitle_parts.append(util.format_ago(row.get("mtime")))
        subtitle = "  ·  ".join(part for part in subtitle_parts if part)
        actions = [
            ResultAction("Open containing folder", lambda: self.hooks.reveal_path(path)),
            ResultAction("Copy path", lambda: self.hooks.copy_text(path)),
        ]
        if not is_dir and self.service.is_previewable(path):
            actions.insert(1, ResultAction("QuickLook preview", lambda: self.hooks.preview(path)))
        return self.make_result(
            title=name,
            subtitle=subtitle,
            category="Folder" if is_dir else "File",
            score=score,
            primary=lambda: self._open(path),
            actions=actions,
            copy_text=path,
            icon_path=path,
            icon_glyph="📁" if is_dir else "📄",
            meta={"path": path, "is_dir": is_dir},
        )

    def _open(self, path: str) -> None:
        ok, message = util.open_path_platform(path)
        self.hooks.notify(message, "info" if ok else "error")
        if ok:
            self.db.add_history("file", path)
            self.hooks.hide_launcher()

    def suggestions(self, limit: int) -> list[SearchResult]:
        rows = self.service.suggestions(min(limit, 3))
        return [self._result(row, 0.5 - index * 0.03) for index, row in enumerate(rows)]

    def empty_help(self) -> SearchResult | None:
        stats = self.service.stats()
        if stats["count"] == 0:
            return self.make_result(
                title="No files indexed yet",
                subtitle="Add folders in Settings → Files and run an index refresh",
                category="File",
                score=1.0,
                primary=lambda: self.hooks.open_settings("files"),
                icon_glyph="📄",
            )
        return None


__all__ = ["FileIndexer", "FileService", "FilesProvider"]
