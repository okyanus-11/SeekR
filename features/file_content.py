"""Explicit, local full-text search across configured indexed text files."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from core.config_manager import ConfigManager
from core.database import Database
from core.models import ResultAction, SearchResult
from core.search_engine import SearchProvider
from core.logging_setup import get_logger

log = get_logger(__name__)
DEFAULT_CONTENT_EXTENSIONS = [".txt", ".md", ".py", ".json", ".csv", ".html", ".xml"]
MAX_CANDIDATES = 500
MAX_TOTAL_READ_BYTES = 8_000_000
DEFAULT_MAX_FILE_BYTES = 1_000_000


class FileContentProvider(SearchProvider):
    """Search the contents of explicitly configured, indexed text files via content:."""

    id = "file_content"
    title = "File contents"
    keyword = "content"
    weight = 0.9
    auto = False

    def search(self, query: str, limit: int) -> list[SearchResult]:
        text = (query or "").strip()
        if not bool(self.config.get("files.content_search_enabled", False)):
            return [self.make_result(
                title="File content search is disabled",
                subtitle="Enable it in Settings → Files. Searches stay local and only read configured text extensions.",
                category="File content", score=1.0,
                primary=lambda: self.hooks.open_settings("files"), icon_glyph="⌕",
            )]
        if not text:
            return [self.make_result(
                title="Search inside indexed text files",
                subtitle="Use content: followed by a word or phrase. Only configured folders and extensions are read.",
                category="File content", score=1.0, icon_glyph="⌕",
            )]
        roots = [Path(item).expanduser() for item in (self.config.get("files.directories", []) or [])]
        if not roots:
            return []
        resolved_roots = [root.resolve() for root in roots]
        extensions = {
            str(ext).lower() if str(ext).startswith(".") else "." + str(ext).lower()
            for ext in (self.config.get("files.content_search_extensions", DEFAULT_CONTENT_EXTENSIONS) or [])
        }
        max_bytes = min(
            10_000_000,
            max(1, int(self.config.get("files.content_search_max_file_bytes", DEFAULT_MAX_FILE_BYTES) or DEFAULT_MAX_FILE_BYTES)),
        )
        if len(text) > 512:
            return []
        candidates = self.db.recent_files(MAX_CANDIDATES, [str(root) for root in roots])
        needle = text.casefold()
        matches: list[tuple[int, dict[str, Any], str]] = []
        bytes_read = 0
        for row in candidates:
            remaining_budget = MAX_TOTAL_READ_BYTES - bytes_read
            if remaining_budget <= 0:
                break
            if row.get("is_dir") or str(row.get("ext", "")).lower() not in extensions:
                continue
            path = Path(str(row.get("path", "")))
            try:
                resolved = path.resolve(strict=True)
                if not resolved.is_file() or resolved.stat().st_size > max_bytes:
                    continue
                if not any(resolved.is_relative_to(root) for root in resolved_roots):
                    continue
                read_limit = min(max_bytes, remaining_budget)
                # Bound the read itself, not just stat() checks: a file can
                # grow between stat and open. This provider runs on the search
                # path, so total disk I/O must remain predictable.
                with resolved.open("rb") as handle:
                    raw = handle.read(read_limit)
                bytes_read += len(raw)
                encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
                content = raw.decode(encoding)
            except (OSError, UnicodeError, RuntimeError, ValueError):
                continue
            position = content.casefold().find(needle)
            if position < 0:
                continue
            excerpt = " ".join(content[max(0, position - 90):position + len(needle) + 150].split())
            matches.append((position, row, excerpt))
            if len(matches) >= limit:
                break
        return [self._result(row, excerpt, 0.95 - index * 0.025)
                for index, (_position, row, excerpt) in enumerate(matches)]

    def _result(self, row: dict[str, Any], excerpt: str, score: float) -> SearchResult:
        path = str(row.get("path", ""))
        return self.make_result(
            title=str(row.get("name", Path(path).name)),
            subtitle=f"{path}\n{excerpt}",
            category="File content",
            score=score,
            primary=lambda: self.hooks.open_path(path),
            actions=[
                ResultAction("Preview file", lambda: self.hooks.preview(path)),
                ResultAction("Copy path", lambda: self.hooks.copy_text(path)),
            ],
            copy_text=path,
            icon_glyph="¶",
            meta={"path": path, "excerpt": excerpt},
        )

    def empty_help(self) -> SearchResult | None:
        return self.make_result(
            title="Search inside files",
            subtitle="Enable content search in Settings → Files, then use content: phrase",
            category="File content", score=1.0,
            primary=lambda: self.hooks.open_settings("files"), icon_glyph="⌕",
        )


__all__ = ["FileContentProvider", "DEFAULT_CONTENT_EXTENSIONS", "DEFAULT_MAX_FILE_BYTES"]
