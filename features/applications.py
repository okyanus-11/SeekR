"""Application discovery, search and launching."""

from __future__ import annotations

import os
import math
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Iterable

from core.config_manager import ConfigManager
from core.database import Database
from core.fuzzy import fuzzy_score
from core.logging_setup import get_logger
from core.models import ResultAction, SearchResult
from core.search_engine import SearchProvider

from . import util

log = get_logger(__name__)

_SHORTCUT_SUFFIXES = (" - shortcut", " shortcut", ".lnk", ".url", ".appref-ms")
_SKIP_EXE_MARKERS = (
    "unins",
    "uninstall",
    "setup",
    "update",
    "vc_redist",
    "crashpad",
    "helper",
    "report",
)


def start_menu_directories() -> list[Path]:
    """Return existing Start Menu (or XDG application) directories."""
    directories: list[Path] = []
    if os.name == "nt":
        program_data = os.environ.get("ProgramData", r"C:\ProgramData")
        app_data = os.environ.get("APPDATA", "")
        candidates = [
            Path(program_data) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
            Path(app_data) / "Microsoft" / "Windows" / "Start Menu" / "Programs" if app_data else None,
        ]
    else:
        candidates = [
            Path("/usr/share/applications"),
            Path("/usr/local/share/applications"),
            Path.home() / ".local" / "share" / "applications",
            Path("/var/lib/flatpak/exports/share/applications"),
            Path.home() / ".local" / "share" / "flatpak" / "exports" / "share" / "applications",
        ]
    for candidate in candidates:
        if candidate is not None and candidate.is_dir():
            directories.append(candidate)
    return directories


def _clean_name(stem: str) -> str:
    name = stem.strip()
    lowered = name.lower()
    for suffix in _SHORTCUT_SUFFIXES:
        if lowered.endswith(suffix):
            name = name[: -len(suffix)].strip()
            lowered = name.lower()
    return name or stem


def _read_desktop_entry(path: Path) -> dict | None:
    """Parse a freedesktop ``.desktop`` file into an application record."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    in_entry = False
    fields: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("["):
            in_entry = line == "[Desktop Entry]"
            continue
        if not in_entry or not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        fields.setdefault(key.strip(), value.strip())
    if fields.get("Type", "Application") != "Application":
        return None
    if fields.get("NoDisplay", "").lower() == "true" or not fields.get("Exec"):
        return None
    exec_line = re.sub(r"%[fFuUidDnNvmk]", "", fields["Exec"]).strip()
    name = fields.get("Name") or _clean_name(path.stem)
    icon = fields.get("Icon", "")
    if icon and not os.path.isabs(icon):
        icon = ""  # resolved through the icon theme at runtime
    return {
        "name": name,
        "path": str(path),
        "source": "desktop",
        "args": exec_line,
        "icon_path": icon,
    }


class AppService:
    """Discovers installed applications and launches them."""

    def __init__(self, config: ConfigManager, db: Database):
        self.config = config
        self.db = db
        self.indexing = False

    # -------------------------------------------------------------- indexing
    def scan(self, progress: Callable[[int, str], None] | None = None) -> list[dict]:
        """Scan the Start Menu (or XDG menus) and return application records."""
        entries: list[dict] = []
        seen_paths: set[str] = set()
        use_start_menu = bool(self.config.get("applications.index_start_menu", True))
        directories = start_menu_directories() if use_start_menu else []
        total = max(1, len(directories))

        for index, directory in enumerate(directories):
            if progress:
                progress(int(index / total * 50), f"Scanning {directory.name}")
            try:
                iterator = directory.rglob("*.desktop") if os.name != "nt" else directory.rglob("*.lnk")
                for path in iterator:
                    try:
                        if not path.is_file():
                            continue
                        key = str(path.resolve())
                        if key in seen_paths:
                            continue
                        seen_paths.add(key)
                        if os.name == "nt":
                            record = {
                                "name": _clean_name(path.stem),
                                "path": str(path),
                                "source": "start_menu",
                                "args": "",
                                "icon_path": str(path),
                            }
                        else:
                            record = _read_desktop_entry(path)
                        if record:
                            entries.append(record)
                    except OSError:
                        continue
            except OSError as exc:
                log.warning("Could not scan %s: %s", directory, exc)

        custom_directories = self._custom_directories()
        if custom_directories:
            if progress:
                progress(45, "Scanning additional application folders")
            entries.extend(self._scan_custom_directories(custom_directories, progress))

        if os.name == "nt" and self.config.get("applications.scan_program_files", False):
            if progress:
                progress(55, "Scanning Program Files")
            entries.extend(self._scan_program_files(progress))

        # De-duplicate by (name, path) so identical menu entries collapse.
        unique: dict[tuple[str, str], dict] = {}
        for entry in entries:
            unique[(entry["name"].lower(), entry["path"].lower())] = entry
        result = list(unique.values())
        if progress:
            progress(80, f"Discovered {len(result)} applications")
        return result

    def _custom_directories(self) -> list[Path]:
        directories: list[Path] = []
        for raw in self.config.get("applications.directories", []) or []:
            text = str(raw).strip()
            if not text:
                continue
            path = Path(text).expanduser()
            if path.is_dir():
                directories.append(path)
        return directories

    def _scan_custom_directories(
        self,
        roots: list[Path],
        progress: Callable[[int, str], None] | None = None,
    ) -> list[dict]:
        """Scan user-chosen folders for shortcuts and executables."""
        entries: list[dict] = []
        seen: set[str] = set()
        suffixes = {".lnk", ".exe"} if os.name == "nt" else {".desktop"}
        for root in roots:
            for current, dirnames, filenames in os.walk(root, onerror=lambda _error: None):
                depth = current[len(str(root)):].count(os.sep)
                if depth >= 4:
                    dirnames[:] = []
                dirnames[:] = [name for name in dirnames if not name.startswith(".")]
                for filename in filenames:
                    suffix = Path(filename).suffix.lower()
                    if suffix not in suffixes:
                        continue
                    if suffix == ".exe" and any(
                        marker in filename.lower() for marker in _SKIP_EXE_MARKERS
                    ):
                        continue
                    full = Path(current) / filename
                    key = str(full).lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    if suffix == ".desktop":
                        record = _read_desktop_entry(full)
                    else:
                        record = {
                            "name": _clean_name(full.stem),
                            "path": str(full),
                            "source": "custom",
                            "args": "",
                            "icon_path": str(full),
                        }
                    if record:
                        entries.append(record)
            if progress:
                progress(50, f"Found {len(entries)} items in additional folders")
        return entries

    def _scan_program_files(
        self,
        progress: Callable[[int, str], None] | None = None,
        roots: list[Path] | None = None,
    ) -> list[dict]:
        """Optionally index executables below Program Files (depth limited)."""
        if roots is None:
            roots = []
            for variable, fallback in (
                ("ProgramFiles", r"C:\Program Files"),
                ("ProgramFiles(x86)", r"C:\Program Files (x86)"),
            ):
                value = os.environ.get(variable, fallback).strip()
                if value:
                    roots.append(Path(value))
            local_appdata = os.environ.get("LOCALAPPDATA", "").strip()
            if local_appdata:
                roots.append(Path(local_appdata) / "Programs")

        found: list[dict] = []
        seen: set[str] = set()
        limit = 4000
        for root in roots:
            if not root or not root.is_dir():
                continue
            def _on_error(error: OSError) -> None:
                log.debug("Skipping unreadable folder during app scan: %s", error)

            for current, dirs, files in os.walk(root, onerror=_on_error):
                depth = current[len(str(root)) :].count(os.sep)
                if depth >= 4:
                    dirs[:] = []
                dirs[:] = [
                    d
                    for d in dirs
                    if not d.startswith(".")
                    and d.lower() not in {"installer", "resources", "windowsapps", "$recycle.bin"}
                ]
                for filename in files:
                    if not filename.lower().endswith(".exe"):
                        continue
                    lowered = filename.lower()
                    if any(marker in lowered for marker in _SKIP_EXE_MARKERS):
                        continue
                    full = os.path.join(current, filename)
                    key = full.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    found.append(
                        {
                            "name": _clean_name(Path(filename).stem),
                            "path": full,
                            "source": "program_files",
                            "args": "",
                            "icon_path": full,
                        }
                    )
                    if len(found) >= limit:
                        break
                if len(found) >= limit:
                    break
            if progress:
                progress(70, f"Found {len(found)} executables")
            if len(found) >= limit:
                break
        return found

    def refresh(self, progress: Callable[[int, str], None] | None = None) -> dict:
        """Rebuild the application cache and return statistics."""
        if self.indexing:
            return {"found": self.db.count_apps(), "written": 0, "seconds": 0.0}
        self.indexing = True
        try:
            return self._refresh(progress)
        finally:
            self.indexing = False

    def _refresh(self, progress: Callable[[int, str], None] | None = None) -> dict:
        started = time.perf_counter()
        entries = self.scan(progress)
        excluded = {str(item).lower() for item in self.config.get("applications.excluded", [])}
        filtered = [
            entry
            for entry in entries
            if entry["name"].lower() not in excluded and entry["path"].lower() not in excluded
        ]
        written = self.db.upsert_apps(filtered, prune_missing=True)
        self.db.set_meta("apps_last_index", time.time())
        elapsed = time.perf_counter() - started
        stats = {"found": len(filtered), "written": written, "seconds": elapsed}
        log.info("Application index refreshed: %s", stats)
        if progress:
            progress(100, f"Indexed {len(filtered)} applications in {elapsed:.2f}s")
        return stats

    def excluded(self) -> set[str]:
        return {str(item).lower() for item in self.config.get("applications.excluded", [])}

    def is_excluded(self, app: dict) -> bool:
        excluded = self.excluded()
        return app.get("name", "").lower() in excluded or app.get("path", "").lower() in excluded

    # ---------------------------------------------------------------- search
    def _aliases_for(self, app: dict) -> list[str]:
        aliases = self.config.get("applications.aliases", {}) or {}
        if not isinstance(aliases, dict):
            return []
        keys = (app.get("name", "").lower(), app.get("path", "").lower())
        collected: list[str] = []
        for key, values in aliases.items():
            if str(key).lower() in keys:
                collected.extend(str(value) for value in values)
        return collected

    def search(self, query: str, limit: int = 8) -> list[dict]:
        """Return applications ranked by fuzzy relevance."""
        text = (query or "").strip()
        if not text:
            return []
        candidates = self.db.app_candidates(text[:40], limit=600)
        # Keep interactive searches bounded. Falling back to all_apps() when a
        # short LIKE query finds few matches makes every typo/partial keystroke
        # scan and fuzzy-rank the entire installed-app database.
        typo = bool(self.config.get("search.typo_tolerance", True))
        prioritize = (bool(self.config.get("search.prioritize_recent", True)) and bool(self.config.get("privacy.usage_tracking", False)))
        now = time.time()
        scored: list[tuple[float, dict]] = []
        for app in candidates:
            if self.is_excluded(app):
                continue
            score = fuzzy_score(text, app["name"], typo_tolerance=typo)
            for alias in self._aliases_for(app):
                score = max(score, fuzzy_score(text, alias, typo_tolerance=typo) * 0.98)
            if score <= 0:
                continue
            if prioritize:
                uses = min(int(app.get("use_count") or 0), 25)
                score += uses * 0.004
                last_used = float(app.get("last_used") or 0)
                if last_used and now - last_used < 86400 * 7:
                    score += 0.04
                elif last_used > 0:
                    score += 0.01
            scored.append((min(1.0, score), app))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [app for _, app in scored[:limit]]

    def suggestions(self, limit: int = 4) -> list[dict]:
        if not self.config.get("smart_suggestions.enabled", True):
            return []
        if not self.config.get("privacy.usage_tracking", False):
            return []
        recent = self.db.recent_apps(limit)
        frequent = self.db.frequent_apps(limit)
        merged: list[dict] = []
        seen: set[str] = set()
        for app in recent + frequent:
            if app["path"] in seen or self.is_excluded(app):
                continue
            seen.add(app["path"])
            merged.append(app)
            if len(merged) >= limit:
                break
        return merged

    # --------------------------------------------------------------- launching
    def launch(self, app: dict, elevated: bool = False) -> tuple[bool, str]:
        """Launch an application; returns ``(success, message)``."""
        path = app.get("path", "")
        source = app.get("source", "")
        if not path:
            return False, "This entry has no launch path"

        if source == "desktop":
            command = app.get("args") or path
            args = util.split_args(command)
            if not args:
                return False, "The desktop entry has no command"
            ok, message = util.run_detached(args)
        elif os.name == "nt":
            if not Path(path).exists():
                return False, f"Application not found: {path}"
            try:
                os.startfile(path, "runas" if elevated else "open")  # type: ignore[attr-defined]
                ok, message = True, f"Launched {app.get('name', path)}"
            except OSError as exc:
                log.error("Could not launch %s: %s", path, exc)
                return False, f"Could not launch {app.get('name', path)}: {exc}"
        else:
            if not Path(path).exists():
                return False, f"Application not found: {path}"
            args = util.split_args(app.get("args") or "") or []
            ok, message = util.run_detached([path, *args])

        if ok and self.config.get("privacy.usage_tracking", False):
            self.db.record_app_launch(path)
            self.db.add_history("app", app.get("name") or path)
        return ok, message

    def open_location(self, app: dict) -> tuple[bool, str]:
        return util.reveal_path_platform(app.get("path", ""))

    def refresh_needed(self) -> bool:
        last = self.db.get_meta("apps_last_index")
        if not last:
            return True
        hours = float(self.config.get("applications.refresh_interval_hours", 24) or 24)
        try:
            return (time.time() - float(last)) > hours * 3600
        except ValueError:
            return True

    def recent_names(self, limit: int = 8) -> list[str]:
        return [entry["value"] for entry in self.db.history("app", limit)]


class ApplicationsProvider(SearchProvider):
    """``app:`` keyword plus default application results."""

    id = "applications"
    title = "Applications"
    keyword = "app"
    weight = 1.15
    auto = True

    def __init__(self, config, db, hooks, service: AppService | None = None):
        super().__init__(config, db, hooks)
        self.service = service or AppService(config, db)

    _last_index_request = 0.0

    def search(self, query: str, limit: int) -> list[SearchResult]:
        if not query.strip():
            return self.suggestions(limit)
        if self.db.count_apps() == 0 and self.service.refresh_needed():
            # Never walk the Start Menu on the GUI thread. Ask the controller
            # for a background refresh (throttled) and explain the state.
            self._request_index()
            return [self._indexing_result()]
        apps = self.service.search(query, limit)
        return [self._result(app, score) for score, app in self._scored(query, apps, limit, self.config)]

    def _request_index(self) -> None:
        now = time.monotonic()
        if self.service.indexing or now - self._last_index_request < 30.0:
            return
        self._last_index_request = now
        try:
            self.hooks.refresh_indexes("applications")
        except Exception:
            log.debug("Could not request an application index", exc_info=True)

    def _indexing_result(self) -> SearchResult:
        return self.make_result(
            title="Indexing applications…",
            subtitle="SeekR is discovering Start Menu shortcuts in the background",
            category="Application",
            score=1.0,
            primary=lambda: self.hooks.refresh_indexes("applications"),
            icon_glyph="▣",
        )

    @staticmethod
    def _scored(query: str, apps: Iterable[dict], limit: int, config=None):
        from core.fuzzy import fuzzy_score

        results = []
        for index, app in enumerate(apps):
            score = max(0.25, fuzzy_score(query, app["name"], typo_tolerance=True))
            results.append((min(1.0, score - index * 0.01), app))
        return results[:limit]

    def _result(self, app: dict, score: float) -> SearchResult:
        launch = lambda: self._launch(app)  # noqa: E731
        actions = [
            ResultAction("Open file location", lambda: self.hooks.reveal_path(app.get("path", "")), hint="Show in folder"),
            ResultAction("Copy path", lambda: self.hooks.copy_text(app.get("path", ""))),
        ]
        if os.name == "nt":
            actions.append(ResultAction("Run as administrator", lambda: self._launch(app, elevated=True)))
        return self.make_result(
            title=app.get("name") or Path(app.get("path", "")).stem,
            subtitle=app.get("path", ""),
            category="Application",
            score=score,
            primary=launch,
            actions=actions,
            copy_text=app.get("path", ""),
            icon_path=app.get("path", ""),
            icon_glyph="▣",
            meta={"path": app.get("path", ""), "app": app},
        )

    def _launch(self, app: dict, elevated: bool = False) -> None:
        ok, message = self.service.launch(app, elevated=elevated)
        self.hooks.notify(message, "info" if ok else "error")
        if ok:
            self.hooks.hide_launcher()

    def suggestions(self, limit: int) -> list[SearchResult]:
        apps = self.service.suggestions(min(limit, 4))
        return [self._result(app, 0.6 - index * 0.03) for index, app in enumerate(apps)]

    def empty_help(self) -> SearchResult | None:
        if self.db.count_apps() == 0:
            return self.make_result(
                title="No applications indexed yet",
                subtitle="Run an application index refresh to discover installed apps",
                category="Application",
                score=1.0,
                primary=lambda: self.hooks.refresh_indexes("applications"),
                icon_glyph="▣",
            )
        return None


__all__ = ["AppService", "ApplicationsProvider", "start_menu_directories"]
