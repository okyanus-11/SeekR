# SeekR 2.0.2

**Published:** 2026-11-20  
**Platform:** 64-bit Windows 10 and Windows 11  
**License:** MIT

SeekR 2.0.2 introduces the top-anchored dropdown launcher. Instead of appearing in the middle of the screen, SeekR opens from the top edge of the active display and remains positioned near the top while you work.

## Highlights

- **Top dropdown layout:** the launcher is horizontally centered on the active screen and anchored close to its top edge.
- **Slide-down opening:** the window reveals itself by sliding down from above the screen.
- **Slide-up dismissal:** hiding the launcher retracts it above the top edge while retaining the existing opacity transition.
- **Daily cat widget:** the daily cat photo continues to render directly inside the launcher, with local caching rather than opening an external link.
- **Existing launcher features:** search, widgets, productivity tools, and settings remain part of the application.

## Installer fixes and verification

The 2.0.2 installer metadata and upgrade configuration were corrected and the installer was rebuilt:

- Inno Setup's fallback version now matches the application version (2.0.2).
- Windows Installed apps displays the correct product name and version, publisher, and application support/update links.
- The installer explicitly reuses the previous installation directory and Start Menu group during an upgrade.
- Automatic application closing is scoped to SeekR.exe.
- The Windows installer smoke test now checks the registered product version, registered install directory, and Start Menu shortcut target, in addition to installing, launching, verifying the UI, and uninstalling.

The fresh-install path and the expanded installer checks passed in GitHub Actions. A real upgrade from an older release with preservation of existing user data still needs manual validation on a physical Windows machine.

## Automated verification

The release pipeline checks the following:

- Ubuntu, Windows Latest, and Windows Server 2022 test suites.
- Portable and onedir Windows executable builds and executable version metadata.
- Packaged launcher UI verification.
- Inno Setup compilation.
- Fresh installation, Windows Installed apps registration, Start Menu shortcut target, installed-app startup and UI verification, and uninstallation.
- SHA-256 checksum generation and release asset publication.

## Important validation notes

This release has not been fully manually validated on physical Windows 10/11 desktops. Mixed-DPI and multi-monitor behaviour, sleep/resume, a real upgrade from an earlier release with user-data preservation, long-duration stability, and screen-reader/accessibility review remain outstanding. CI verifies automated tests and the fresh-install path; it does not replace those hardware-dependent checks.

The executables are unsigned because no code-signing certificate is configured. Windows may display SmartScreen warnings.

## Downloads

- Installer: [SeekR-Setup-2.0.2.exe](https://github.com/okyanus-11/SeekR/releases/download/v2.0.2/SeekR-Setup-2.0.2.exe)
- Portable: [SeekR.exe](https://github.com/okyanus-11/SeekR/releases/download/v2.0.2/SeekR.exe)
- Checksums: [SHA256SUMS.txt](https://github.com/okyanus-11/SeekR/releases/download/v2.0.2/SHA256SUMS.txt)

See the [README](../README.md), [installation guide](INSTALLATION.md), and [Windows manual checklist](WINDOWS_MANUAL_TEST.md).
