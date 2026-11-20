# Installing and running SeekR

## Windows release builds

SeekR supports 64-bit Windows 10 and Windows 11.

- **Installer:** `SeekR-Setup-<version>.exe` installs SeekR per-user under `%LOCALAPPDATA%\\Programs\\SeekR`, creates a Start Menu shortcut, and offers an optional desktop shortcut.
- **Portable:** `SeekR.exe` runs without installing the application.
- Neither option requires Python or administrator privileges.

Download both builds and the `SHA256SUMS.txt` manifest from the [latest GitHub Release](https://github.com/okyanus-11/SeekR/releases/latest). The executables are unsigned, so Windows may show a SmartScreen unfamiliar-app warning.

### Fresh installation

1. Download `SeekR-Setup-<version>.exe` from the official release page.
2. Run it as your normal Windows user. Administrator elevation should not be required.
3. Keep the default destination unless you have a reason to change it.
4. Finish setup and launch SeekR from the Start Menu.
5. Press `Alt + Space` to open the launcher.

### Updating or repairing an installation

Run the newer installer while SeekR is closed. The installer uses the same application ID, remembers the previous install directory, closes a running SeekR process when possible, and replaces the application files. It does not intentionally remove the user's data directory.

**Important:** CI validates a fresh install, launch, UI verification, and uninstall. A real upgrade from an older release with preservation of existing user data still requires manual validation on a physical Windows machine. Back up `%APPDATA%\\SeekR` before upgrading if the data matters.

### Uninstalling

Use **Settings → Apps → Installed apps → SeekR → Uninstall**, or the **Uninstall SeekR** Start Menu shortcut. The uninstaller removes the application files and shortcuts. It intentionally preserves `%APPDATA%\\SeekR`, which contains configuration, the SQLite database, notes, logs, and optional clipboard history.

To remove personal data too, first back up anything you need, uninstall SeekR, and then remove that folder yourself. Do not delete it if you want to preserve your settings or notes.

## Run from source

Requires Python 3.10 or newer (Python 3.12 recommended) on Windows or Linux:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

On Linux, activate the virtual environment with `source .venv/bin/activate`. Qt may require an X11/Wayland display session for interactive use. macOS is not currently supported or tested.

## Build on Windows

Use Python 3.12 and the pinned development requirements:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python build.py
python build.py --onedir
```

The portable executable is written to `dist\\SeekR.exe`; the onedir payload required by Inno Setup is written to `dist\\SeekR\\`.

Compile the installer using the same version as `core/version.py`:

```powershell
$version = python -c "from core.version import APP_VERSION; print(APP_VERSION)"
$compiler = Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\\ISCC.exe"
& $compiler "/DMyAppVersion=$version" ".\\installer\\seekr.iss"
```

The resulting installer is `dist\\installer\\SeekR-Setup-$version.exe`. GitHub Actions builds both executable formats, compiles the installer, checks its installed application and shortcuts, launches the installed app, verifies the packaged UI, uninstalls it, and generates SHA-256 checksums.

See the [Windows manual test checklist](WINDOWS_MANUAL_TEST.md) before describing native Windows integration or upgrade behaviour as fully verified.

## User data and privacy

SeekR stores its configuration, SQLite database, application logs, notes, and optional clipboard history under `%APPDATA%\\SeekR` on Windows. This data remains after uninstalling. Clipboard history is local and unencrypted; enable it only if you accept that copied content is stored on your device.
