"""Screenshot capture and storage."""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

from PySide6.QtGui import QGuiApplication, QPixmap

from core.config_manager import ConfigManager
from core.database import Database
from core.logging_setup import get_logger
from core.models import ResultAction, SearchResult
from core.paths import expand_path
from core.search_engine import SearchProvider

from . import util

log = get_logger(__name__)


class ScreenshotError(RuntimeError):
    """Raised when a screenshot cannot be captured or saved."""


def screenshot_directory(config: ConfigManager) -> Path:
    configured = str(config.get("screenshots.directory", "") or "").strip()
    directory = expand_path(configured) if configured else Path.home() / "Pictures" / "SeekR"
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError:
        fallback = expand_path("~")
        log.warning("Screenshot directory unusable (%s); using %s", directory, fallback)
        directory = fallback
    return directory


def capture_screen(screen_index: int | None = None) -> QPixmap:
    """Grab the whole screen. Raises :class:`ScreenshotError` on failure."""
    app = QGuiApplication.instance()
    if app is None:
        raise ScreenshotError("Screenshots need the application to be running")
    screens = QGuiApplication.screens()
    if not screens:
        raise ScreenshotError("No screen was detected")
    screen = screens[screen_index] if screen_index is not None and 0 <= screen_index < len(screens) else QGuiApplication.primaryScreen()
    if screen is None:
        raise ScreenshotError("No primary screen was detected")
    pixmap = screen.grabWindow(0)
    if pixmap is None or pixmap.isNull():
        raise ScreenshotError(
            "The screen could not be captured. On Wayland, screenshot capture requires a portal-enabled session."
        )
    return pixmap


def save_screenshot(config: ConfigManager, screen_index: int | None = None) -> tuple[bool, str, str]:
    """Capture the screen and save it as a PNG.

    Returns ``(success, path, error)``.
    """
    try:
        pixmap = capture_screen(screen_index)
    except ScreenshotError as exc:
        return False, "", str(exc)
    directory = screenshot_directory(config)
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    target = directory / f"SeekR_{stamp}.png"
    counter = 1
    while target.exists():
        target = directory / f"SeekR_{stamp}_{counter}.png"
        counter += 1
    if not pixmap.save(str(target), "PNG"):
        return False, "", f"Could not write {target}"
    return True, str(target), ""


def open_snipping_tool() -> tuple[bool, str]:
    """Launch the Windows snipping overlay."""
    if os.name != "nt":
        return False, "The Snipping Tool is only available on Windows"
    return util.run_detached(["explorer.exe", "ms-screenclip:"])


def list_screenshots(config: ConfigManager, limit: int = 50) -> list[Path]:
    directory = screenshot_directory(config)
    try:
        files = [path for path in directory.iterdir() if path.suffix.lower() == ".png"]
    except OSError:
        return []
    files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return files[:limit]


class ScreenshotProvider(SearchProvider):
    """The ``shot`` keyword."""

    id = "screenshots"
    title = "Screenshots"
    keyword = "shot"
    weight = 1.0
    auto = False

    def search(self, query: str, limit: int) -> list[SearchResult]:
        directory = screenshot_directory(self.config)
        results = [
            self.make_result(
                title="Take a screenshot",
                subtitle=f"Capture the full screen and save it to {directory}",
                category="Screenshot",
                score=0.95,
                primary=self._capture,
                actions=[ResultAction("Open screenshots folder", lambda: self.hooks.open_path(str(directory)))],
                icon_glyph="▣",
            ),
            self.make_result(
                title="Open screenshots folder",
                subtitle=str(directory),
                category="Screenshot",
                score=0.8,
                primary=lambda: self.hooks.open_path(str(directory)),
                icon_glyph="🖼",
            ),
        ]
        if os.name == "nt":
            results.append(
                self.make_result(
                    title="Open Snipping Tool",
                    subtitle="Capture a region with the Windows snipping overlay",
                    category="Screenshot",
                    score=0.85,
                    primary=self._snipping,
                    icon_glyph="✂",
                )
            )
        recent = list_screenshots(self.config, limit=5)
        for index, path in enumerate(recent):
            results.append(
                self.make_result(
                    title=path.name,
                    subtitle=f"Saved {util.format_ago(path.stat().st_mtime)}  ·  {util.format_bytes(path.stat().st_size)}",
                    category="Screenshot",
                    score=0.7 - index * 0.02,
                    primary=lambda p=str(path): self.hooks.open_path(p),
                    actions=[
                        ResultAction("Preview", lambda p=str(path): self.hooks.preview(p)),
                        ResultAction("Open containing folder", lambda p=str(path): self.hooks.reveal_path(p)),
                    ],
                    copy_text=str(path),
                    icon_path=str(path),
                    icon_glyph="🖼",
                )
            )
        return results[:limit]

    def _capture(self) -> None:
        ok, path, error = save_screenshot(self.config)
        if not ok:
            self.hooks.show_error("Screenshot failed", error)
            return
        self.hooks.notify(f"Screenshot saved to {path}")
        self.hooks.copy_text(path)
        self.hooks.hide_launcher()

    def _snipping(self) -> None:
        ok, message = open_snipping_tool()
        self.hooks.notify(message, "info" if ok else "error")
        if ok:
            self.hooks.hide_launcher()

    def empty_help(self) -> SearchResult | None:
        return self.make_result(
            title="Screenshots",
            subtitle="Capture the screen or open recent screenshots",
            category="Screenshot",
            score=1.0,
            primary=self._capture,
            icon_glyph="▣",
        )


__all__ = [
    "ScreenshotError",
    "capture_screen",
    "save_screenshot",
    "screenshot_directory",
    "open_snipping_tool",
    "list_screenshots",
    "ScreenshotProvider",
]
