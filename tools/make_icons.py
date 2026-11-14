"""Generate the SeekR icon assets (PNG + multi-size ICO).

The icon itself is drawn by :func:`ui.icons.app_icon`, so the packaged icon and
the in-app icon can never drift apart. Run this after changing the icon design:

    python tools/make_icons.py
"""

from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QBuffer, QByteArray, QIODevice  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ui.icons import app_icon  # noqa: E402

SIZES = (16, 24, 32, 48, 64, 128, 256)


def png_bytes(size: int) -> bytes:
    pixmap = app_icon(size).pixmap(size, size)
    if pixmap.isNull():
        raise RuntimeError(f"Could not render the icon at {size}px")
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not pixmap.save(buffer, "PNG"):
        raise RuntimeError("Qt could not encode the PNG icon")
    buffer.close()
    return bytes(data)


def ico_bytes(images: list[tuple[int, bytes]]) -> bytes:
    """Build an ICO container with PNG-compressed entries (Vista+)."""
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries = bytearray()
    payload = bytearray()
    for size, data in images:
        dimension = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", dimension, dimension, 0, 0, 1, 32, len(data), offset)
        payload += data
        offset += len(data)
    return header + bytes(entries) + bytes(payload)


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    destination = ROOT / "assets" / "icons"
    destination.mkdir(parents=True, exist_ok=True)

    images = [(size, png_bytes(size)) for size in SIZES]
    png_path = destination / "seekr.png"
    png_path.write_bytes(dict(images)[256])
    ico_path = destination / "seekr.ico"
    ico_path.write_bytes(ico_bytes(images))

    del app
    print(f"Wrote {png_path.relative_to(ROOT)} and {ico_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
