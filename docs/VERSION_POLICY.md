# Version identity policy

## The ambiguity this resolves

`main` currently contains two different things that both claimed 2.0.3:

1. **Python/PySide6 2.0.3 candidate** — `core/version.py`, `installer/seekr.iss`,
   `CHANGELOG.md` and `docs/RELEASE_NOTES_2.0.3.md` were bumped by a previous
   assistant. It is **not published**.
2. **Native Rust 2.0.3** — the takeover target, which was still `0.1.0` in
   `Cargo.toml`.

Shipping both under one tag would make "SeekR 2.0.3" ambiguous.

## Decision

- **Rust `2.0.3` is the release identity for v2.0.3.** `Cargo.toml` and
  `src/lib.rs` (`PRODUCT_VERSION`) now carry `2.0.3`.
- **The published, supported download stays Python v2.0.2**
  (`LEGACY_RELEASE_VERSION` in `src/lib.rs`).
- **The Python 2.0.3 candidate is fallback maintenance, not the v2.0.3 release.**
  It may ship later as its own patch release, but it must never be tagged
  `v2.0.3` and must never be described as the native release.
- The existing protection in the release workflow (a tag must match the
  version being packaged) stays in force. Do not bypass it.

## What must match before the Rust v2.0.3 tag exists

All of the following must describe the *same* native build:

- `Cargo.toml` / `Cargo.lock` package version
- Windows executable metadata (`.rc` / version resource)
- installer `AppVersion` and output filename
- README "latest release" text and release notes
- tag name, asset names and `SHA256SUMS.txt`

The parity matrix in [`RUST_PARITY_MATRIX.md`](RUST_PARITY_MATRIX.md) is the
source of truth for whether the native app is ready for that tag.
