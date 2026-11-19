# SeekR 2.0.0 — release implementation plan

**Status:** planning and implementation checklist  
**Target:** Windows 10/11, Python + PySide6 retained  
**Release policy:** 2.0.0 is not releasable until every required item below is implemented, tested, documented, and verified on a real Windows desktop.  
**Plugin system:** explicitly deferred to 3.0.0. Do not add plugin loading, third-party code execution, marketplace installation, or plugin permissions in 2.0.0.

This plan is intentionally exhaustive. A checked box means the work is implemented and supported by test evidence; it must never mean merely planned or partially implemented.

## 1. Performance and responsiveness

- [ ] Measure packaged cold start and warm start separately (installer and portable builds). A repeatable Windows runner now records sequential process-to-visible startup, Alt+Space-to-visible latency, idle CPU, memory and thread counts; its results still need to be collected on supported Windows hardware.
- [ ] Measure hotkey-to-visible latency, first paint, and time-to-interactive on real Windows hardware.
- [ ] Record idle CPU, working set/private bytes, thread count, and memory growth over short and long runs.
- [ ] Profile startup imports and defer nonessential modules without delaying first-use interactions.
- [ ] Keep expensive initialization and I/O off the GUI thread.
- [ ] Review Qt startup, first paint, animation, and repaint costs with profiling evidence.
- [ ] Make application indexing incremental and avoid unnecessary full rescans.
- [x] Preserve the existing file index during a scan, prune stale records only after a complete scan, and retain cached records when configured folders are unavailable or indexing is cancelled. (Incremental change detection and scan-cost optimization remain open.)
- [ ] Review icon extraction/cache bounds and ensure cache eviction is deterministic.
- [x] Pause widget polling while the launcher is hidden and defer weather/meme requests until activation. (Configurable refresh intervals and per-widget stale/offline states remain open.)
- [ ] Reduce unnecessary widget updates and Qt repaints.
- [ ] Benchmark large file indexes, including substring search and typo-tolerant ranking, before changing search semantics.
- [ ] Keep repeatable benchmark scripts and publish methodology, hardware, and before/after results.
- [ ] Set measurable performance budgets only after representative packaged measurements exist.

## 2. Interface and design system

- [ ] Audit every launcher, widget, settings, tools, dialog, context-menu, and empty/loading/error state.
- [ ] Define shared design tokens for spacing, typography, radii, borders, surfaces, colors, focus, hover, disabled, and error states.
- [ ] Ensure all themes use the same semantic palette roles and avoid hard-coded component colors.
- [ ] Standardize component sizing, alignment, icon treatment, and keyboard focus indicators.
- [ ] Improve search-result hierarchy, icon quality/fallbacks, metadata layout, and selection visibility.
- [ ] Improve empty, loading, no-match, offline, and provider-error states.
- [ ] Add restrained, consistent transitions for opening/closing, result changes, selection, and hover.
- [ ] Respect reduced-motion/animation settings everywhere, including child widgets.
- [ ] Keep animation work lightweight and avoid opacity/parenting patterns that can make Qt widgets disappear.
- [ ] Verify all themes and all nine existing locales for clipping, overflow, and layout regressions.
- [ ] Capture genuine screenshots from a real Windows desktop for the README.

## 3. Search and discovery

- [ ] Audit ranking across exact, prefix, substring, token, fuzzy, alias, recent, and frequent matches.
- [ ] Prefer exact and high-confidence matches without making typo tolerance worse.
- [ ] Improve abbreviation and common-alias handling without keyword collisions.
- [x] Add bounded recent/frequent application ranking behind the existing privacy usage-tracking setting; existing settings allow disabling and clearing usage data.
- [ ] Ensure recent activity has bounded retention and never leaks private query content.
- [x] Add natural-language file filters for supported metadata (type, modified date, and size).
- [ ] Add indexed document-content search only for explicitly configured file types and folders.
- [ ] Make indexing status, supported formats, exclusions, and privacy implications clear.
- [ ] Add tests for ambiguous natural-language filters, time zones, locale parsing, and large indexes.
- [ ] Preserve explicit keyword routing and existing aliases as backwards-compatible behavior.

## 4. Widgets and their lifecycle

- [ ] Keep widget ownership/lifecycle independent from search-result refreshes.
- [ ] Verify widgets remain visible after repeated show/hide, activation, resize, theme change, settings refresh, and result updates.
- [ ] Give every widget isolated error handling, loading, stale-data, offline, and disabled states.
- [ ] Make refresh intervals configurable within safe minimum/maximum bounds.
- [ ] Pause or slow polling when hidden or when the relevant widget is disabled.
- [ ] Add configurable widget sizes/layouts without reparenting fragile live widgets.
- [ ] Persist widget configuration and restore it safely after upgrades.
- [ ] Add battery, network throughput, storage, media playback, focus timer, tasks, and expanded performance-monitor widgets where reliable data sources are available.
- [ ] Keep all optional network widgets non-blocking and cache last-good data.
- [ ] Document data sources, refresh behavior, and permissions for each widget.

## 5. Productivity features

### Quick Actions 2.0 and workflows
- [ ] Support user-defined multi-step workflows with a clear editor and preview.
- [ ] Support opening apps, folders, websites, and explicitly configured commands.
- [ ] Validate workflow steps and arguments; never compose shell command strings.
- [ ] Require confirmation for destructive, elevated, or externally impactful actions.
- [ ] Add cancellation, progress, per-step error reporting, and safe failure behavior.
- [ ] Add workflow import/export with schema validation and versioning.
- [ ] Keep workflows local; do not introduce remote execution or third-party code loading.

### Text snippets
- [ ] Add an opt-in local snippets manager with shortcuts, categories, search, and preview.
- [ ] Expand snippets only through an explicit user action/hotkey; never unexpectedly replace text.
- [ ] Support plain text first; define safe behavior for multiline and rich text.
- [ ] Add privacy controls, backup/export, and tests for focus changes and target-app failures.

### Window management
- [ ] Add discoverable commands for tiling left/right, minimizing all, switching, and closing windows.
- [ ] Protect critical/system windows and require confirmation for bulk or destructive actions.
- [ ] Test multiple monitors, mixed DPI, virtual desktops where supported, and elevated-window limitations.
- [ ] Clearly report unavailable Windows APIs or permission boundaries.

### Clipboard manager
- [ ] Preserve clipboard history as opt-in.
- [ ] Add safe text, rich-text, and image previews with size limits.
- [x] Add age-based retention for unpinned clipboard text; pinned entries remain. (Rich text/image previews, categories and favorites remain open.)
- [ ] Explain local storage and encryption status honestly; never silently collect clipboard content.
- [ ] Exclude sensitive formats where feasible and provide a pause/clear control.
- [ ] Test large payloads, corrupt entries, pruning, and database migration.

### Command chains
- [ ] Add a constrained, explicit command-chain syntax for supported built-in actions.
- [ ] Parse into structured actions; never use eval or shell=True.
- [ ] Show the complete action plan before execution when any step is destructive or ambiguous.
- [ ] Add per-step confirmation, cancellation, timeout, and partial-failure reporting.
- [ ] Ensure command chains cannot bypass existing command safety checks.

## 6. Reliability, accessibility, and compatibility

- [ ] Add automated UI interaction coverage for core launcher flows and settings.
- [ ] Add widget lifecycle regression tests for every refresh/visibility/theme transition.
- [ ] Add long-duration stability and memory-growth tests.
- [ ] Add repeated open/close, repeated activation, and single-instance stress tests.
- [ ] Test database migration, interrupted writes, backup recovery, and corrupted configuration.
- [ ] Test offline mode, DNS/network failures, slow endpoints, and malformed provider responses.
- [ ] Test Windows 10 and Windows 11 on real desktops.
- [ ] Test mixed-DPI and multi-monitor layouts, scaling changes, sleep/resume, and display hot-plug.
- [ ] Test global hotkey conflicts, tray lifetime, startup registration, focus behavior, and window activation.
- [ ] Review keyboard-only navigation, visible focus, screen-reader labels where supported, and contrast.
- [ ] Verify reduced-motion behavior and scalable UI text.
- [ ] Keep all existing regression tests passing; add tests before fixing discovered regressions.

## 7. Packaging, updates, and distribution

- [ ] Audit installer, portable build, and onedir packaging from clean Windows environments.
- [ ] Verify cold launch, warm launch, upgrade from the previous public version, reinstall, rollback, and uninstall.
- [ ] Preserve user settings/database on normal upgrades and document data removal on uninstall.
- [ ] Add a secure update-checking flow that verifies release metadata and downloaded artifact hashes.
- [ ] Provide clear in-app update availability, release notes, defer, and restart behavior.
- [ ] Never silently replace a running executable or install an unverified artifact.
- [ ] Add code-signing support when a valid signing certificate is available; do not claim signed builds otherwise.
- [ ] Publish SHA256 checksums for every release artifact.
- [ ] Improve crash diagnostics with explicit user consent and redaction; never upload clipboard, notes, paths, or query history by default.
- [ ] Make installer failure recovery and rollback behavior testable.
- [ ] Ensure the installer is prominently linked from the README and every release page.

## 8. Documentation and release hygiene

- [ ] Synchronize README, application version, changelog, installer metadata, and release workflow versioning.
- [ ] Replace stale or contradictory validation claims with current evidence.
- [ ] Document each new feature, keyboard shortcut, setting, data source, privacy behavior, and known limitation.
- [ ] Keep a complete Windows manual test record for each release candidate.
- [ ] Publish screenshots captured from the actual release candidate.
- [ ] Provide upgrade notes and migration behavior for existing 1.x user data.
- [ ] Update troubleshooting and security/privacy documentation.
- [ ] Ensure all repository workflows are green for the release commit and tag.
- [ ] Verify generated installer and portable artifacts are downloadable and match published checksums.

## 9. Release gates

A 2.0.0 release candidate must not be tagged until all of the following are true:

1. Every required checklist item is complete or explicitly removed from scope with an explanation and owner approval.
2. Full test suite passes on supported Python versions and Windows CI.
3. Windows packaging, installation, upgrade, launch, and uninstall checks pass.
4. Manual Windows checklist passes on real hardware, including widgets, hotkeys, tray, DPI, and multi-monitor behavior.
5. Long-duration stability test completes without unexplained crashes, widget loss, or unbounded memory growth.
6. Packaged performance results are recorded and reviewed against the 1.x baseline.
7. README, changelog, version metadata, installer, release workflow, and checksums agree on 2.0.0.
8. All release workflows are green; no failed, cancelled, skipped-required, or stale run is treated as a pass.
9. No plugin loading or marketplace execution code is included; plugins remain a 3.0.0 project.


## Verified implementation log (not a release checklist)

The following 2.0.0 work has been added on the development branch. CI and platform validation remain release gates:

- Natural-language file metadata filters and plural-aware matching.
- Safe file-index snapshot behavior during cancellation, inaccessible roots and complete scans.
- Persistent widget lifecycle, visibility-aware polling, theme refresh and regression coverage.
- Bounded app usage ranking and recent/frequent suggestions; tracking is off by default and disabling it suppresses personalization.
- Clipboard age retention that never expires pinned entries.
- Structured local workflows with validation, import/export, atomic import storage, bounded steps and no shell/script execution.
- Explicitly selected local text snippets, categories and aliases; no automatic text injection.
- Explicit command chains over existing command entries, with per-step confirmation for destructive/custom-confirmed actions and stop-on-failure behavior.
- Per-window left/right tiling using the selected window's nearest monitor work area, confirmed normal-close requests, and minimize-all with SeekR/shell-process exclusions.
- Shared semantic theme roles, spacing/radius/animation tokens, and visible keyboard-focus styling.

These entries are not a substitute for the release gates below. The remaining checklist items still apply.

## Explicitly deferred to 3.0.0

- Third-party plugin loading and execution.
- Plugin marketplace, discovery, installation, update, and removal.
- Plugin permissions, sandboxing, signing, and trust model.
- Public plugin SDK and developer documentation.

The 2.0.0 work should preserve clean internal provider boundaries, but must not ship a plugin runtime or imply that plugins are supported.
