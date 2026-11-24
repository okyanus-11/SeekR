# Changelog

## [Unreleased] — native Rust 2.0.3

### Added

- Interactive native result list (selection, hover, click, scroll, status line) replacing the single text block.
- Background search worker with 70 ms debounce, generation IDs and stale-result rejection.
- `time:`, `app:` and `file:` search modes plus automatic arithmetic in plain queries.
- Single-instance activation and the global `Alt+Space` hotkey.
- Feature parity matrix and version identity policy (`docs/RUST_PARITY_MATRIX.md`, `docs/VERSION_POLICY.md`).

### Fixed

- The Rust crate did not compile outside Windows (type inference in the file index); Ubuntu CI now guards this.
- Registered third-party search providers were excluded from every query.

### Changed

- `Cargo.toml` and `PRODUCT_VERSION` now identify the native build as 2.0.3; the published Python fallback remains v2.0.2.

## [2.0.3] - 2026-11-24

### Fixed

- Keep the Windows launcher surface opaque and use position-only dropdown animation to avoid stale repaints from layered windows.
- Prevent delayed focus-loss events and interrupted hide animations from undoing a fresh show request.
- Initialize result row sizing before the first visible show so a background search result can render during hidden startup.
- Buffer single-instance show requests without blocking the GUI event loop.
- Bound dictionary-service response reads and identify requests with the current application version.

### Changed

- Collect system-widget metrics on a worker thread so slow Windows providers cannot block launcher input or repainting.

### Validation

- Add Windows regression coverage for repeated hide/show/search/render cycles, system-widget worker execution, and pre-show result rendering.
- Add packaged 3-minute stability, reinstall/uninstall, and v2.0.2 upgrade/data-preservation gates to the Windows workflow.
- Keep the Rust/Slint crate separate as an experimental preview; v2.0.3 packages the Python/PySide6 application.

## [2.0.2] - 2026-11-20

### Fixed

- Correct the Inno Setup fallback version and Windows product metadata so the installer registers the current SeekR version, publisher, and support links.
- Preserve the previous installation directory and Start Menu group during upgrades; scope automatic application closing to SeekR.exe.

### Tests

- Extend the Windows installer smoke test to verify the registered product version, install directory, and Start Menu shortcut target, in addition to installation, launch, UI verification, and uninstall.


### Changed

- Repositioned the launcher as a top-anchored dropdown, centered horizontally and kept close to the active screen's top edge.
- Reworked the entrance and dismissal transitions to slide down from and retract above the top edge, while preserving the existing fade and animation settings.

### Tests

- Added a GUI regression test for top-edge anchoring and horizontal centering.


## [2.0.1] - 2026-11-20

### Changed

- Replaced the daily meme card with a daily cat photo displayed directly inside the launcher; no post link or external browser action is involved.
- Fetch cat photos from TheCatAPI on a background worker, validate the image host and content type, enforce a 4 MB download limit, and cache the rendered image locally for the current calendar day.
- Preserve the last successful cat photo for offline display and retry failed refreshes without blocking the launcher.
- Migrate existing daily-widget enabled state and right-rail order from the former widget setting to the cat setting.

### Validation

- Release validation is performed by the v2.0.1 GitHub Actions pipeline; its result is recorded on the release page and in the repository workflow.


## [2.0.0] - 2026-11-19

### Added

- Added an optional Windows media-session widget with current-track metadata and play/pause/previous/next controls, using the Windows Global System Media Transport Controls API when available. The card is opt-in and reports unsupported environments clearly.
- Added a Diagnostics tools page for user-initiated local report export. Logs are excluded by default; optional log inclusion applies best-effort redaction and clearly warns users to review the file. Reports are never uploaded.
- Update checks now show official release notes and include a per-version “Remind me later” action; update notifications stay quiet for a version the user has deferred.
- Configurable launcher widget rail width, card height, and persistent left/right card ordering; settings changes reorder existing cards without recreating or reparenting them.
- Local multi-step workflows with validated steps, preview, cancellation, progress,
  per-step errors, and versioned JSON import/export.
- A reusable snippets manager with categories, aliases, search, explicit copy,
  and validated JSON backup/restore.
- A local task manager with due dates, notes, completion state, launcher search,
  and a compact launcher task-summary widget.
- A unified Command Center, explicit command chains, and safer window-management
  actions for switching, tiling and minimizing.
- A database backup page with consistent SQLite backups, integrity-checked restores,
  and automatic rollback to the live snapshot if restoration fails.
- Natural-language file filters for extension, local calendar date and size,
  plus opt-in local content search for configured roots and text extensions.
- Configurable refresh intervals for launcher widgets and reduced-motion support
  in shared animated controls.
- Clipboard privacy controls for pausing monitoring, clearing all entries (including
  pinned items), and best-effort filtering of common credential-shaped strings.
- Explicit clipboard privacy disclosures and a plain-text-only policy for rich-text
  clipboard content; optional PNG capture remains separate and unencrypted.
- Update checks validate semantic release tags and official asset URLs, expose
  GitHub-published SHA-256 digests, and lets users verify a manually downloaded
  asset by expected size and SHA-256 without silently downloading or installing updates.

### Changed

- Weather is cached per configured location across restarts, and weather and daily meme widgets retain last-good data during network outages and clearly label cached/stale content instead of replacing useful information with an empty error state.
- File-content search now has strict candidate and aggregate read budgets.
- File indexing preserves the last complete snapshot on cancellation, inaccessible
  folders and index-limit exits.
- Hidden launcher widgets stop polling; network-backed widgets fetch outside the
  UI thread and refresh only when active.
- Clipboard history applies age-based retention to unpinned entries while
  preserving pinned entries; separately opt-in PNG image capture is size-bounded,
  stored as unencrypted local files, previewed in the manager and copied back on explicit selection.
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

- Latest full CI run [44706861698](https://github.com/okyanus-11/SeekR/actions/runs/44706861698) passed: Ubuntu 328 passed / 2 skipped; Windows Latest 326 passed / 4 skipped; Windows Server 2022 326 passed / 4 skipped.
- The Windows packaging job passed portable and onedir builds, packaged UI verification, Inno Setup compilation, fresh install, launch, installed UI verification, uninstall, SHA-256 manifest generation and artifact upload.
- Physical Windows 10/11 desktop checks (mixed DPI, multi-monitor, sleep/resume, real 1.x upgrade, long-duration stability and accessibility review) have not been performed. The release is not described as manually Windows-verified. Builds are unsigned.

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
