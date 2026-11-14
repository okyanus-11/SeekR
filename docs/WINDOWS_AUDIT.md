# Windows compatibility audit — SeekR 1.0.0

Date: 2026-11-14

## Scope and environment

This audit inspected every source module, the test suite, the build script and
the runtime assets of SeekR 1.0.0. The audit host was a **headless Linux x86-64
container** (Python 3.12.3, PySide6 6.12.0, psutil 7.2.2, SymPy 1.14.0,
SQLite with WAL). It had:

- no Windows installation or Windows VM,
- no Wine or other Win32 compatibility layer,
- no display server (Qt ran with `QT_QPA_PLATFORM=offscreen`),
- no PyInstaller Windows bootloader (PyInstaller cannot cross-compile).

Consequently this document distinguishes three kinds of evidence:

| Label | Meaning |
|---|---|
| **REAL** | Executed in this environment against real files, SQLite, Qt widgets or the real Python standard library. |
| **SIMULATED** | Windows path/argument/registry behaviour exercised by injecting Windows semantics (for example `os.name == "nt"` or `windows=True`) into real code. |
| **MOCKED Win32** | Code that calls a Win32 API was exercised with a fake implementation of that API. This proves the call sequence and error handling, not Windows behaviour. |
| **UNVERIFIED** | Requires Windows and was not executed. It must not be treated as tested. |

**Bottom line:** the application code was deeply audited and repaired, and its
cross-platform logic is covered by 154 passing tests. A genuine Windows
`SeekR.exe` was **not** built or launched, and no Windows-only API was executed
on Windows. The Windows release therefore remains *unverified* until the
checklist at the end of this document is run on real Windows 10/11 hardware.

## Method

1. Read the whole repository: entry point, core services, all feature services,
   all search providers, Qt windows/pages, build script, assets, tests and
   documentation.
2. Grepped for platform branches, subprocess use, shell invocation, hard-coded
   paths, encoding assumptions, thread boundaries and Win32 `ctypes` calls.
3. Ran the existing suite to establish a baseline (128 passing tests on Linux).
4. Repaired concrete defects (below), keeping the architecture and all features.
5. Added `tests/test_windows_compat.py` with 26 tests, each explicitly labelled
   `[REAL]`, `[SIMULATED]` or `[MOCKED Win32]`.
6. Ran the full suite, byte-compilation, `main.py --version`, and PyInstaller
   packaging on Linux as far as it is meaningful.
7. Parsed the shipped `.ico` and the generated Windows version resource with
   PyInstaller's own parsers to validate their structure.

## Defects found and fixed

### Launcher, focus, hotkey and tray

| # | Finding | Fix | Evidence |
|---|---|---|---|
| 1 | Window enumeration used 32-bit `HWND` ctypes signatures; 64-bit handles were truncated. The enumeration callback also called `GlobalFree` on a pointer it did not own. | Correct 64-bit signatures, callback lifetime handling, no invalid free. | Code review; non-Windows fallback test |
| 2 | Setting a new hotkey could leave SeekR with **no** working hotkey when re-registration failed. | Register the new combination first; restore the previous one on failure; expose `last_error`; Settings verifies registration and reverts the field. | `test_hotkey_registration_and_failure_reporting` (MOCKED Win32) |
| 3 | The tray menu object had no retained reference and could be garbage-collected; the tray could not be enabled after starting with it disabled. | Retain `_tray_menu`, create the tray lazily when the setting changes, avoid duplicates. | `test_tray_menu_is_retained_and_created_on_demand` (REAL Qt / availability mocked) |
| 4 | Windows could leave the frameless launcher behind other windows after a hotkey press. | Added a platform `force_foreground()` helper and applied it only on Windows; no-op elsewhere. | Code review; Linux fallback test |
| 5 | "Hide when focus is lost" could hide the launcher while a modal child dialog was open. | Skip deactivation hiding while a modal dialog is active. | Code review; existing GUI tests |
| 6 | `general.start_minimized` was stored but ignored at startup. | Honoured by the entry point when `--hidden` is not given. | Code review |
| 7 | Appearance changes reopened the launcher instead of repainting it. | Added `refresh_appearance()` and used it for live theme/config changes. | Existing GUI tests |
| 8 | Single-instance code could signal activation twice and left sockets/server objects open. | One explicit activation signal, tracked and closed sockets, server closed at exit. | `test_single_instance_forwards_activation` (REAL, Linux backend) |
| 9 | Startup registration was not reconciled with the configuration. | Compare the Run-key/autostart state at startup and correct the stored setting. | `test_startup_registry_toggle` (MOCKED Win32) |

### Application discovery

| # | Finding | Fix | Evidence |
|---|---|---|---|
| 10 | `applications.index_start_menu` was ignored; disabling Start Menu indexing still scanned it. | The switch is honoured, with a helpful empty-state message. | `test_application_scan_respects_start_menu_toggle` (SIMULATED) |
| 11 | Program Files scanning assumed non-empty environment variables, included `WindowsApps`/recycle-bin noise, produced duplicates and could raise on unreadable directories. | Robust root resolution, skip markers, case-insensitive dedupe, `onerror` handling, depth cap. | `test_program_files_scan_is_robust` (SIMULATED) |
| 12 | Application scanning ran synchronously from the search provider, freezing the launcher on first use. | Provider returns an "Indexing applications…" result and requests a background re-index; results refresh afterwards. | `test_application_provider_never_indexes_on_the_gui_thread` (REAL) |
| 13 | Applications from user-chosen portable folders could not be added at all. | Added `applications.directories`, a Windows-aware scanner (`.lnk`, `.exe`; `.desktop` elsewhere) and a Settings → Applications list editor. | `test_custom_application_folder_scans_lnk_files` (SIMULATED path) |
| 14 | `.lnk`/`.exe` paths with spaces or arguments were vulnerable to quote handling. | Shared Windows-correct argument splitter is used for commands; `.lnk` files are opened through the shell, executables launched with an argument vector. | `test_split_args_windows_quoting` (REAL parser, Windows rules) |


### File search, indexing and paths

| # | Finding | Fix | Evidence |
|---|---|---|---|
| 16 | Default folders were assumed to be `~/Desktop`, `~/Documents`, `~/Downloads`, wrong under OneDrive redirection and localised Windows profiles. | Resolve Windows Known Folders through `SHGetKnownFolderPath` with a safe fallback. | `test_known_folder_fallback_and_defaults` (MOCKED Win32 / SIMULATED) |
| 17 | Hidden/system files were not detected on Windows; only dotfiles were skipped. | `FILE_ATTRIBUTE_HIDDEN`/`SYSTEM` are checked via `GetFileAttributesW` with the correct signature. | `test_windows_hidden_attribute_detection` (MOCKED Win32) |
| 18 | Directory traversal could follow junctions/symlinks into cycles or unrelated trees on Windows. | Do not traverse reparse points/symlinks by default; skip protected/system locations; keep depth and entry limits. | Code review; indexing tests |
| 19 | Reaching `max_files` was reported as a user cancellation. | Separate `limit_reached` from `cancelled`, with a clear status message. | `test_file_index_limit_is_not_reported_as_cancellation` (REAL, 1002 files) |
| 20 | Indexing errors on individual directories could abort the whole run. | Per-entry and per-directory error handling; the run continues and reports skipped paths. | Code review; indexing tests |
| 21 | Text previews assumed UTF-8, garbling Notepad-style UTF-16 files. | Detect UTF-16 LE/BE and UTF-8 BOMs, then fall back to the platform preferred encoding. | `test_text_preview_decodes_windows_utf16` (REAL) |
| 22 | `reveal in Explorer` built fragile quoting and did not select the file. | `explorer.exe /select,"<path>"` construction with validation, and a separate open-folder path. | `test_explorer_select_command` (REAL) |

### Windows features

| # | Finding | Fix | Evidence |
|---|---|---|---|
| 23 | `powercfg` was invoked by bare name and its exit status was ignored, so failures looked like success. | Resolve the absolute system executable, return `(returncode, output)`, handle non-zero exits and decode errors. | `test_powercfg_uses_exit_status` (MOCKED subprocess) |
| 24 | Critical Windows processes (and SeekR itself) could be terminated from the process manager. | Refuse protected PIDs/names and self-termination with an explanatory result. | `test_critical_processes_are_protected` (REAL on Linux names + policy) |
| 25 | Snipping Tool launch failed when the `ms-screenclip:` handler was absent; screenshot location was not configurable in the UI. | Direct URI launch with a documented fallback, race-safe file checks, and a Settings → Files screenshot-folder editor. | `test_screenshot_directory_setting_is_used` (REAL) |
| 26 | Firefox bookmarks ignored the WAL file, so recent bookmarks were missing or the copy was inconsistent. | Copy `places.sqlite` together with `-wal`/`-shm` before reading. | Code review |
| 27 | Commands ignored `general.confirm_destructive_actions`, decoded output strictly, and relied on Unix-only signals for sleep/lock. | Honour the setting, decode with replacement, use ctypes on Windows with a portable fallback, improve Recycle Bin messages. | Code review; command tests |
| 28 | GPU/system information blocked the GUI thread with PowerShell/WMI, and CPU sampling blocked for 150 ms per refresh. | Non-blocking CPU sampling, cached GPU snapshot refreshed by a daemon thread, UTF-8 PowerShell output and `errors="replace"`. | `test_gpu_probe_never_blocks` and `test_windows_gpu_query_forces_utf8` (MOCKED subprocess) |
| 29 | SSH detection and terminal launching used Unix assumptions on Windows. | Detect `ssh.exe`/OpenSSH and use Windows Terminal or `cmd` appropriately. | Code review |
| 30 | Default screenshot, quick-action and notes locations used POSIX assumptions. | Known-folder/`%APPDATA%` based defaults. | Path tests |

### Configuration, database and build

| # | Finding | Fix | Evidence |
|---|---|---|---|
| 31 | Configuration directory used one platform-neutral path and could fall back inside the install tree. | `%APPDATA%\SeekR` on Windows, `~/.config/SeekR` on Linux, Application Support on macOS; `SEEKR_HOME` override; executable location never used for user data. | `test_windows_paths_survive_config_roundtrip` (REAL config, Windows path strings) |
| 32 | Configuration writes must survive interruption and Windows replace semantics; corrupt JSON must not block startup. | Reviewed the existing same-directory temporary-file + `os.replace` write and corrupt-file backup; retained and covered by tests. | Existing config tests |
| 33 | `--onedir` packaging reported/detected the wrong artifact path. | `output_target()` resolves `dist/SeekR.exe`, `dist/SeekR`, or `dist/SeekR/SeekR` per platform/mode. | `test_build_output_paths` (REAL) |
| 34 | The build could leave its spec and version resource in the source root. | `--specpath build`, version resource written to `build/version_info.txt`. | Build run below |
| 35 | The Windows icon and version metadata were not structurally validated. | Generated multi-size ICO; parsed it and the version resource with PyInstaller's parsers. | Build validation below |

## Verification actually performed

### Test suite

Command (Linux, offscreen Qt):

```bash
QT_QPA_PLATFORM=offscreen SEEKR_HOME=/tmp/seekr_test pytest -q
```

Result: **154 passed, 0 failed, 0 skipped** (exit code 0). This includes the
pre-existing 128-test suite and 26 new Windows-compatibility tests. The new
tests are labelled by evidence type; none of them claims to have executed a
Win32 API. `python -m compileall` over `core`, `features`, `ui`, `main.py`,
`build.py` and `tests` succeeds. `python main.py --version` prints
`SeekR 1.0.0`.

Windows coverage inside the 26 tests includes: argument quoting, Explorer
selection, Known Folder fallbacks, hidden attributes, Program Files scanning,
Start Menu toggle, custom shortcut folders, non-blocking application indexing,
mock hotkey registration/failure rollback, mock Run-key startup, mocked
`powercfg`, UTF-8 PowerShell GPU parsing and caching, file-limit semantics,
critical-process protection, real single-instance forwarding on the Linux
backend, tray menu lifetime/lazy creation, non-Windows window fallback, build
artifact paths, config round-trips with Windows paths, UTF-16 text previews and
the screenshot directory setting.

### Packaging

PyInstaller 6.22.3 was installed and `python build.py --onedir` and
`python build.py` were executed **on Linux**. They produced:

- `dist/SeekR/SeekR` (onedir, 13.5 MiB directory build)
- `dist/SeekR` (onefile, 73.0 MiB, ELF x86-64 — not a Windows executable)

Both were launched with `QT_QPA_PLATFORM=offscreen` and an isolated
`SEEKR_HOME`. `--version` printed `SeekR 1.0.0`; the GUI initialised, registered
all providers, created `seekr.db` and logs in the isolated data directory, and
indexed in the background. This proves the frozen import graph, asset
bundling and data-directory logic work in a PyInstaller build **on Linux**. It
does not prove the Windows executable works.

The generated `assets/icons/seekr.ico` contains seven PNG-compressed entries
(16, 24, 32, 48, 64, 128, 256 px); PyInstaller's Windows icon reader accepts
all of them. The generated `build/version_info.txt` parses as a
`VSVersionInfo` with product name `SeekR`, version `1.0.0`, description,
company, copyright and original filename `SeekR.exe`. On Windows, PyInstaller
will embed these resources; the .exe itself has **not** been produced here.

## Not verified (requires Windows)

The following must be treated as unverified until run on real Windows 10/11:

1. Building `dist/SeekR.exe` with the Windows PyInstaller bootloader and
   embedding the icon/version resource into the PE file.
2. Launching that `.exe` (including no console window, no Python required,
   first-run directory creation in `%APPDATA%\SeekR`, and clean exit).
3. Global `Alt+Space` and configurable hotkeys via `RegisterHotKey`, conflict
   detection, and hotkey release on exit.
4. Tray icon visibility, context menu, show/hide, and quit through the Windows
   shell notification area.
5. Start Menu `.lnk` enumeration, COM resolution, extracted icons, launching
   shortcuts with spaces in paths, and UWP/WindowsApps entries.
6. Window enumeration and switching through the real Win32 API, including
   elevated windows and multiple monitors.
7. `powercfg` scheme listing/switching with real Windows power schemes.
8. Snipping Tool overlay (`ms-screenclip:`) and saved screenshot files.
9. Start-with-Windows via the `HKCU\...\Run` key, including upgrading the
   executable path.
10. Clipboard monitoring under the Windows clipboard, including image
    clipboard content and locked-clipboard retries.
11. Browser profile discovery (Chrome/Edge/Brave/Firefox) on real profiles,
    including locked/WAL databases.
12. GPU/WMI/PowerShell system information on real hardware, and CPU/memory
    readings under Windows.
13. Frameless-window activation/focus, click-outside-to-hide, Escape, DPI
    scaling, multi-monitor placement and animations.
14. Named-pipe single-instance forwarding (the code uses Qt's local socket,
    which maps to a named pipe on Windows; only the Linux backend was run).
15. Windows notifications/balloon messages and their suppression settings.
16. Antivirus/SmartScreen behaviour, code signing and long-path (>260 chars)
    support. SeekR does not ship a long-path manifest; deep paths may fail.
17. Any Windows performance number. None is reported in
    `docs/WINDOWS_PERFORMANCE.md`.

## Residual risks

- **Mocked Win32 signatures can still be wrong in detail.** The 64-bit HWND
  and `GetFileAttributesW` signatures were corrected against the Windows API
  documentation, but only a Windows run can prove them.
- **COM/shell behaviour** (`.lnk` icons, Start Menu, tray) can differ between
  Windows versions, shell replacements and locked-down enterprise profiles.
- **Frozen Windows imports** can differ from Linux. PyInstaller's Windows
  analysis was not run; a missing hidden import would only appear there.
- **PNG-compressed icons** are accepted by current PyInstaller and Windows
  Vista+, but Explorer rendering was not inspected.
- **Performance on Windows** is unknown; NTFS, Defender and cold starts can
  change indexing and startup behaviour substantially.

## Reproduce this audit

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate ; Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt

python -m compileall core features ui main.py build.py tests
python main.py --version
QT_QPA_PLATFORM=offscreen pytest -q        # Linux headless
python build.py --onedir                   # Linux build for packaging checks
```

## Required Windows release checklist

Run these on a clean Windows 10 and Windows 11 machine before publishing a
release and record the results:

1. `py -3.12 -m venv .venv && .venv\Scripts\pip install -r requirements-dev.txt`
2. `.venv\Scripts\python -m pytest -q` — all tests must pass (real Windows run).
3. `.venv\Scripts\python main.py --version` and `python main.py`.
4. `.venv\Scripts\python build.py` and `python build.py --onedir`.
5. Launch `dist\SeekR.exe`: verify no console, first-run data in
   `%APPDATA%\SeekR`, icon in Explorer/taskbar, and no missing-module dialog.
6. Exercise every Phase 6 item: Alt+Space, Escape, app/file/calculator/web/
   command search, settings, all themes, tools pages, clipboard, notes
   persistence, tray, clean exit, restart with preserved settings.
7. Check hotkey conflict handling with another app owning `Alt+Space`.
8. Check a non-admin account, a path with spaces and Unicode, a OneDrive-
   redirected profile, 125%/150%/200% DPI, and a second monitor.
9. Run `python tools/benchmark.py` and record the hardware/OS in
   `docs/WINDOWS_PERFORMANCE.md`.
10. Only then change the README status from "unverified on Windows" to
    "verified", with the tested Windows versions and date.
