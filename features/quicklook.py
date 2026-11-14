"""QuickLook-style previews for images and text files."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from core.logging_setup import get_logger

from . import util

log = get_logger(__name__)

IMAGE_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".ico", ".tif", ".tiff", ".svg",
}
TEXT_SUFFIXES = {
    ".txt", ".md", ".markdown", ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".xml",
    ".html", ".htm", ".css", ".scss", ".ini", ".cfg", ".conf", ".log", ".csv", ".tsv",
    ".yml", ".yaml", ".toml", ".sh", ".bat", ".ps1", ".c", ".h", ".hpp", ".cpp", ".cs",
    ".java", ".kt", ".rs", ".go", ".sql", ".gitignore", ".env.example", ".reg", ".tex",
}


class QuickLookError(RuntimeError):
    """Raised when a file cannot be previewed."""


def preview_kind(path: str | os.PathLike[str]) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        return "image"
    if suffix in TEXT_SUFFIXES or Path(path).name.lower() in {".gitignore", "dockerfile", "makefile"}:
        return "text"
    return "unsupported"


def file_summary(path: str | os.PathLike[str]) -> dict:
    target = Path(path)
    try:
        stat_result = target.stat()
    except OSError as exc:
        raise QuickLookError(f"Cannot read {target}: {exc}") from exc
    return {
        "name": target.name,
        "path": str(target),
        "size": stat_result.st_size,
        "modified": stat_result.st_mtime,
        "size_text": util.format_bytes(stat_result.st_size),
        "modified_text": util.format_ago(stat_result.st_mtime),
        "kind": preview_kind(target),
        "suffix": target.suffix.lower(),
        "is_dir": target.is_dir(),
    }


def load_text_preview(path: str | os.PathLike[str], max_bytes: int = 160_000) -> str:
    target = Path(path)
    try:
        size = target.stat().st_size
        with target.open("rb") as handle:
            data = handle.read(max_bytes)
    except OSError as exc:
        raise QuickLookError(f"Cannot read {target.name}: {exc}") from exc
    text = data.decode("utf-8", errors="replace")
    if size > max_bytes:
        text += f"\n\n… preview truncated ({util.format_bytes(size)} total)"
    return text


def load_image_preview(path: str | os.PathLike[str], max_pixels: int = 2400) -> QPixmap:
    target = Path(path)
    pixmap = QPixmap(str(target))
    if pixmap.isNull():
        raise QuickLookError(f"Could not decode {target.name} as an image")
    if pixmap.width() > max_pixels or pixmap.height() > max_pixels:
        pixmap = pixmap.scaled(
            max_pixels,
            max_pixels,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    return pixmap


__all__ = [
    "IMAGE_SUFFIXES",
    "TEXT_SUFFIXES",
    "QuickLookError",
    "preview_kind",
    "file_summary",
    "load_text_preview",
    "load_image_preview",
]
