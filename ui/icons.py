"""Icon helpers: generated application icon and cached file icons."""

from __future__ import annotations

import os
from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import QFileInfo, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QFileIconProvider

_MAX_CACHED_ICONS = 512


class IconStore:
    """Caches file icons so scrolling results stays fast."""

    def __init__(self) -> None:
        self._provider = QFileIconProvider()
        self._cache: OrderedDict[str, QIcon] = OrderedDict()

    def icon_for(self, path: str | None) -> QIcon | None:
        if not path:
            return None
        if path in self._cache:
            self._cache.move_to_end(path)
            return self._cache[path]
        icon = QIcon()
        if os.path.exists(path):
            try:
                icon = self._provider.icon(QFileInfo(path))
            except Exception:
                icon = QIcon()
        if icon.isNull() and os.name != "nt":
            # Linux desktop entries and executables: fall back to the theme.
            try:
                icon = QIcon.fromTheme("application-x-executable")
            except Exception:
                icon = QIcon()
        self._cache[path] = icon
        if len(self._cache) > _MAX_CACHED_ICONS:
            self._cache.popitem(last=False)
        return icon if not icon.isNull() else None

    def cached_icon_for(self, path: str | None) -> QIcon | None:
        """Return an already-resolved icon without touching the Windows shell."""
        if not path:
            return None
        icon = self._cache.get(path)
        if icon is not None:
            self._cache.move_to_end(path)
            return icon
        return None

    def clear(self) -> None:
        self._cache.clear()


def app_icon(size: int = 256) -> QIcon:
    """Render the SeekR icon (rounded accent tile with a magnifier mark)."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    gradient = QLinearGradient(0, 0, size, size)
    gradient.setColorAt(0.0, QColor("#8f6bff"))
    gradient.setColorAt(1.0, QColor("#4c2fd6"))
    path = QPainterPath()
    path.addRoundedRect(QRectF(size * 0.03, size * 0.03, size * 0.94, size * 0.94), size * 0.22, size * 0.22)
    painter.fillPath(path, gradient)

    # Magnifier
    pen = QPen(QColor("#ffffff"))
    pen.setWidthF(size * 0.075)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.drawEllipse(QRectF(size * 0.27, size * 0.24, size * 0.4, size * 0.4))
    painter.drawLine(
        int(size * 0.61), int(size * 0.59), int(size * 0.77), int(size * 0.76)
    )

    # Spark of the "R"
    font = QFont("Segoe UI", int(size * 0.2), QFont.Weight.Bold)
    painter.setFont(font)
    painter.setPen(QColor(255, 255, 255, 235))
    painter.drawText(
        QRectF(size * 0.5, size * 0.52, size * 0.36, size * 0.34),
        int(Qt.AlignmentFlag.AlignCenter),
        "R",
    )
    painter.end()
    return QIcon(pixmap)


def app_pixmap(size: int = 256) -> QPixmap:
    return app_icon(size).pixmap(size, size)


def save_icon_files(directory: str | Path) -> dict[str, str]:
    """Write PNG and ICO icon files (used by the build script)."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    png_path = directory / "seekr.png"
    ico_path = directory / "seekr.ico"
    pixmap = app_pixmap(256)
    written: dict[str, str] = {}
    if pixmap.save(str(png_path), "PNG"):
        written["png"] = str(png_path)
    # Qt can write multi-frame ICO files from a 256px pixmap.
    if pixmap.save(str(ico_path), "ICO"):
        written["ico"] = str(ico_path)
    return written


__all__ = ["IconStore", "app_icon", "app_pixmap", "save_icon_files"]
