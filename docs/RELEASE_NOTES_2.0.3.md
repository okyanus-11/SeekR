# SeekR 2.0.3

**Status:** Candidate; not published  
**Platform:** 64-bit Windows 10 and Windows 11  
**Application:** Python + PySide6

SeekR 2.0.3 continues the stable Python launcher and installer from v2.0.2 with Windows responsiveness and release-validation improvements. The parallel Rust/Slint implementation remains an experimental preview and is not included in these packages.

## What changed

- Keep the launcher surface opaque and animate its dropdown by position, avoiding stale Windows repaints associated with layered windows.
- Protect rapid hide/show cycles from stale animation completions and delayed focus-loss events.
- Handle single-instance activation without waiting on socket data on the GUI thread.
- Move system-widget metric collection off the GUI thread.
- Render results safely if a background search finishes before the first show.
- Bound dictionary-service response reads and send the current application version in its user agent.

The existing app/file search, selectable result list, calculator/copy actions, widget controls, and saved preferences remain available. No placeholder actions are added.

## Data and installation

User configuration and the SQLite database remain in the per-user SeekR data directory, outside the install folder. The candidate Windows workflow verifies the portable and installer builds, packaged UI rendering, reinstall/uninstall, a 3-minute packaged-process soak, and an upgrade from v2.0.2 that checks saved settings and a database note.

## Release status

This is a release candidate. The v2.0.3 tag and public assets remain gated on the Windows 10/11 interactive checklist, including repeated hotkey reopen/search, widget persistence, and visible long-session responsiveness. CI results do not substitute for that desktop sign-off.

When published, the release page will include the installer, portable executable, and SHA-256 checksums.
