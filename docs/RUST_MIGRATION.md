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

## Current implementation status

The current native slice includes:

- Windows Start Menu application discovery and bounded indexing of common user
  folders, built on a worker thread so directory traversal does not block the UI.
- Fuzzy title matching with typo tolerance and deterministic result ranking.
- A calculator prefix (calc:) with case-insensitive matching and clipboard copy.
- A live local clock preview updated once per second.
- Persistent widget enabled states, dimensions and left/right ordering.
- Migration of legacy Python widget preferences while preserving unrelated
  settings and unknown keys.
- Atomic settings replacement, malformed-file protection, and regression tests.

Current native slice, updated for the 2.0.3 takeover:

- Results render as a real interactive list (rows, selection, hover, click,
  scroll) rather than one formatted text block.
- Search runs on a worker thread with a 70 ms debounce, generation IDs and
  stale-result rejection, so old queries can never overwrite the current list.
- Explicit `calc:`, `time:`, `app:` and `file:` modes plus automatic arithmetic
  (`6 * 7` returns 42); unknown prefixes stay plain queries instead of
  returning placeholders.
- Deterministic ranking, duplicate removal, provider error/panic containment.
- Single-instance activation via a named mutex; a second launch focuses the
  existing window. Verified on Windows.
- Global `Alt+Space` hotkey via `RegisterHotKey` on a dedicated message-loop
  thread.
- `Cargo.toml` and `PRODUCT_VERSION` now carry the native 2.0.3 identity; see
  [VERSION_POLICY.md](VERSION_POLICY.md).

The native preview is still not feature-complete. Only the clock widget has live
 data; the widget controls edit persisted preferences but no dashboard renders
System/Tasks/Weather/Cat/Media yet. Tray icon, active-monitor placement and
DPI handling, startup integration, the full settings/tools surfaces, the
SQLite layer and its migration, and Windows installer/portable packaging remain
release blockers. See [RUST_PARITY_MATRIX.md](RUST_PARITY_MATRIX.md) for the
row-by-row status and verification gaps.

CI runs Clippy, unit tests and optimized Windows builds on both windows-2022
and windows-latest, and now also checks formatting, Clippy and tests on Ubuntu
so Linux-only compile breaks are caught (the crate previously did not build off
Windows). This validates compilation and core logic, not real desktop
interaction or long-duration stability.

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
