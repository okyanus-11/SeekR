# Changelog

All notable changes to SeekR are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
semantic versioning.

## [Unreleased]

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

- Launch Windows SSH clients directly in a new console rather than composing
  commands through `cmd.exe`.

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
