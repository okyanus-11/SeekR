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

Download the portable `SeekR.exe`, setup installer, and `SHA256SUMS.txt` from the [latest SeekR GitHub Release](https://github.com/okyanus-11/SeekR/releases/latest). The portable executable runs without installation; the setup installer provides a per-user installation and uninstaller. Main-branch builds are also uploaded as 30-day GitHub Actions artifacts. A version tag (`v*`) publishes both executables and their SHA-256 checksums to GitHub Releases. The installer and portable executable are unsigned, so Windows may display an unfamiliar-app SmartScreen warning.

### Upgrading

Run the newer `SeekR-Setup-<version>.exe` over the existing installation. Inno
Setup upgrades in place: it replaces the binaries and shortcuts, remembers the
previously chosen install directory (`UsePreviousAppDir` is on by default), and
never touches `%APPDATA%\SeekR`, so settings, notes and clipboard history
survive. Only a same-version reinstall has been validated so far; a real upgrade
from an earlier build is still on the release checklist as tests I04–I06 in
[WINDOWS_MANUAL_TEST.md](WINDOWS_MANUAL_TEST.md).

## Run from source

Requires Python 3.10 or newer (3.12 recommended) on Windows or Linux:

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

The standalone executable is written to `dist\SeekR.exe`. To build the onedir
folder required by the installer, run `python build.py --onedir`. To retain a
console for troubleshooting, add `--console`. GitHub Actions builds both the
portable executable and the onedir installer payload, validates the installer
with an install/start/uninstall smoke test, and publishes the executable,
installer, and SHA-256 manifest as workflow artifacts. Tag-triggered builds
also attach those files to the matching GitHub Release.

See [the Windows manual test checklist](WINDOWS_MANUAL_TEST.md) before
describing native shell integration as verified.

## User data and privacy

SeekR keeps its JSON configuration, SQLite database, application logs, notes,
and optional clipboard history under `%APPDATA%\SeekR` on Windows and the
platform's application-data directory elsewhere. Back up this folder before
manually changing or removing it. Clipboard history is local application data,
not encrypted storage; enable it only if you accept that copied text is stored
on the local device.
