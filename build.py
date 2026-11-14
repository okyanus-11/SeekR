#!/usr/bin/env python3
"""Build the standalone Windows executable for SeekR.

Usage (from the repository root, inside a virtual environment):

    pip install -r requirements-dev.txt
    python build.py

The script produces ``dist/SeekR.exe`` (one-file, windowed) plus the Windows
version resource so Explorer shows the correct product name and version.
It refuses to claim success if PyInstaller fails.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from core.version import APP_AUTHOR, APP_COPYRIGHT, APP_DESCRIPTION, APP_NAME, APP_VERSION, APP_VERSION_INFO

ROOT = Path(__file__).resolve().parent
ICON = ROOT / "assets" / "icons" / "seekr.ico"

VERSION_TEMPLATE = """# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={version_tuple},
    prodvers={version_tuple},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', '{author}'),
         StringStruct('FileDescription', '{description}'),
         StringStruct('FileVersion', '{version}'),
         StringStruct('InternalName', '{name}'),
         StringStruct('LegalCopyright', '{copyright}'),
         StringStruct('OriginalFilename', '{name}.exe'),
         StringStruct('ProductName', '{name}'),
         StringStruct('ProductVersion', '{version}')])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def output_target(onedir: bool, platform: str | None = None) -> Path:
    """Return the expected artifact path for the selected build layout."""
    executable = f"{APP_NAME}.exe" if (platform or os.name) == "nt" else APP_NAME
    if onedir:
        return ROOT / "dist" / APP_NAME / executable
    return ROOT / "dist" / executable


def ensure_icon() -> None:
    if ICON.exists():
        return
    print("Icon asset missing; generating it now…")
    subprocess.run([sys.executable, str(ROOT / "tools" / "make_icons.py")], cwd=ROOT, check=True)


def version_resource() -> Path:
    build_dir = ROOT / "build"
    build_dir.mkdir(exist_ok=True)
    path = build_dir / "version_info.txt"
    path.write_text(
        VERSION_TEMPLATE.format(
            version=APP_VERSION,
            version_tuple=APP_VERSION_INFO,
            author=APP_AUTHOR,
            description=APP_DESCRIPTION,
            copyright=APP_COPYRIGHT,
            name=APP_NAME,
        ),
        encoding="utf-8",
    )
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=f"Build {APP_NAME} {APP_VERSION}")
    parser.add_argument("--onedir", action="store_true", help="Build a folder instead of a single .exe")
    parser.add_argument("--console", action="store_true", help="Keep the console window (debugging)")
    args = parser.parse_args()

    if os.name != "nt":
        print(
            "WARNING: this is not Windows. PyInstaller will build for the current platform,\n"
            "and Windows-only integration (global hotkey, Start Menu, power plans) is untested here.",
            file=sys.stderr,
        )

    ensure_icon()
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller is missing. Install the development requirements first:", file=sys.stderr)
        print("    pip install -r requirements-dev.txt", file=sys.stderr)
        return 2

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name",
        APP_NAME,
        "--icon",
        str(ICON),
        "--add-data",
        f"{ROOT / 'assets'}{os.pathsep}assets",
        "--collect-data",
        "tzdata",
        "--version-file",
        str(version_resource()),
        "--specpath",
        str(ROOT / "build"),
        "--onedir" if args.onedir else "--onefile",
        "--console" if args.console else "--windowed",
        str(ROOT / "main.py"),
    ]
    print("Running:", " ".join(command))
    completed = subprocess.run(command, cwd=ROOT)
    if completed.returncode != 0:
        print("Build failed. See the PyInstaller output above.", file=sys.stderr)
        return completed.returncode

    target = output_target(args.onedir)
    if target.exists():
        print(f"Built {target} ({target.stat().st_size / (1024 * 1024):.1f} MiB)")
    else:
        print(f"Build finished but {target} was not found; inspect dist/ manually.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
