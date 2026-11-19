"""JSON configuration with defaults, validation and atomic persistence."""

from __future__ import annotations

import copy
import json
import os
import re
import threading
from pathlib import Path
from typing import Any, Callable

from . import paths
from .constants import (
    DEFAULT_EXCLUDED_DIRS,
    DEFAULT_EXCLUDED_EXTENSIONS,
    THEME_IDS,
    WEB_ENGINES,
)
from .hotkeys import HotkeyError, is_valid_hotkey, normalize_hotkey
from .logging_setup import get_logger
from .version import CONFIG_SCHEMA_VERSION

log = get_logger(__name__)

_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def default_config() -> dict[str, Any]:
    """Return a fresh copy of the default configuration."""
    user_home = paths.home()
    return {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "general": {
            "hotkey": "Alt+Space",
            "start_with_windows": False,
            "start_minimized": False,
            "hide_on_focus_loss": True,
            "language": "en",
            "show_tray_icon": True,
            "confirm_destructive_actions": True,
            "remember_last_query": False,
            "check_for_updates": False,
        },
        "appearance": {
            "theme": "dark",
            "accent": "#68a9ff",
            "opacity": 0.98,
            "font_family": "Segoe UI",
            "font_size": 13,
            "window_width": 1180,
            "window_height": 620,
            "result_spacing": 4,
            "corner_radius": 14,
            "animations": True,
            "animation_duration": 150,
            "show_icons": True,
            "show_categories": True,
        },
        "widgets": {
            "clock_enabled": True,
            "weather_enabled": True,
            "system_enabled": True,
            "meme_enabled": True,
            "weather_location": "",
        },
        "search": {
            "max_results": 12,
            "fuzzy": True,
            "typo_tolerance": True,
            "autocomplete": True,
            "auto_detect": True,
            "save_history": True,
            "history_limit": 300,
            "prioritize_recent": True,
            "debounce_ms": 65,
            "keyword_aliases": {},
            "disabled_providers": [],
        },
        "applications": {
            "index_start_menu": True,
            "scan_program_files": False,
            "directories": [],
            "excluded": [],
            "aliases": {},
            "refresh_on_start": False,
            "refresh_interval_hours": 24,
        },
        "files": {
            "enabled": True,
            "auto_index": True,
            "directories": paths.default_document_dirs(),
            "excluded_dirs": list(DEFAULT_EXCLUDED_DIRS),
            "excluded_extensions": list(DEFAULT_EXCLUDED_EXTENSIONS),
            "include_hidden": False,
            "max_depth": 10,
            "max_files": 200000,
            "include_folders": True,
            "content_search_enabled": False,
            "content_search_extensions": [".txt", ".md", ".py", ".json", ".csv", ".html", ".xml"],
            "content_search_max_file_bytes": 1000000,
        },
        "web": {
            "engine": "duckduckgo",
            "browser": "system",
            "engines": copy.deepcopy(WEB_ENGINES),
            "open_in_background": False,
        },
        "calculator": {
            "precision": 10,
            "history_limit": 50,
            "angle_unit": "rad",
            "show_steps": False,
        },
        "commands": {
            "confirm_destructive": True,
            "custom": [],
        },
        "clipboard": {
            "enabled": False,
            "limit": 200,
            "poll_interval_ms": 600,
            "ignore_duplicates": True,
            "capture_images": False,
            "exclude_sensitive": True,
        },
        "privacy": {
            "clipboard_history": False,
            "clipboard_history_consent": False,
            "usage_tracking": False,
            "save_search_history": True,
            "retention_days": 90,
        },
        "updates": {
        "check_automatically": False,
        "last_check": 0.0,
    },
    "advanced": {
            "debug": False,
            "logging": True,
            "log_level": "INFO",
            "performance_stats": False,
            "single_instance": True,
        },
        "date_time": {
            "format": "%Y-%m-%d %H:%M:%S",
            "favourite_zones": ["UTC", "Europe/Istanbul", "America/New_York", "Asia/Tokyo"],
        },
        "screenshots": {
            "directory": paths.default_screenshot_dir(),
        },
        "notes": {
            "auto_save_ms": 700,
        },
        "quick_actions": {"enabled": True},
        "smart_suggestions": {
            "enabled": True,
            "recent_apps": 4,
            "recent_files": 3,
            "recent_queries": 2,
        },
        "ssh": {"terminal": "system"},
        "_paths": {"home": str(user_home)},
    }


def _coerce(value: Any, default: Any) -> Any:
    """Best-effort coercion of *value* to the type of *default*."""
    if default is None:
        return value
    if isinstance(default, bool):
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on", "enabled"}
        return default
    if isinstance(default, int) and not isinstance(default, bool):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
    if isinstance(default, float):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
    if isinstance(default, str):
        return value if isinstance(value, str) else str(value)
    if isinstance(default, list):
        if not isinstance(value, (list, tuple)):
            return copy.deepcopy(default)
        return [str(item) for item in value if isinstance(item, (str, int, float))]
    if isinstance(default, dict):
        return value if isinstance(value, dict) else copy.deepcopy(default)
    return value


def _clamp_int(low: int, high: int) -> Callable[[Any], int]:
    def _validate(value: Any) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return low
        return max(low, min(high, number))

    return _validate


def _clamp_float(low: float, high: float) -> Callable[[Any], float]:
    def _validate(value: Any) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return low
        return max(low, min(high, number))

    return _validate


def _validate_color(value: Any) -> str:
    text = str(value or "").strip()
    if _COLOR_RE.match(text):
        return text.lower()
    if re.match(r"^#?[0-9a-fA-F]{3}$", text):
        text = text.lstrip("#")
        return "#" + "".join(ch * 2 for ch in text.lower())
    return "#68a9ff"


def _validate_theme(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in THEME_IDS else "dark"


def _validate_hotkey(value: Any) -> str:
    text = str(value or "").strip()
    try:
        return normalize_hotkey(text)
    except HotkeyError:
        return "Alt+Space"


def _validate_engine(value: Any) -> str:
    text = str(value or "").strip()
    return text or "duckduckgo"


def _validate_str_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item) for item in value if str(item).strip()]


#: Dotted-path validators applied after generic coercion.
_VALIDATORS: dict[str, Callable[[Any], Any]] = {
    "general.hotkey": _validate_hotkey,
    "appearance.theme": _validate_theme,
    "appearance.accent": _validate_color,
    "appearance.opacity": _clamp_float(0.65, 1.0),
    "appearance.font_size": _clamp_int(8, 28),
    "appearance.window_width": _clamp_int(460, 1600),
    "appearance.window_height": _clamp_int(300, 1200),
    "appearance.result_spacing": _clamp_int(0, 20),
    "appearance.corner_radius": _clamp_int(0, 30),
    "appearance.animation_duration": _clamp_int(0, 800),
    "search.max_results": _clamp_int(3, 50),
    "search.history_limit": _clamp_int(10, 5000),
    "search.debounce_ms": _clamp_int(40, 800),
    "search.disabled_providers": _validate_str_list,
    "files.max_depth": _clamp_int(1, 30),
    "files.max_files": _clamp_int(1000, 3000000),
    "files.directories": _validate_str_list,
    "files.excluded_dirs": _validate_str_list,
    "files.excluded_extensions": _validate_str_list,
    "applications.excluded": _validate_str_list,
    "applications.refresh_interval_hours": _clamp_int(1, 720),
    "web.engine": _validate_engine,
    "calculator.precision": _clamp_int(1, 30),
    "calculator.history_limit": _clamp_int(0, 500),
    "clipboard.limit": _clamp_int(10, 2000),
    "clipboard.poll_interval_ms": _clamp_int(200, 5000),
    "privacy.retention_days": _clamp_int(1, 3650),
    "date_time.format": lambda value: str(value or "%Y-%m-%d %H:%M:%S"),
}

#: Keys whose value must be a mapping of string -> list of strings.
_ALIAS_KEYS = ("search.keyword_aliases", "applications.aliases")


def _merge_defaults(target: Any, defaults: Any) -> Any:
    """Recursively fill missing keys from *defaults* (mutates *target*)."""
    if isinstance(defaults, dict):
        if not isinstance(target, dict):
            return copy.deepcopy(defaults)
        for key, default_value in defaults.items():
            if key not in target:
                target[key] = copy.deepcopy(default_value)
            else:
                target[key] = _merge_defaults(target[key], default_value)
        return target
    return target


def _apply_special(dotted: str, value: Any, default: Any) -> Any:
    validator = _VALIDATORS.get(dotted)
    if validator is not None:
        return validator(value)
    if dotted == "search.keyword_aliases":
        # alias -> keyword (single string), e.g. {"w": "web"}
        if not isinstance(value, dict):
            return {}
        cleaned: dict[str, str] = {}
        for key, target in value.items():
            if isinstance(target, (list, tuple)):
                target = target[0] if target else ""
            if not isinstance(target, str):
                continue
            alias = str(key).strip().lower()
            keyword = target.strip().lower()
            if alias and keyword:
                cleaned[alias] = keyword
        return cleaned
    if dotted == "applications.aliases":
        # application name -> list of aliases
        if not isinstance(value, dict):
            return {}
        cleaned_lists: dict[str, list[str]] = {}
        for key, aliases in value.items():
            items = [aliases] if isinstance(aliases, str) else _validate_str_list(aliases)
            if str(key).strip():
                cleaned_lists[str(key)] = items
        return cleaned_lists
    return _coerce(value, default)


def sanitize(data: Any, defaults: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate *data* against the defaults and return a clean configuration."""
    base = copy.deepcopy(defaults if defaults is not None else default_config())
    if not isinstance(data, dict):
        return base
    merged = _merge_defaults(copy.deepcopy(data), base)
    _sanitize_in_place(merged, base, "")
    return merged


def _sanitize_in_place(node: dict[str, Any], defaults: dict[str, Any], prefix: str) -> None:
    for key, default_value in defaults.items():
        dotted = f"{prefix}.{key}" if prefix else key
        value = node.get(key, default_value)
        if isinstance(default_value, dict):
            if not isinstance(value, dict):
                node[key] = copy.deepcopy(default_value)
                continue
            _sanitize_in_place(value, default_value, dotted)
        else:
            node[key] = _apply_special(dotted, value, default_value)


class ConfigManager:
    """Loads, validates and persists the user configuration."""

    def __init__(self, path: str | os.PathLike[str] | None = None, autoload: bool = True):
        self._path = Path(path) if path is not None else paths.config_path()
        self._lock = threading.RLock()
        self._listeners: list[Callable[[str, Any], None]] = []
        self._defaults = default_config()
        self._data: dict[str, Any] = copy.deepcopy(self._defaults)
        self._dirty = False
        if autoload:
            self.load()

    # ------------------------------------------------------------------ paths
    @property
    def path(self) -> Path:
        return self._path

    @property
    def data(self) -> dict[str, Any]:
        """Live configuration mapping. Mutate through :meth:`set`."""
        return self._data

    @property
    def defaults(self) -> dict[str, Any]:
        return copy.deepcopy(self._defaults)

    # ------------------------------------------------------------------- load
    def load(self) -> dict[str, Any]:
        with self._lock:
            if not self._path.exists():
                self._data = copy.deepcopy(self._defaults)
                return self._data
            try:
                raw = self._path.read_text(encoding="utf-8")
                parsed = json.loads(raw)
            except (OSError, json.JSONDecodeError) as exc:
                log.error("Configuration at %s is unreadable (%s); using defaults", self._path, exc)
                self._backup_corrupt_file()
                self._data = copy.deepcopy(self._defaults)
                return self._data
            self._data = sanitize(parsed, self._defaults)
            # Version 2 widens only the untouched 1.0.x default geometry so the
            # new side rails fit; explicitly customised dimensions are kept.
            # Treat malformed schema metadata as an old config rather than
            # allowing a string/null value to crash application startup.
            old_schema_version = 1
            if isinstance(parsed, dict):
                try:
                    old_schema_version = int(parsed.get("schema_version", 1) or 1)
                except (TypeError, ValueError):
                    old_schema_version = 1
                if old_schema_version < 2:
                    # Compare the sanitised values so legacy numeric strings
                    # receive the same default-size migration as JSON numbers.
                    if self._data["appearance"]["window_width"] == 780:
                        self._data["appearance"]["window_width"] = 1180
                    if self._data["appearance"]["window_height"] == 500:
                        self._data["appearance"]["window_height"] = 620
            self._data["schema_version"] = CONFIG_SCHEMA_VERSION
            privacy = parsed.get("privacy") if isinstance(parsed, dict) else None
            has_clipboard_consent = (
                isinstance(privacy, dict)
                and "clipboard_history_consent" in privacy
                and privacy["clipboard_history_consent"] is True
            )
            if not has_clipboard_consent:
                # Older releases defaulted clipboard history on. Without an
                # explicit consent marker, treat that value as implicit
                # legacy configuration, not as permission to keep capturing.
                self._data["clipboard"]["enabled"] = False
                self._data["privacy"]["clipboard_history"] = False
                self._data["privacy"]["clipboard_history_consent"] = False
            return self._data

    def _backup_corrupt_file(self) -> None:
        try:
            backup = self._path.with_suffix(".corrupt.json")
            self._path.replace(backup)
            log.warning("Moved unreadable configuration to %s", backup)
        except OSError:
            log.warning("Could not move the unreadable configuration aside")

    # ------------------------------------------------------------------- save
    def save(self) -> bool:
        with self._lock:
            self._data = sanitize(self._data, self._defaults)
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                temporary = self._path.with_suffix(".tmp")
                temporary.write_text(
                    json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8"
                )
                os.replace(temporary, self._path)
                self._dirty = False
                return True
            except OSError as exc:
                log.error("Could not save configuration to %s: %s", self._path, exc)
                return False

    # ------------------------------------------------------------------ access
    def get(self, dotted: str, default: Any = None) -> Any:
        with self._lock:
            node: Any = self._data
            for part in dotted.split("."):
                if not isinstance(node, dict) or part not in node:
                    return default
                node = node[part]
            return node

    def set(self, dotted: str, value: Any, save: bool = True) -> Any:
        """Set a value by dotted path, sanitise it and optionally persist."""
        parts = dotted.split(".")
        with self._lock:
            default_node: Any = self._defaults
            for part in parts:
                default_node = default_node.get(part) if isinstance(default_node, dict) else None
            cleaned = _apply_special(dotted, value, default_node)
            node = self._data
            for part in parts[:-1]:
                child = node.get(part)
                if not isinstance(child, dict):
                    child = {}
                    node[part] = child
                node = child
            node[parts[-1]] = cleaned
            if dotted in {"privacy.clipboard_history", "clipboard.enabled"}:
                # Presence of this marker distinguishes a user decision from
                # the old implicit default during future config migrations.
                enabled = bool(cleaned)
                self._data["privacy"]["clipboard_history"] = enabled
                self._data["clipboard"]["enabled"] = enabled
                self._data["privacy"]["clipboard_history_consent"] = True
            self._dirty = True
            if save:
                self.save()
            for listener in list(self._listeners):
                try:
                    listener(dotted, cleaned)
                except Exception:
                    log.exception("Configuration listener failed for %s", dotted)
            return cleaned

    def update(self, values: dict[str, Any], save: bool = True) -> None:
        for key, value in values.items():
            self.set(key, value, save=False)
        if save:
            self.save()

    def reset(self, save: bool = True) -> bool:
        """Restore defaults and report whether they were persisted successfully."""
        with self._lock:
            self._data = copy.deepcopy(self._defaults)
            self._dirty = True
            saved = self.save() if save else True
            for listener in list(self._listeners):
                try:
                    listener("*", None)
                except Exception:
                    log.exception("Configuration listener failed during reset")
            return saved

    def subscribe(self, listener: Callable[[str, Any], None]) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)

    def unsubscribe(self, listener: Callable[[str, Any], None]) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)


__all__ = ["ConfigManager", "default_config", "sanitize"]
