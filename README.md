# SeekR

**A fast, keyboard-driven launcher for Windows 10 and 11.** Press `Alt+Space`, type what you need, press `Enter`.

SeekR is a native desktop application built with Python and PySide6. It searches your applications and files, evaluates expressions, opens websites, runs safe commands, previews documents, manages clipboard history and notes, and bundles a set of everyday developer utilities — all from one floating window.

**Current version:** 1.0.1 · **License:** MIT

> Plugins are **not** part of 1.0.0. The Settings → Plugins page shows the planned marketplace as *Coming Soon*; no plugin code is loaded or executed.

---

## Contents

- [Features](#features)
- [Screenshots](#screenshots)
- [Requirements](#requirements)
- [Installation](#installation)
- [Windows validation](#windows-validation)
- [Running from source](#running-from-source)
- [Building a standalone executable](#building-a-standalone-executable)
- [Keyboard shortcuts](#keyboard-shortcuts)
- [Keyword reference](#keyword-reference)
- [Configuration](#configuration)
- [Database](#database)
- [Themes](#themes)
- [Project structure](#project-structure)
- [Architecture](#architecture)
- [Testing](#testing)
- [Performance](#performance)
- [Windows compatibility](#windows-compatibility)
- [Troubleshooting](#troubleshooting)
- [Known limitations](#known-limitations)
- [Roadmap: plugins](#roadmap-plugins)
- [License](#license)

---

## Features

### Launcher

- Frameless, translucent, always-on-top search window with a keyboard-first workflow.
- Global hotkey (`Alt+Space` by default, configurable) with conflict detection and a clear error if the combination is already taken.
- Debounced live search, fuzzy matching with typo tolerance, ranking across providers, and result deduplication.
- Recent and frequently used applications influence ranking.
- Context menu for secondary actions, action cycling with `Tab`, and numbered actions with `Ctrl+1…9`.
- Subtle open/close/selection animations that can be disabled in Settings.
- Optional "hide when focus is lost", tray icon, and start-with-Windows support.
- Single-instance enforcement: launching SeekR again brings the existing window forward.

### Search providers

| Area | What it does |
|---|---|
| Applications | Discovers Start Menu shortcuts (`.lnk`), configured Program Files locations and additional user folders, extracts icons, supports aliases, exclusions, launch history and background re-indexing. Executables are launched directly — no shell. |
| Files & folders | Indexes configured directories in background threads (WAL SQLite index), respects excluded folders/extensions and hidden files, filters by extension (`ext:pdf`), opens files/folders, copies paths, shows metadata. |
| Calculator | SymPy-backed parser (no `eval`): arithmetic, powers, roots, trigonometry (degrees or radians), logarithms, factorials, constants (`pi`, `e`, `tau`, `phi`), percentages, scientific notation, unit conversion, configurable precision, calculation history. |
| Web search | Google, Bing, DuckDuckGo, YouTube, Wikipedia, GitHub, plus custom engines defined by URL templates. Configurable default engine and browser handling. |
| Translation | `translate: Hello to Turkish` builds a Google Translate URL; supports 20+ language names. |
| Dictionary | `define: algorithm` opens dictionary lookups and offers in-app definitions via the Dictionary tool page. |
| Commands | Built-in safe system commands and user-defined commands with confirmation for destructive actions, argument-safe execution, aliases and history. |
| Clipboard | Opt-in text clipboard history, off by default; copied text is stored unencrypted in the local database with hash-based deduplication, pinning, search, deletion and automatic pruning. |
| Notes | Lightweight notes with autosave, pinning, search and timestamps. |
| System info | Real CPU, memory, disks, GPU, battery, network, IP, uptime and OS data via `psutil` and platform APIs. No invented values. |
| Date & time | Current time, time-zone lookup and conversion, date differences, countdown timer, configurable formats. |
| Windows | Lists open windows and switches to the selected one (Windows API; unavailable elsewhere). |
| Emoji | Searchable emoji table; copies the selected emoji. |
| Color | HEX/RGB/HSL/HSV conversion, color picking, copyable values. |
| Screenshots | The Tools page has a Qt full-screen capture action that saves to the configured folder (Settings → Files); a separate action opens the Windows Snipping Tool for region capture. The Snipping Tool's save destination is controlled by Windows, not SeekR. Neither path has been verified with a real-display capture. |
| Processes | Search running processes with CPU/memory usage, details, and confirmation before termination. |
| Bookmarks | Reads browser bookmarks (Chrome, Edge, Brave, Firefox) when their profile files are readable; degrades gracefully otherwise. |
| QuickLook | Safe previews for images and text-like documents (never executes previewed files). |
| Quick Connect | SSH profiles with validation; passwords are never stored. |
| Power | Lists and switches Windows power schemes where `powercfg` supports it. |
| Quick Actions | Open folders, open websites, launch applications with arguments, copy predefined text. |
| Smart suggestions | Recent applications/files/searches when the query is empty; can be disabled. |

### Tools window

A single window with 14 pages: **Calculator**, **Developer tools**, **Date & time**, **Color**, **Dictionary**, **Screenshots**, **System**, **Processes**, **Power**, **Clipboard**, **Quick notes**, **Bookmarks**, **Quick Connect**, **Quick actions**.

The Developer tools page implements all 15 utilities:

1. UUID generator
2. Base64 encoder
3. Base64 decoder
4. JSON formatter
5. JSON validator
6. URL encoder
7. URL decoder
8. Hash generator (MD5, SHA-1, SHA-256, SHA-512)
9. Color converter
10. Regex tester
11. Timestamp converter
12. Text case converter
13. Character counter
14. Word counter
15. Hexadecimal converter

### Settings

Thirteen pages — General, Appearance, Search, Applications, Files, Web, Calculator, Commands, Clipboard, Privacy, Advanced, Plugins, About — all bound to the persisted JSON configuration. Every control writes through validation and takes effect immediately (theme changes repaint all windows).

### Themes

Dark, Light, AMOLED, Catppuccin Mocha, Dracula and Nord, with custom accent color, transparency, font family/size, window width, result spacing and animation toggle. The theme stylesheet is applied application-wide, not just to the launcher.

---

## Screenshots

No screenshots are included. The Qt full-screen capture and Windows Snipping Tool region-capture paths are separate; neither has been manually verified against a real display.

---

## Requirements

**End users:** Windows 10 or 11 (64-bit) and the built `SeekR.exe` — no Python installation needed.

**Development:**

- Python 3.10+ (developed and tested with 3.12)
- PySide6 ≥ 6.6
- psutil ≥ 5.9
- sympy ≥ 1.12
- tzdata ≥ 2024.1 (time zones on systems without a system tz database)

---

## Installation

See [docs/INSTALLATION.md](docs/INSTALLATION.md) for installation, build, and user-data details.

### From a local build

A native Windows executable and installer were validated on Windows 11. The
installer was installed, same-version reinstalled, launched, and uninstalled;
the Start Menu shortcut targeted the installed executable, and isolated
`%APPDATA%` test data survived uninstall. The visible launcher returned `4`
for `calc: 2+2`. The Python 3.12.10 Windows suite passed with two documented
platform skips.

This is not a public release. A true upgrade from an older installer, code
signing/SmartScreen, and several native shell integrations remain unverified.
`Alt+Space` was already registered by another application on the validation
PC, so an alternate hotkey was used instead. Repeated packaged launch activation
was inconsistent in that run: the request was forwarded but the window did not
reliably appear. The cause was identified and fixed afterwards, but the fix
still needs re-testing on a Windows desktop. See
[the Windows audit](docs/WINDOWS_AUDIT.md) for the full checklist. For a build
from source, see
[Building a standalone executable](#building-a-standalone-executable), then:

1. After a successful local build, place `SeekR.exe` in a folder you control (for example `%LOCALAPPDATA%\Programs\SeekR`).
2. Run it. Enable **Start with Windows** in Settings → General if desired.

User data is stored in `%APPDATA%\SeekR`, never next to the executable.

Locally built files are not a published release.

### Development setup

```bash
git clone https://github.com/okyanus-11/SeekR.git
cd SeekR
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements-dev.txt
```

---

## Windows validation

Before calling a build a Windows release, run the automated check on the target
Windows PC, then complete the manual GUI checklist.

### Prerequisites

- Windows 10 or Windows 11, 64-bit.
- Python 3.10 or newer, 64-bit. **Python 3.12 is recommended.** Install it from
  <https://www.python.org/downloads/windows/> and tick either “Add python.exe to
  PATH” or the Python launcher (`py`).
- Windows PowerShell 5.1 (built in) or PowerShell 7.
- An internet connection for the first `pip install`, and about 1 GB of free
  disk space for the virtual environment and build.
- No administrator rights are required for the test or build.
- Run the commands from the repository root (the folder containing `main.py`).

### Run the automated Windows checks

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\windows_test.ps1
```

In PowerShell 7:

```powershell
pwsh -NoProfile -File .\tools\windows_test.ps1
```

The script:

1. Verifies it is running on Windows and checks the Python version.
2. Creates or reuses `.venv` and installs `requirements-dev.txt`.
3. Verifies all runtime, test and build dependencies import.
4. Byte-compiles the source.
5. Runs the complete pytest suite with the native Windows Qt platform.
6. Checks `python main.py --version`.
7. Runs `build.py` and verifies `dist\SeekR.exe` and its Windows version
   metadata.

Each check is printed and saved as **PASS**, **FAIL** or **SKIPPED**. A full
report is written to **`windows_test_results.txt` in the repository root**. The
script exits with code `0` only when every required check passes; any failure
exits with code `1` and remains visible in the report.

On Windows 11 build 26300, the full suite passed with 169 tests at Python 3.12
(168 at Python 3.14) and 2 documented skips. The process-isolated
single-instance forwarding regression test ran as part of that suite. The Linux
suite passes **176 tests** on Ubuntu 24.04 with offscreen Qt. Automated checks
do not verify native GUI behavior; the Win32 hotkey, tray, window switching, and
Snipping Tool experience have not been manually verified. See
[Windows compatibility](#windows-compatibility).

### Manual GUI checks

Automated checks cannot verify Alt+Space, the tray, DPI, window activation or
how the app looks. After the automated report says `RESULT: PASS`, work through
[`docs/WINDOWS_MANUAL_TEST.md`](docs/WINDOWS_MANUAL_TEST.md). Record every row,
including failures and tests that could not be performed.

---

## Running from source

```bash
python main.py
```

Useful flags:

| Flag | Meaning |
|---|---|
| `--version` | Print the version and exit. |
| `--debug` | Verbose logging (also available as a setting). |
| `--no-hotkey` | Start without registering the global hotkey. |
| `--hidden` | Start without showing the launcher. |
| `--settings` | Open Settings on start. |
| `--tools` | Open the Tools window on start. |
| `--reset-config` | Reset the configuration to defaults. |
| `--allow-multiple` | Bypass the single-instance check (development only). |

---

## Building a standalone executable

On Windows, from the repository root:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe build.py
```

If you have already activated the virtual environment, `python build.py` is
equivalent. `build.py` checks for Python 3.10+, PySide6, psutil, sympy, tzdata
and PyInstaller before invoking PyInstaller, and prints the exact pip command if
something is missing.

The script:

1. Generates the icon assets if missing (`tools/make_icons.py`).
2. Writes a Windows version resource (product name, version 1.0.0, copyright) to `build/version_info.txt`.
3. Runs PyInstaller with `--onefile --windowed`, bundling `assets/` and `tzdata`.

Output on Windows: **`dist\SeekR.exe`** — a single-file, windowed GUI build with
the application icon and version resource, requiring no separately installed
Python. Use `--onedir` for a troubleshooting folder build at
`dist\SeekR\SeekR.exe`, or `--console` for a debug build that keeps a console
window and shows startup errors. On Linux the same command produces `dist/SeekR`
and `dist/SeekR/SeekR`, which are not Windows executables.

> Windows 11 build 26300: the automated suite passed (169 passed, 2 skipped at
> Python 3.12), the 62.8 MiB `dist\SeekR.exe` was built and its metadata
> checked, a hidden frozen-app startup smoke test passed, and the installer
> compiled with Inno Setup 6.7.3. Interactive Windows shell/GUI behavior and
> clean-profile installation remain unverified. See
> [Windows compatibility](#windows-compatibility).

---

## Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `Alt+Space` | Show/hide the launcher (global, configurable) |
| `↑` / `↓` | Move selection |
| `PageUp` / `PageDown` | Move selection by six rows |
| `Enter` | Run the primary action of the selected result |
| `Tab` / `Shift+Tab` | Cycle through all actions of the selected result |
| `Ctrl+1` … `Ctrl+9` | Run the action at that position |
| `Ctrl+C` | Copy the selected result (when no text is selected) |
| `Ctrl+,` | Open Settings |
| `Ctrl+T` | Open the Tools window |
| `Ctrl+R` | Re-index applications and files |
| `Esc` | Clear the action selection, then hide the launcher |
| Right-click a result | Context menu with every action |

---

## Keyword reference

Keywords are matched case-insensitively at the start of the query (`web: python`).

| Keyword | Example | Result |
|---|---|---|
| `web:` | `web: Raspberry Pi 5` | Opens the configured search engine |
| `calc:` | `calc: sqrt(144) + 25 * 4` | `112` |
| `comm:` | `comm: ipconfig` | Runs the built-in command (with confirmation where required) |
| `file:` | `file: invoice` | Searches the file index |
| `app:` | `app: discord` | Searches installed applications |
| `wiki:` | `wiki: ESP32` | Wikipedia search |
| `yt:` | `yt: DOOM soundtrack` | YouTube search |
| `gh:` | `gh: ESP32 projects` | GitHub search |
| `translate:` | `translate: Hello to Turkish` | Google Translate link |
| `unit:` | `unit: 100 km to miles` | `62.137119 mi` |
| `time:` | `time: Tokyo` | Current time in Tokyo |
| `define:` | `define: algorithm` | Dictionary lookup |
| `sys:` | `sys:` | Live system information entries |

Without a keyword SeekR still works: `25 * 48` produces a calculator result automatically, and `discord` ranks matching applications first.

Custom aliases are configured on Settings → Search (`{"w": "web"}` makes `w:` behave like `web:`). Aliases are validated, stored lowercase, and can never shadow an existing keyword.

---

## Configuration

- **Location:** `%APPDATA%\SeekR\config.json` on Windows; `$XDG_CONFIG_HOME/SeekR/config.json` (or `~/.config/SeekR`) on Linux; `~/Library/Application Support/SeekR` on macOS.
- **Override:** set `SEEKR_HOME` to use a portable/test directory for the config, database, logs and cache.
- **Validation:** on load, every value is coerced and clamped against defaults. A corrupt file is backed up as `config.corrupt.json` and defaults are used, so a bad edit cannot prevent startup.
- **Writes:** atomic (temporary file + replace), so an interrupted save cannot truncate the configuration.
- **Live updates:** configuration listeners repaint themes, re-register hotkeys and refresh pages without a restart.

---

## Database

SQLite at `%APPDATA%\SeekR\seekr.db` (WAL mode, busy timeout, per-thread connections).

Tables: `apps`, `files`, `clipboard`, `notes`, `history`, `custom_commands`, `ssh_profiles`, `quick_actions`, `meta`.

- Clipboard history is off by default. When explicitly enabled, copied text is
  stored unencrypted in the local database; entries are deduplicated by hash
  and pruned to the configured limit, with pinned entries exempt.
- History retention is configurable (Privacy page) and applied at startup.
- The file index can be cleared/rebuilt from Settings → Files.
- **Vacuum database** is available on Settings → Advanced.
- No data leaves the machine; clipboard contents are never transmitted.

---

## Themes

| Theme | Character |
|---|---|
| Dark | Neutral graphite with blue accent |
| Light | Soft off-white surfaces |
| AMOLED | True black, high contrast |
| Catppuccin Mocha | Muted pastel dark |
| Dracula | Purple-tinted dark |
| Nord | Cool arctic blue-grey |

Accent color, transparency, font, window width, result spacing and animations are configurable per user and persisted. Theme switching updates every open window immediately.

---

## Project structure

```
SeekR/
├── main.py                     # CLI entry point, QApplication bootstrap
├── build.py                    # PyInstaller build script + Windows metadata
├── requirements.txt            # Runtime dependencies
├── requirements-dev.txt        # + pytest, PyInstaller
├── pytest.ini
├── assets/icons/               # Generated PNG + multi-size ICO
├── core/
│   ├── application.py          # Composition root, providers, tray, hooks
│   ├── search_engine.py        # SearchProvider contract, keywords, ranking
│   ├── config_manager.py       # Defaults, validation, atomic persistence
│   ├── database.py             # Schema and all domain queries
│   ├── fuzzy.py                # Similarity, scoring, subsequence matching
│   ├── hotkeys.py              # Win32 RegisterHotKey + native event filter
│   ├── hotkey_manager.py       # Hotkey parsing/registration facade
│   ├── startup.py              # Start-with-Windows registration
│   ├── single_instance.py      # Local socket based single instance
│   ├── workers.py              # QThreadPool jobs, cancel tokens, debouncer
│   ├── hooks.py                # UIHooks protocol + NullHooks
│   ├── logging_setup.py        # Rotating log files
│   ├── errors.py               # Global exception hook
│   ├── paths.py                # Per-user directories, SEEKR_HOME
│   └── models.py               # SearchResult, ResultAction
├── features/                   # Services + search providers (UI-free)
│   ├── applications.py  files.py  calculator.py  web_search.py
│   ├── dictionary.py    commands.py  clipboard.py  notes.py
│   ├── system_info.py   developer_tools.py  date_time.py
│   ├── window_search.py emoji_search.py  color_tools.py
│   ├── screenshots.py   process_manager.py  bookmarks.py
│   ├── quicklook.py     quick_connect.py  power.py  quick_actions.py
│   └── util.py
├── ui/
│   ├── launcher_window.py      # Frameless launcher, keyboard model
│   ├── settings_window.py      # 13 settings pages
│   ├── tools_window.py         # 14 tool pages
│   ├── tools/basic.py          # Calculator, developer, date/time, color, dictionary
│   ├── tools/system.py         # System, processes, power, screenshots
│   ├── tools/data.py           # Clipboard, notes, bookmarks, SSH, actions
│   ├── components.py  dialogs.py  themes.py  icons.py  i18n.py
├── docs/                       # Architecture, audit and performance notes
├── tools/                      # Icon generator, benchmark, Windows test runner
├── tests/                      # pytest suite, incl. windows compatibility
├── CHANGELOG.md                # Release notes
└── README.md
```

---

## Architecture

SeekR is layered so that features never depend on the UI:

1. **Core** — configuration, SQLite, search engine, hotkeys, logging, workers.
2. **Features** — plain Python services and `SearchProvider` implementations. Providers return `SearchResult` objects whose callbacks do the work; side effects that need the UI (hide the launcher, change theme, show a dialog) go through the `UIHooks` protocol.
3. **UI** — PySide6 windows and widgets. The composition root (`core/application.py`) wires every service, provider, hook and window together.

**Adding a provider** (the future plugin path): subclass `SearchProvider`, implement `search()`, optionally `suggestions()` and `empty_help()`, and register it with `SearchEngine.register()`. Keywords and aliases are resolved centrally, so a provider cannot introduce keyword conflicts. Errors raised by a provider are contained and surfaced as an "unavailable" result instead of crashing the launcher.

Heavy work (file indexing, application scanning, clipboard polling, process sampling) runs on Qt threads or thread-pool jobs; the GUI thread only renders results. Indexing can be cancelled and reports progress/errors.

More detail: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Testing

```bash
pytest
```

The suite covers configuration validation/persistence, database operations, fuzzy matching, calculator expressions and errors, keyword detection/aliases/ranking, provider failures, web URL generation, command parsing and safety, date/time conversion, file indexing, application discovery, clipboard, notes, quick actions, SSH validation, system info, process listing/termination, emoji search, QuickLook, and headless GUI integration (launcher navigation, execution, settings and tools pages).

GUI tests require a Qt platform; on a headless machine use:

```bash
QT_QPA_PLATFORM=offscreen pytest
```

On Ubuntu 24.04 with Python 3.12 and `QT_QPA_PLATFORM=offscreen`, the current
suite passes **176 tests** with no failures or skips. Five regression tests
(four for repeated activation, one for quitting) were added after the Windows
validation run above and have not yet run on Windows.

The Windows suite passed on Windows 11 build 26300; mocked or source-level
checks do not establish native GUI behavior. In particular, real-display
capture and the Snipping Tool's save destination are not established by tests.
The full evidence process is in [docs/WINDOWS_AUDIT.md](docs/WINDOWS_AUDIT.md).

---

## Performance

Windows source-mode performance measurements have been run on a Windows 11
machine. They cover headless/controller and synthetic workloads, not the
packaged build or visible-display responsiveness. Results, methodology, and
limitations are in [docs/WINDOWS_PERFORMANCE.md](docs/WINDOWS_PERFORMANCE.md)
and [docs/PERFORMANCE.md](docs/PERFORMANCE.md).

---

## Windows compatibility

Automated tests, a frozen-app startup smoke test, executable packaging,
installer compilation, and install/reinstall/uninstall ran on Windows 11 build
26300. Native Win32 hotkey, tray, window-switching, and Snipping Tool UX have
not been manually verified, and tests do not establish real-display capture or
where Snipping Tool saves captures. No release has been published. See
[docs/WINDOWS_AUDIT.md](docs/WINDOWS_AUDIT.md) for the evidence and
[docs/WINDOWS_MANUAL_TEST.md](docs/WINDOWS_MANUAL_TEST.md) for the checklist.

---

## Troubleshooting

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for additional
troubleshooting guidance.

| Symptom | Fix |
|---|---|
| Hotkey does nothing | Another application owns the combination. Settings → General shows the registration error; choose a different hotkey. Run SeekR without elevation conflicts: Windows does not deliver some hotkeys across integrity levels. |
| Applications missing | Settings → Applications → **Refresh index**. Portable apps can be added under **Additional application folders**; anything else can be launched with Quick Actions. |
| File results empty | Add at least one directory on Settings → Files and run a re-index (`Ctrl+R`). |
| Time zones wrong | `tzdata` must be installed (it is bundled in the executable). |
| Clipboard history not updating | Enable clipboard history in Settings → Clipboard or Privacy. It is off by default and stores copied text unencrypted in the local database. |
| Settings window empty/odd after an upgrade | Close SeekR, delete `%APPDATA%\SeekR\config.json` (a backup is created automatically when validation fails). |
| Logs | `%APPDATA%\SeekR\logs\seekr.log` (rotating). Enable debug logging on Settings → Advanced for detail. |
| PowerShell script is blocked | Run it with `-ExecutionPolicy Bypass` as shown in [Windows validation](#windows-validation). |
| `py` not found | Reinstall Python with the Python launcher enabled, or run `python --version` and use a Python on `PATH`. |
| Build says packages are missing | Run `.venv\Scripts\python.exe -m pip install -r requirements-dev.txt`, then `.venv\Scripts\python.exe build.py`. |
| `dist\SeekR.exe` is missing | Read the build output in the report; fix the first error (usually a missing package or a locked `dist` folder), then rerun. Use `--console` for a diagnostic build. |
| Reporting a failure | Include `windows_test_results.txt`, the test ID from `docs/WINDOWS_MANUAL_TEST.md`, `%APPDATA%\SeekR\logs\seekr.log`, Windows version, display scaling and steps to reproduce. Open an issue at <https://github.com/okyanus-11/SeekR/issues>. Never include passwords or private clipboard/note content. |

---

## Known limitations

- **Windows verification:** automated tests, a frozen-app startup smoke test, executable packaging, installer compilation, and install/reinstall/uninstall ran on Windows 11 build 26300. Native hotkey, tray, window switching, Snipping Tool UX and Windows 10 remain unverified manually. Repeated launch activation was inconsistent in that run; the cause was fixed afterwards and needs re-confirmation on a desktop. See [docs/WINDOWS_AUDIT.md](docs/WINDOWS_AUDIT.md) for the verified/unverified split.
- **Language:** Settings offers English and Türkçe; in 1.0.0 only the launcher shell is translated. Tool and settings pages remain English. This is a documented partial feature, not a stub.
- **GPU utilisation:** shown only when the platform exposes it (NVML/`nvidia-smi` or Windows counters); otherwise the UI says it is unavailable rather than inventing a number.
- **Bookmarks:** browsers must be closed or use readable profile files; encrypted/locked stores are skipped with a message.
- **Dictionary:** `define:` opens a web lookup; offline definitions are not bundled.
- **Screenshots:** SeekR has a Qt full-screen capture/save-to-configured-folder path and a separate Windows Snipping Tool region-capture action. Real-display capture is not verified, and SeekR does not establish the Snipping Tool's save destination.
- **SSH:** requires an `ssh` client on `PATH`; SeekR never stores passwords (key files or agent authentication only).
- No screenshots are shipped; no real-display capture has been verified.

---

## Roadmap: plugins

Version 1.0.0 intentionally ships **no plugin loading and no third-party code execution**. The provider interface, centralized keyword resolution and `UIHooks` boundary are the extension points a future plugin system will use. Settings → Plugins currently presents the planned marketplace as *Coming Soon* with no fake install buttons.

---

## License

MIT — see [LICENSE](LICENSE).

Copyright (c) 2026 Okyanus Bora Şevik.

Built with Python, PySide6, SymPy, psutil and SQLite.
