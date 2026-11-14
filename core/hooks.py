"""UI hooks.

Feature modules must not import Qt widgets, so every user-visible side effect
goes through this small interface. The real implementation lives in
``core.application.SeekRApplication``; tests use :class:`NullHooks`.
"""

from __future__ import annotations

from typing import Optional


class UIHooks:
    """Default no-op implementation of the UI interface."""

    def open_path(self, path: str) -> bool:
        return False

    def reveal_path(self, path: str) -> bool:
        return False

    def open_url(self, url: str) -> bool:
        return False

    def copy_text(self, text: str) -> bool:
        return False

    def show_info(self, title: str, text: str) -> None:
        return None

    def show_error(self, title: str, text: str) -> None:
        return None

    def confirm(self, title: str, message: str) -> bool:
        return False

    def notify(self, message: str, level: str = "info") -> None:
        return None

    def open_settings(self, page: Optional[str] = None) -> None:
        return None

    def open_tools(self, tab: Optional[str] = None) -> None:
        return None

    def open_clipboard(self) -> None:
        return None

    def open_notes(self, note_id: Optional[int] = None) -> None:
        return None

    def open_tool_window(self, name: str) -> None:
        return None

    def lookup_definition(self, word: str) -> None:
        return None

    def preview(self, path: str) -> None:
        return None

    def fill_query(self, text: str) -> None:
        return None

    def hide_launcher(self) -> None:
        return None

    def refresh_indexes(self, which: str = "all") -> None:
        return None

    def open_connection(self, profile: dict) -> None:
        return None


class NullHooks(UIHooks):
    """Hooks used in headless tests: records calls without touching the UI."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple]] = []

    def _record(self, name: str, *args) -> None:
        self.calls.append((name, args))

    def open_path(self, path: str) -> bool:
        self._record("open_path", path)
        return True

    def reveal_path(self, path: str) -> bool:
        self._record("reveal_path", path)
        return True

    def open_url(self, url: str) -> bool:
        self._record("open_url", url)
        return True

    def copy_text(self, text: str) -> bool:
        self._record("copy_text", text)
        return True

    def show_info(self, title: str, text: str) -> None:
        self._record("show_info", title, text)

    def show_error(self, title: str, text: str) -> None:
        self._record("show_error", title, text)

    def confirm(self, title: str, message: str) -> bool:
        self._record("confirm", title, message)
        return False

    def notify(self, message: str, level: str = "info") -> None:
        self._record("notify", message, level)

    def open_settings(self, page: Optional[str] = None) -> None:
        self._record("open_settings", page)

    def open_tools(self, tab: Optional[str] = None) -> None:
        self._record("open_tools", tab)

    def open_clipboard(self) -> None:
        self._record("open_clipboard")

    def open_notes(self, note_id: Optional[int] = None) -> None:
        self._record("open_notes", note_id)

    def open_tool_window(self, name: str) -> None:
        self._record("open_tool_window", name)

    def lookup_definition(self, word: str) -> None:
        self._record("lookup_definition", word)

    def preview(self, path: str) -> None:
        self._record("preview", path)

    def fill_query(self, text: str) -> None:
        self._record("fill_query", text)

    def hide_launcher(self) -> None:
        self._record("hide_launcher")

    def refresh_indexes(self, which: str = "all") -> None:
        self._record("refresh_indexes", which)

    def open_connection(self, profile: dict) -> None:
        self._record("open_connection", profile)


__all__ = ["UIHooks", "NullHooks"]
