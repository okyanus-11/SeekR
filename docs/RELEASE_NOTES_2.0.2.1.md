# SeekR 2.0.2.1

**Platform:** 64-bit Windows 10 and Windows 11  
**License:** MIT  
**Type:** Maintenance release on top of 2.0.2

SeekR 2.0.2.1 is a focused reliability release. It fixes four defects found while
auditing the 2.0.2 code on Windows — including the launcher freezes that could
appear after rapid dismiss/reopen cycles and after roughly two minutes of use.

## Fixed

### System widget no longer freezes the launcher
The CPU / memory / storage / battery / network card called `psutil` directly
from a 2-second `QTimer` slot on the GUI thread. On Windows those calls
(`disk_usage`, `sensors_battery`, `net_io_counters`) can take hundreds of
milliseconds, which is exactly the reported "freezes after about two minutes"
symptom. Collection now runs on the thread pool, results are applied on the GUI
thread, overlapping refreshes are skipped, and refresh is paused while the
launcher is hidden.

### Single-instance activation no longer blocks the UI
The local-socket server used `waitForReadyRead()` inside GUI-thread slots. A
second launch that connected without an immediate payload stalled the launcher
for up to 700 ms. Reads are now fully non-blocking with a bounded per-socket
buffer, so a split `show` payload still works and a silent client cannot stall
the interface.

### File-query date filters cannot crash
`today` / `yesterday` filters converted local midnights with
`datetime.timestamp()`, which raises `OSError` on Windows for some local days
near the epoch. Conversion now uses `time.mktime` with a UTC fallback, and a
regression test covers the failing case.

### Update checks understand four-part versions
The updater's version pattern rejected any `major.minor.patch.build` tag and
ranked `2.0.2.1` equal to `2.0.2`. A fix release would therefore have been
reported as "invalid release version" or "already up to date". Version parsing
now accepts four-part releases and sorts `2.0.2.1` above `2.0.2` (and above its
own prereleases).

## Unchanged

- Search, widgets, tools, settings, themes, localization, privacy defaults and
  the top-anchored dropdown launcher from 2.0.2.
- User data stays in `%APPDATA%\SeekR`; uninstalling preserves it.
- No new network destinations or data collection.

## Verification

- Full test suite on a physical Windows machine: **334 passed, 4 skipped,
  0 failed** (2.0.2 shipped with one failing test on this path).
- The release workflow runs the suite on Ubuntu, Windows Server 2022 and
  Windows Latest, builds the portable one-file executable and the onedir build,
  verifies executable metadata, compiles the Inno Setup installer, then
  installs, launches, verifies the UI, uninstalls, and publishes SHA-256
  checksums.

## Known limitations

- Executables are unsigned, so SmartScreen may warn.
- The release pipeline does not replace physical testing. Mixed-DPI and
  multi-monitor behaviour, sleep/resume, upgrading from an older 1.x install
  with data preservation, accessibility review and long-duration sessions still
  need hands-on validation.
- The Rust/Slint experiment is not part of this release; 2.0.2.1 is the
  Python/PySide6 application.

## Downloads

- Installer: `SeekR-Setup-2.0.2.1.exe`
- Portable: `SeekR.exe`
- Checksums: `SHA256SUMS.txt`

Both the installer and the portable executable require no Python installation.
