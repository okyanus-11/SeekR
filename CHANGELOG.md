# Changelog

All notable changes to SeekR are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
semantic versioning.

## [Unreleased]

### Added

- Seven additional languages: Spanish, French, German, Italian, Brazilian
  Portuguese, Japanese and Simplified Chinese. Launcher text, common controls,
  shared headings and Tools navigation now use the localization catalog.
- Persistent local caching for dictionary definitions, allowing previous
  lookups to work offline.
- Windows GPU Engine performance-counter fallback for non-NVIDIA adapters.
- Multi-monitor full-screen screenshot composition.

### Fixed

- Firefox bookmarks now use SQLite's backup API for consistent snapshots that
  include live WAL data; Chromium bookmark reads fall back to Bookmarks.bak.
- Quick Connect finds the standard Windows OpenSSH installation even when the
  executable is not on PATH.
- Locale aliases such as pt_br and zh are normalized safely.

### Added

- Windows and Linux CI, plus a per-user Windows installer build and downloadable
  executable/installer artifacts.
- Installation and troubleshooting guides for source, executable and installer
  workflows.

### Changed

- Clipboard history is opt-in and requires explicit consent; Settings discloses
  that copied text is stored unencrypted in the local database.
- Pin runtime and build dependencies to exact versions.
- Limit PyInstaller collection to modules discovered as used instead of
  collecting all PySide6 and Shiboken modules.

### Fixed

- A second launch on Windows could miss the running instance and start a second
  copy instead. `notify_existing()` reported failure whenever the show request
  had already been handed to the OS, and the caller then took the single-
  instance socket name for itself. It now only waits for bytes still queued.
- `notify_existing()` could still report `False` on Windows even though the
  request was delivered: `connectToServer`/`waitForConnected` can fail
  spuriously under the offscreen QPA (and, on a real desktop, during slow
  startup), and `waitForBytesWritten` reports `False` for a buffer already
  flushed to the OS. It now retries the connection within the timeout budget
  and never treats the flush result as failure.
- Repeated activation of an already-running instance now reliably brings the
  launcher forward. A show request used to be able to produce a window that was
  visible but not active, which the "hide when focus is lost" timer then hid
  again, so a forwarded launch looked ignored. Showing the launcher now cancels
  the pending hide and retries foreground activation for one second; a fade-out
  interrupted by a show can no longer hide the re-shown window; and the
  launching process passes its foreground permission to the running instance
  before asking it to show.
- Quitting SeekR now really stops it. `QCoreApplication.quit()` proved to be a
  no-op while the application controller was running (the event loop survived
  every delay from 100 ms to 3 s), so the tray's Quit action did nothing; the
  quit path now calls `exit(0)` directly, which always stops the loop.
- Launch Windows SSH clients directly in a new console rather than composing
  commands through `cmd.exe`.

### Tests

- Regression tests for repeated activation: a refused foreground activation, the
  activation grace period, an interrupted hide animation, and a forwarded socket
  request revealing a hidden launcher.

## [1.0.0] — 2026-11-14

### Added

- Windows compatibility audit (`docs/WINDOWS_AUDIT.md`) and a Windows
  performance measurement plan (`docs/WINDOWS_PERFORMANCE.md`).
- 26 Windows-focused tests covering argument quoting, Explorer selection,
  Known Folders, hidden attributes, Program Files scanning, Start Menu toggle,
  custom application folders, non-blocking app indexing, mocked hotkey and
  Run-key behaviour, mocked `powercfg`, GPU PowerShell parsing/caching,
  file-limit semantics, process protection, single-instance forwarding, tray
  lifetime, build paths, Windows config round-trips, UTF-16 previews and the
  screenshot folder.
- Configurable screenshot folder (Settings → Files) and additional application
  folders (Settings → Applications), backed by persisted settings.
- A Windows validation runner (`tools/windows_test.ps1`) that creates a
  virtual environment, installs dependencies, runs checks, builds
  `dist\SeekR.exe`, verifies its metadata and writes a PASS/FAIL/SKIPPED report.
- A manual GUI validation checklist (`docs/WINDOWS_MANUAL_TEST.md`).
- Changelog.

### Fixed

- 64-bit `HWND` truncation and an invalid `GlobalFree` in window enumeration.
- Hotkey changes could leave no working hotkey; the previous combination is
  restored and the error is shown.
- Tray menu lifetime and enabling the tray after startup with it disabled.
- Start Menu indexing switch was ignored; Program Files scans were fragile and
  duplicated entries; application scanning blocked the GUI thread.
- Windows Known Folder resolution for OneDrive-redirected/localised profiles.
- Hidden/system file detection, reparse-point traversal and file-limit
  reporting during indexing.
- UTF-16/UTF-8 BOM text previews, Firefox WAL bookmarks, Snipping Tool launch,
  `powercfg` exit-status handling and protected-process termination.
- Windows argument splitting and Explorer `/select` quoting.
- Blocking GPU/CPU system-information queries; the GPU snapshot is cached and
  refreshed off the GUI thread.
- `--onedir` artifact detection and build resource paths.
- Single-instance socket cleanup and duplicate activation.
- Start-minimized was ignored; appearance changes reopened the launcher.

### Initial release

- SeekR desktop launcher: search providers, calculator, web search, commands,
  file indexing, clipboard history, notes, tools, settings, themes, tray/hotkey
  support and a PyInstaller build script.

### Known limitations at the original 2026-11-14 audit

- The original audit ran in headless Linux without Wine and therefore did not
  build or launch a native Windows executable or exercise Windows-only APIs.
- See `docs/WINDOWS_AUDIT.md` for the full evidence classification and the
  Windows follow-up validation and remaining release checklist.
