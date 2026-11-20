# SeekR 2.0.2

**Published:** 2026-11-20  
**Platform:** Windows 10 and Windows 11  
**License:** MIT

SeekR 2.0.2 introduces the top-anchored dropdown launcher. Instead of appearing in the middle of the screen, SeekR opens from the top edge of the active display and remains positioned near the top while you work.

## Highlights

- **Top dropdown layout:** the launcher is horizontally centered on the active screen and anchored close to its top edge.
- **Slide-down opening:** the window reveals itself by sliding down from above the screen.
- **Slide-up dismissal:** hiding the launcher retracts it above the top edge while retaining the existing opacity transition.
- **Daily cat widget:** the daily cat photo continues to render directly inside the launcher, with local caching rather than opening an external link.
- **Existing launcher features:** search, widgets, productivity tools, and settings remain part of the application.

## Automated verification

The v2.0.2 release commit passed the complete GitHub Actions pipeline:

- Ubuntu test suite: passed.
- Windows Latest test suite: passed.
- Windows Server 2022 test suite: passed.
- Windows portable executable build and startup verification: passed.
- Packaged launcher UI verification: passed.
- Windows installer build: passed.
- Fresh installation, installed-app startup and UI verification, and uninstallation: passed.
- SHA-256 checksum generation and release asset upload: passed.

## Important validation notes

The release has not been manually tested on physical Windows 10/11 desktops. Mixed-DPI and multi-monitor behaviour, sleep/resume, a real upgrade from 1.x with user-data preservation, long-duration stability, and screen-reader/accessibility review remain outstanding. CI verifies automated tests and the fresh-install path; it does not replace those hardware-dependent checks.

The executables are unsigned because no code-signing certificate is configured. Windows may display SmartScreen warnings.

## Downloads

- Installer: [SeekR-Setup-2.0.2.exe](https://github.com/okyanus-11/SeekR/releases/download/v2.0.2/SeekR-Setup-2.0.2.exe)
- Portable: [SeekR.exe](https://github.com/okyanus-11/SeekR/releases/download/v2.0.2/SeekR.exe)
- Checksums: [SHA256SUMS.txt](https://github.com/okyanus-11/SeekR/releases/download/v2.0.2/SHA256SUMS.txt)

See [README](../README.md) and the [Windows manual checklist](WINDOWS_MANUAL_TEST.md).
