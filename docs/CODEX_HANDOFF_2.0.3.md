# SeekR — Codex Handoff: v2.0.3

**Date:** 2026-11-23  
**Repository:** `okyanus-11/SeekR`  
**Branch policy:** `main` only; do not create branches unless the user explicitly requests it.  
**Last observed main commit:** `8d315936280a51c5a28fbc9cafc4ed8e16341289` — "Document live clock preview and remaining widget work".

## Mission

Finish **SeekR v2.0.3** as a complete, reliable, installable Windows release. Do not stop at a plan, a partial prototype, or a green compile. Do not publish until the app works as a desktop product and all release gates pass.

The user selected **Rust** as the future development direction. A Rust/Slint implementation now exists in parallel with the published Python/PySide6 v2.0.2 app, but it is still a preview and does not have feature parity. Keep v2.0.2 intact as the known-good fallback until the Rust app is genuinely ready. Do not call the current native preview v2.0.3 or publish it as a finished replacement.

## Product roadmap

### v2.0.2 — Stable baseline
Published Python + PySide6 application. Preserve its launcher workflows, settings, database, and installer.

### v2.0.3 — Current objective
- Search improvements: ranking/relevance, typo tolerance, app/file discovery, selectable results, launch/copy actions, calculator, responsive background indexing.
- Widget customization: enable/disable, dimensions, ordering, persistence, and working live widget behavior.
- Bug fixes and stability; especially rapid reopen and long-session GUI freezes.
- Verify startup, resource use, repeated open/hide/search cycles.
- Windows installer and portable build, smoke-tested.
- Accurate README, changelog, release notes, version metadata, checksums.

### v2.1.0
System Monitor, Clipboard History, Focus Timer.

### v2.2.0
Smart Search and personalization/adaptive ranking.

### v2.3.0
Automation and user-configurable workflows.

### v3.0.0
Plugin ecosystem and extensibility.

Do not pull later-version features into 2.0.3 unless needed for its acceptance criteria. Do not advertise placeholders that have no working action.

## Current repository state

### Stable vs native
- Published stable version: **v2.0.2**, Python + PySide6.
- Parallel native crate: `seekr-native` v0.1.0, Rust 2024 edition, Rust 1.95+, Slint 1.19, Serde, `meval`, `arboard`, `chrono`.
- Migration policy in `docs/RUST_MIGRATION.md`: retain Python v2.0.2 as fallback until parity, Windows integration, migration safety, packaging, and stability gates pass.

### Native features already implemented
- Slint desktop shell and provider-based search with deterministic ranking/typo tolerance.
- Windows Start Menu app discovery and bounded common-folder indexing.
- Indexing moved to a background thread.
- Case-insensitive `calc:` calculator with clipboard copy.
- Previous/Next controls to select and activate search results.
- Persistent widget enabled states, sizes, and left/right ordering.
- Legacy Python widget preference migration; preserve unknown config keys.
- Atomic config writes and round-trip/replacement tests.
- Live local clock preview updated every second.
- Rust CI uploads native preview artifacts after optimized build.

### Known native gaps / release blockers
- Search results are still text-rendered, not a polished interactive result list.
- Only the clock has a live widget data preview; full widget dashboard/providers are not ported.
- Widget controls persist preferences but do not yet provide full v2.0.2 widget behavior.
- Global hotkey, tray, single-instance lifecycle, active-monitor placement/dropdown behavior, full settings/tools surfaces, database integration, installer and end-user packaging remain unimplemented or unverified.
- No verified feature parity or real desktop/long-duration stability sign-off.

### Historical critical bug
The existing app has been reported to freeze/lose GUI responsiveness:
- Rapidly dismissing and reopening it can freeze the GUI.
- It has also frozen after roughly two minutes.
- Rebuilding did not reliably resolve the reopen issue.

Reproduce this, isolate the lifecycle/thread/timer/event-loop cause, fix the root cause, and add regression coverage. Do not accept "seems fixed" without repeated validation.

## CI state at handoff — poll before relying on it

### Rust native workflow
- Run **45232428878**, commit `9a48af95ffb01f5a145ff193ab2bc7af69fa1dc4`.
- Both Windows jobs had passed formatting, Clippy, and Rust tests.
- Optimized release builds were still running; artifact upload was pending.
- Jobs: `137898304774` (windows-latest), `137898305273` (windows-2022).

### Python tests + Windows installer workflow
- Run **45232454450**, commit `8d315936280a51c5a28fbc9cafc4ed8e16341289`.
- Python tests passed on windows-2022, windows-latest, and ubuntu-latest.
- Windows packaging job `137896830955` was still running the executable build/test step. Widget verification, installer build, install/uninstall checks, checksum staging and artifact upload were pending.

**First task:** re-check these runs and inspect logs/artifacts. Their status may have changed after this handoff was written.

## Immediate execution order for Codex

1. Fetch latest `main`, inspect recent commits and current workflow status. Establish which implementation is being packaged.
2. Audit `Cargo.toml`, `src/main.rs`, `src/search.rs`, `src/config.rs`, `ui/launcher.slint`, `build.rs`, and Rust CI. Check runtime/lifecycle issues, not just compilation.
3. Reproduce the rapid-reopen and long-session freezes. Test launch → dismiss → reopen repeatedly, search while indexing, and sessions well beyond two minutes. Inspect timers, event-loop exit/re-entry, worker lifetime, callbacks, shared state, and single-instance behavior.
4. Finish the search experience: navigate/select/open/copy any result reliably; handle indexing state; keep expensive indexing off the UI thread; remove fake results.
5. Finish widget customization and real widget behavior, not just persisted settings.
6. Implement or prove parity for global hotkey, active-monitor placement, tray, single-instance activation, clean shutdown/reopen, and startup behavior on supported Windows 10/11.
7. Preserve existing settings and database data. Migrate safely with backup/rollback; never discard unknown config keys.
8. Build optimized binaries, installer and portable package. Test fresh install, upgrade over v2.0.2, launch/use, uninstall and reinstall.
9. Update README, changelog, release notes, version constants, installer metadata and checksums. Document only shipped behavior.
10. Publish only after every acceptance gate passes; verify release assets, tag/version and checksums after publishing.

## Engineering rules

- Work on `main` only.
- Make actual code changes; do not substitute status reports or TODO lists for implementation.
- Keep commits focused and descriptive.
- Do not delete/overwrite the known-good v2.0.2 implementation during migration.
- Preserve configuration/data compatibility.
- Never advertise a placeholder action.
- Avoid expensive work on the UI thread.
- Surface actionable errors; add regression tests for fixes.
- Never claim Windows runtime validation from CI compilation alone.
- Never call the release finished if any acceptance criterion remains incomplete.

## Definition of done — v2.0.3

- [ ] Search improvements work in the actual Windows app.
- [ ] Widget customization and promised widget behavior work and persist after restart.
- [ ] Rapid-reopen and long-session freezes are root-caused, fixed, and regression-tested.
- [ ] Repeated open/hide/reopen cycles and long-duration use remain responsive.
- [ ] Existing settings/data are preserved or safely migrated.
- [ ] Hotkey, tray, active-monitor placement, single-instance activation, shutdown/reopen work.
- [ ] Formatting, lint, tests, optimized builds, and packaging checks pass.
- [ ] Installer and portable build are produced and smoke-tested.
- [ ] Fresh install, upgrade, uninstall, reinstall are verified.
- [ ] README/changelog/release notes/version/checksums match the shipped build.
- [ ] Only then publish v2.0.3 with verified assets.

**Final direction:** continue until the release is genuinely ready. A green CI run is necessary, not sufficient. Do not ship the incomplete native preview as v2.0.3.
