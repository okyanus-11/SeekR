# SeekR Rust migration

## Migration policy

The published 2.0.2 Python/PySide6 application remains the known-good fallback while
the native implementation is built and verified. The Rust project is deliberately
introduced alongside it; the existing application is not removed or replaced until
the Rust implementation has feature parity and passes the release gates.

This avoids turning a language migration into an unreviewable, all-at-once rewrite.
It also means the Rust preview is not yet a replacement for the published product.

## Native stack

- Rust 1.95+
- Slint 1.19 for the desktop UI
- Serde and JSON for validated local configuration
- SQLite will be introduced behind a repository layer before feature ports need it
- Windows-specific integration will be isolated behind platform modules

## Initial migration slice

- Compiled Slint desktop shell.
- Provider-isolated search with deterministic ranking.
- Containment of provider errors and panics.
- Validated widget layout, dimensions, enabled states and refresh intervals.
- Atomic configuration writes and non-destructive handling of malformed config.
- Windows CI for formatting, linting, tests and release builds.

## Release gates

Do not publish a Rust replacement until all of the following are true:

1. Search, widget customization and the existing launcher workflows have verified
   feature parity or an explicitly documented migration decision.
2. The application launches and remains responsive on supported Windows 10/11
   hardware, including repeated open/hide/search cycles and long-duration runs.
3. Windows integration (global hotkey, active-monitor placement, tray, startup,
   single-instance activation and installer/uninstaller) is implemented and tested.
4. Existing user configuration and database data are migrated safely with backup
   and rollback.
5. CI passes formatting, Clippy, unit/integration tests and packaged Windows smoke
   tests; installer metadata and checksums match the release version.
6. README, changelog, release notes and installer describe the actual shipped build.

A successful compile alone is not a release sign-off.
