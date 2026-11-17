"""Screenshot capture and storage."""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QPainter, QPixmap

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
    """Capture one screen or compose all connected displays into one image."""
    app = QGuiApplication.instance()
    if app is None:
        raise ScreenshotError("Screenshots need the application to be running")
    screens = QGuiApplication.screens()
    if not screens:
        raise ScreenshotError("No screen was detected")

    if screen_index is not None:
        if not 0 <= screen_index < len(screens):
            raise ScreenshotError(f"Screen index {screen_index} is out of range")
        pixmap = screens[screen_index].grabWindow(0)
        if pixmap is None or pixmap.isNull():
            raise ScreenshotError("The selected screen could not be captured")
        return pixmap

    captures = []
    bounds = screens[0].geometry()
    for screen in screens:
        geometry = screen.geometry()
        bounds = bounds.united(geometry)
        pixmap = screen.grabWindow(0)
        if pixmap is None or pixmap.isNull():
            raise ScreenshotError(
                f"Could not capture display {screen.name() or geometry}"
            )
        # Normalize each display to its logical geometry so mixed-DPI monitors
        # can be composed without gaps or offsets in the virtual desktop image.
        normalized = pixmap.scaled(
            geometry.size(),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        normalized.setDevicePixelRatio(1.0)
        captures.append((geometry, normalized))

    combined = QPixmap(bounds.size())
    combined.fill(Qt.GlobalColor.transparent)
    painter = QPainter(combined)
    try:
        for geometry, pixmap in captures:
            painter.drawPixmap(geometry.topLeft() - bounds.topLeft(), pixmap)
    finally:
        painter.end()
    if combined.isNull():
        raise ScreenshotError("The connected displays could not be combined")
    return combined

def save_pixmap(config: ConfigManager, pixmap: QPixmap) -> tuple[bool, str, str]:
    """Save an already-captured pixmap in the configured screenshot folder."""
    if pixmap is None or pixmap.isNull():
        return False, "", "There is no screenshot to save"
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


def save_screenshot(config: ConfigManager, screen_index: int | None = None) -> tuple[bool, str, str]:
    """Capture the screen and save it as a PNG.

    Returns ``(success, path, error)``.
    """
    try:
        pixmap = capture_screen(screen_index)
    except ScreenshotError as exc:
        return False, "", str(exc)
    return save_pixmap(config, pixmap)

def open_snipping_tool() -> tuple[bool, str]:
    """Launch the Windows snipping overlay."""
    if os.name != "nt":
        return False, "The Snipping Tool is only available on Windows"
    try:
        os.startfile("ms-screenclip:")  # type: ignore[attr-defined]
        return True, "Opened the Snipping Tool"
    except OSError:
        # Older shells sometimes need Explorer to resolve the protocol.
        return util.run_detached(["explorer.exe", "ms-screenclip:"])


def list_screenshots(config: ConfigManager, limit: int = 50) -> list[Path]:
    directory = screenshot_directory(config)
    try:
        files = [path for path in directory.iterdir() if path.suffix.lower() == ".png"]
    except OSError:
        return []

    def _mtime(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except OSError:
            return 0.0

    files.sort(key=_mtime, reverse=True)
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
            try:
                modified = path.stat().st_mtime
                size = path.stat().st_size
            except OSError:
                continue
            results.append(
                self.make_result(
                    title=path.name,
                    subtitle=f"Saved {util.format_ago(modified)}  ·  {util.format_bytes(size)}",
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
