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
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

from core.version import APP_AUTHOR, APP_COPYRIGHT, APP_DESCRIPTION, APP_NAME, APP_VERSION, APP_VERSION_INFO

ROOT = Path(__file__).resolve().parent
ICON = ROOT / "assets" / "icons" / "seekr.ico"

#: Import name -> package name shown in the error message.
REQUIRED_MODULES = (
    ("PySide6", "PySide6"),
    ("psutil", "psutil"),
    ("sympy", "sympy"),
    ("tzdata", "tzdata"),
    ("PyInstaller", "pyinstaller"),
)

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


def missing_modules() -> list[str]:
    """Return packages needed for a build that are not importable."""
    missing: list[str] = []
    for module, package in REQUIRED_MODULES:
        try:
            available = importlib.util.find_spec(module) is not None
        except (ImportError, ModuleNotFoundError, ValueError):
            available = False
        if not available:
            missing.append(package)
    return missing


def ensure_icon() -> None:
    if ICON.is_file():
        return
    print("Icon asset missing; generating it now...")
    script = ROOT / "tools" / "make_icons.py"
    if not script.is_file():
        raise FileNotFoundError(f"Icon generator not found: {script}")
    try:
        completed = subprocess.run([sys.executable, str(script)], cwd=ROOT, check=False)
    except OSError as exc:
        raise RuntimeError(f"Could not run the icon generator: {exc}") from exc
    if completed.returncode != 0 or not ICON.is_file():
        raise RuntimeError(
            "Icon generation failed. Run 'python tools/make_icons.py' and inspect the error above."
        )


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

    if sys.version_info < (3, 10):
        print("SeekR requires Python 3.10 or newer to build.", file=sys.stderr)
        return 2

    if os.name != "nt":
        print(
            "WARNING: this is not Windows. PyInstaller will build for the current platform,\n"
            "and Windows-only integration (global hotkey, Start Menu, power plans) is untested here.",
            file=sys.stderr,
        )

    missing = missing_modules()
    if missing:
        print("Missing build dependencies: " + ", ".join(missing), file=sys.stderr)
        print("Install them into this interpreter with:", file=sys.stderr)
        print("    pip install -r requirements-dev.txt", file=sys.stderr)
        return 2

    try:
        ensure_icon()
    except (OSError, RuntimeError) as exc:
        print(f"Cannot build without the application icon: {exc}", file=sys.stderr)
        return 2

    try:
        version_path = version_resource()
    except OSError as exc:
        print(f"Could not write the Windows version resource: {exc}", file=sys.stderr)
        return 2

    # Write PyInstaller output to a log file so the full traceback is preserved
    # even when the terminal/PowerShell capture truncates it.
    log_path = ROOT / "build" / "pyinstaller.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = log_path.open("w", encoding="utf-8")
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
        str(version_path),
        "--specpath",
        str(ROOT / "build"),
        "--onedir" if args.onedir else "--onefile",
        "--console" if args.console else "--windowed",
        str(ROOT / "main.py"),
    ]
    print("Running:", " ".join(command))
    print(f"PyInstaller output will be written to {log_path}")
    completed = subprocess.run(command, cwd=ROOT, stdout=log_file, stderr=subprocess.STDOUT)
    log_file.close()
    if completed.returncode != 0:
        print("Build failed. Last 40 lines of PyInstaller output:", file=sys.stderr)
        try:
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            for line in lines[-40:]:
                print(line, file=sys.stderr)
        except OSError:
            pass
        print(f"Full log: {log_path}", file=sys.stderr)
        return completed.returncode

    target = output_target(args.onedir)
    if target.is_file():
        print(f"Built {target} ({target.stat().st_size / (1024 * 1024):.1f} MiB)")
        if os.name == "nt" and target.suffix.lower() == ".exe":
            print(f"Windows executable: {target}")
        return 0
    print(f"Build finished but {target} was not found; inspect dist/ manually.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise SystemExit(1)
