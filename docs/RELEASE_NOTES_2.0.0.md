# SeekR 2.0.0

**Published:** 2026-11-20  
**Platform:** Windows 10 and Windows 11  
**License:** MIT

SeekR 2.0.0 is a substantial upgrade to the keyboard-driven Windows launcher. It expands search, widgets, productivity tools, privacy controls, backup/recovery, and diagnostics while keeping user data local.

## Highlights

- Natural-language file metadata filters and opt-in content search restricted to configured roots and file types.
- Incremental indexing, bounded search-history retention, and safer handling of incomplete scans.
- Six configurable launcher widgets, including an optional Windows media-session controller, configurable layout/order/refresh, and cached offline fallbacks.
- A Command Center, local workflows, text snippets, task manager, explicit command chains, and constrained window management.
- Integrity-checked SQLite backup/restore with rollback on failure.
- Opt-in clipboard history with retention, pinning, pause/clear controls, best-effort credential filtering, and separately opt-in bounded PNG capture.
- Local diagnostics export; logs are excluded by default and reports are never uploaded.
- Safer update verification using official release metadata, asset size, and SHA-256 checks.
- Nine launcher-shell locales, reduced-motion support, and a unified Tools experience.

## Automated verification

The release commit passed the complete GitHub Actions pipeline:

- Ubuntu Latest: 328 passed, 2 skipped.
- Windows Latest: 326 passed, 4 skipped.
- Windows Server 2022: 326 passed, 4 skipped.
- Windows portable and onedir builds, packaged UI verification, installer compilation, fresh installation, launch, installed UI verification, uninstallation, SHA-256 staging, and GitHub release publication all succeeded.

The published installer and portable executable are accompanied by `SHA256SUMS.txt`.

## Important validation notes

The release has **not** been manually tested on physical Windows 10/11 desktops. Mixed-DPI and multi-monitor behaviour, sleep/resume, a real upgrade from 1.x with user-data preservation, long-duration stability, and screen-reader/accessibility review remain outstanding. CI proves the automated and fresh-install paths; it does not prove those hardware-dependent scenarios.

The executables are **unsigned** because no code-signing certificate is configured. Do not interpret the absence of a signature as a malware verdict, but Windows may display SmartScreen warnings.

Clipboard text and PNG captures are stored locally and unencrypted when their respective opt-in features are enabled. Clipboard credential filtering is best-effort, not a guarantee.

Third-party plugins, plugin execution, marketplace installation, plugin permissions, and the public plugin SDK are **not included** in 2.0.0; they are deferred to 3.0.0.

## Downloads

- Installer: [SeekR-Setup-2.0.0.exe](https://github.com/okyanus-11/SeekR/releases/download/v2.0.0/SeekR-Setup-2.0.0.exe)
- Portable: [SeekR.exe](https://github.com/okyanus-11/SeekR/releases/download/v2.0.0/SeekR.exe)
- Checksums: [SHA256SUMS.txt](https://github.com/okyanus-11/SeekR/releases/download/v2.0.0/SHA256SUMS.txt)

See [README](../README.md), [Windows manual checklist](WINDOWS_MANUAL_TEST.md), and [Windows performance notes](WINDOWS_PERFORMANCE.md).
