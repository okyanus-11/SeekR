# Installing and running SeekR

## Windows release builds

SeekR targets 64-bit Windows 10/11. Download the standalone `SeekR.exe` to run
without installing Python, or use `SeekR-Setup-<version>.exe` for a per-user
installation. The installer uses Inno Setup, installs under the current user's
Local AppData, creates a Start Menu shortcut, and offers an optional desktop
shortcut. It does not require administrator privileges.

The installer registers a standard Windows uninstaller. Uninstalling removes
the application binaries and shortcuts but intentionally preserves the user's
configuration, SQLite database, notes, and clipboard history under
`%APPDATA%\SeekR`; remove that profile separately only if you intend to delete
all SeekR data.

Release builds are produced by the GitHub Actions workflow. Until a GitHub
Release is explicitly published, CI artifacts are not a permanent public
download. Do not treat a branch build as a signed or SmartScreen-reputation
verified installer.

## Run from source

Requires Python 3.12 or newer on Windows or Linux:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

On Linux, activate the virtual environment with `source .venv/bin/activate`.
Qt may require an X11/Wayland display session for interactive use. macOS is not
currently a supported or tested platform.

## Build on Windows

Use Python 3.12 and the pinned development requirements:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python build.py
```

The standalone executable is written to `dist\SeekR.exe`. To build an onedir
folder for diagnostics, run `python build.py --onedir`. To retain a console
for troubleshooting, add `--console`. GitHub Actions builds the standalone
executable and Inno Setup installer, then publishes them as workflow artifacts;
it does not create a GitHub Release automatically.

See [the Windows manual test checklist](WINDOWS_MANUAL_TEST.md) before
describing native shell integration as verified.

## User data and privacy

SeekR keeps its JSON configuration, SQLite database, application logs, notes,
and optional clipboard history under `%APPDATA%\SeekR` on Windows and the
platform's application-data directory elsewhere. Back up this folder before
manually changing or removing it. Clipboard history is local application data,
not encrypted storage; enable it only if you accept that copied text is stored
on the local device.
