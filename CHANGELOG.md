# Changelog

## [2.0.0] - 2026-11-19

### Added

- Local multi-step workflows with validated steps, preview, cancellation, progress,
  per-step errors, and versioned JSON import/export.
- A reusable snippets manager with categories, aliases, search, explicit copy,
  and validated JSON backup/restore.
- A local task manager with due dates, notes, completion state, launcher search,
  and a compact launcher task-summary widget.
- A unified Command Center, explicit command chains, and safer window-management
  actions for switching, tiling and minimizing.
- Natural-language file filters for extension, local calendar date and size,
  plus opt-in local content search for configured roots and text extensions.
- Configurable refresh intervals for launcher widgets and reduced-motion support
  in shared animated controls.

### Changed

- File-content search now has strict candidate and aggregate read budgets.
- File indexing preserves the last complete snapshot on cancellation, inaccessible
  folders and index-limit exits.
- Hidden launcher widgets stop polling; network-backed widgets fetch outside the
  UI thread and refresh only when active.
- Clipboard history applies age-based retention to unpinned entries while
  preserving pinned entries.
- Widget layout, visibility, theme application and refresh behavior are covered
  by Qt regression tests.

### Fixed

- Widget cards no longer disappear or detach after settings refreshes, theme
  changes, launcher hide/show cycles or asynchronous refreshes.
- Calendar-day file searches now use local midnight boundaries, so “yesterday”
  excludes files modified today.
- Snippet and workflow restore validate complete imports before database writes
  and report storage/encoding failures without crashing the Tools window.

### Validation

- Linux, Windows 10/11 runner matrix tests pass.
- Windows portable and onedir builds pass; packaged UI verification, installer
  build, install, launch, UI smoke test and uninstall pass.
- CI publishes the portable executable, installer and SHA-256 manifest as
  downloadable workflow artifacts.

## [Unreleased]

## [1.1.2] - 2026-11-19

### Fixed

- Keep widget cards in stable layouts and toggle visibility without removing or reparenting them during settings refreshes.
- Remove child-widget opacity effects that could leave cards visually transparent after launcher repaint or activation.
- Add a delayed Qt regression test proving all four widgets remain visible and the clock continues updating after refreshes.


All notable changes to SeekR are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
semantic versioning.

## [1.1.1] - 2026-11-18

### Fixed

- Keep launcher widget cards permanently parented to their side rails instead of reparenting them during every refresh, preventing Qt from hiding or detaching cards.
- Add launcher-visibility and render-snapshot regression checks for all enabled widget cards.
- Make the `--reset-config` command report persistence failures correctly; a successful reset no longer prints a false error.

## [1.1.0] - 2026-11-18

### Added

- Four launcher widgets around the Alt+Space results: local clock, CPU and memory usage, current weather, and a daily wholesome meme with an image preview.
- A dedicated Settings → Widgets page with individual toggles and a city/town weather location field.
- Daily meme caching and periodic weather refreshes; network work runs outside the UI thread.

### Changed

- Redesigned the launcher with two widget cards on each side of the central results list, a wider default layout, theme-aware cards, hover states and fade transitions.
- Search scheduling runs one search at a time and keeps only the latest pending query; stale results are ignored.
- Existing 1.0.x configurations are migrated to the new widget defaults while custom window dimensions are preserved.

### Notes

- Weather data is provided by Open-Meteo. The daily meme uses the Meme API wholesome-meme feed.
- The clock and system usage widgets work locally; weather and meme widgets require an internet connection.

## [1.0.2] - 2026-11-17

### Changed

- Package the Windows installer as a PyInstaller onedir application instead of a one-file executable. This avoids extracting the entire bundled runtime on every cold start and should substantially reduce first-launch delay.

### Fixed

- Add an installed-application startup smoke test to Windows CI so the installer is checked beyond file installation and uninstallation.

## [Unreleased]

### Added

- Seven additional languages: Spanish, French, German, Italian, Brazilian
  Portuguese, Japanese and Simplified Chinese. Launcher text, common controls,
  shared headings and Tools navigation use the localization catalog.
- Persistent local caching for dictionary definitions, allowing previous
  lookups to work offline.
- Windows GPU Engine performance-counter fallback for non-NVIDIA adapters.
- Multi-monitor full-screen screenshot composition and built-in region capture
  that saves directly to SeekR's configured folder.
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

- Firefox bookmarks now use SQLite's backup API for consistent snapshots that
  include live WAL data; Chromium bookmark reads fall back to Bookmarks.bak.
- Quick Connect finds the standard Windows OpenSSH installation even when the
  executable is not on PATH.
- Locale aliases such as pt_br and zh are normalized safely.
- A second launch on Windows could miss the running instance and start a second
  copy instead. notify_existing() reported failure whenever the show request
  had already been handed to the OS, and the caller then took the single-
  instance socket name for itself. It now only waits for bytes still queued.
- notify_existing() could still report False on Windows even though the request
  was delivered: connectToServer/waitForConnected can fail spuriously under the
  offscreen QPA or during slow startup, and waitForBytesWritten reports False
  for a buffer already flushed to the OS. It now retries within the timeout and
  never treats the flush result as failure.
- Repeated activation of an already-running instance now reliably brings the
  launcher forward. A show request could produce a visible but inactive window
  that the focus-loss timer hid again. Showing the launcher now cancels pending
  hides, retries foreground activation for one second, and passes foreground
  permission from the launching process to the running instance.
- Quitting SeekR now really stops the event loop; the tray Quit action calls
  exit(0) instead of relying on a no-op QCoreApplication.quit() path.
- Launch Windows SSH clients directly in a new console without composing
  commands through cmd.exe.

### Tests

- Added regression coverage for nine-language catalogs, shared widget labels,
  offline dictionary caching, Chromium backup recovery, Firefox live-WAL
  snapshots, Windows SSH path discovery and GPU Engine counter parsing.
- Regression tests for repeated activation cover refused foreground activation,
  the activation grace period, an interrupted hide animation and a forwarded
  socket request revealing a hidden launcher.

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
