# SeekR 2.0.0 — release implementation plan

**Status:** implementation and automated validation; real-desktop release gates remain  
**Target:** Windows 10/11, Python + PySide6 retained  
**Release policy:** 2.0.0 is not releasable until every required item below is implemented, tested, documented, and verified on a real Windows desktop. Automated CI success does not replace manual Windows 10/11, DPI, multi-monitor, and long-duration validation.  
**Plugin system:** explicitly deferred to 3.0.0. Do not add plugin loading, third-party code execution, marketplace installation, or plugin permissions in 2.0.0.

This plan is intentionally exhaustive. A checked box means the work is implemented and supported by test evidence; it must never mean merely planned or partially implemented.

## 1. Performance and responsiveness

- [ ] Measure packaged cold start and warm start separately (installer and portable builds). A repeatable Windows runner now records sequential process-to-visible startup, Alt+Space-to-visible latency, idle CPU, memory and thread counts; its results still need to be collected on supported Windows hardware.
- [ ] Measure hotkey-to-visible latency, first paint, and time-to-interactive on real Windows hardware.
- [ ] Record idle CPU, working set/private bytes, thread count, and memory growth over short and long runs.
- [ ] Profile startup imports and defer nonessential modules without delaying first-use interactions.
- [x] Keep expensive initialization and I/O off the GUI thread.
- [ ] Review Qt startup, first paint, animation, and repaint costs with profiling evidence.
- [x] Make application indexing incremental and avoid unnecessary full rescans.
- [x] Incremental file-index change detection: unchanged metadata rows are skipped, forced reindex is supported, and stale paths are pruned only after a complete scan; cancellation and inaccessible roots preserve the last complete snapshot.
- [x] Review icon extraction/cache bounds and ensure cache eviction is deterministic; LRU eviction is bounded and covered by tests.
- [x] Pause widget polling while the launcher is hidden and defer weather/meme requests until activation. (Configurable refresh intervals and per-widget stale/offline states remain open.)
- [ ] Reduce unnecessary widget updates and Qt repaints.
- [ ] Benchmark large file indexes, including substring search and typo-tolerant ranking, before changing search semantics.
- [ ] Keep repeatable benchmark scripts and publish methodology, hardware, and before/after results.
- [ ] Set measurable performance budgets only after representative packaged measurements exist.

## 2. Interface and design system

- [ ] Audit every launcher, widget, settings, tools, dialog, context-menu, and empty/loading/error state.
- [x] Define shared design tokens for spacing, typography, radii, borders, surfaces, colors, focus, hover, disabled, and error states.
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
- [x] Add indexed document-content search only for explicitly configured file types and folders.
- [ ] Make indexing status, supported formats, exclusions, and privacy implications clear.
- [ ] Add tests for ambiguous natural-language filters, time zones, locale parsing, and large indexes.
- [ ] Preserve explicit keyword routing and existing aliases as backwards-compatible behavior.

## 4. Widgets and their lifecycle

- [x] Keep widget ownership/lifecycle independent from search-result refreshes.
- [x] Verify widgets remain visible after repeated show/hide, activation, resize, theme change, settings refresh, and result updates with Qt regression tests.
- [x] Give weather and daily meme widgets explicit loading, stale-data, offline, and disabled states; preserve last-good content on network failure. Local clock/system/task widgets report unavailable data independently.
- [x] Make refresh intervals configurable within safe minimum/maximum bounds.
- [x] Pause or slow polling when hidden or when the relevant widget is disabled.
- [x] Add configurable widget sizes/layouts without reparenting fragile live widgets; rail width and card height are persisted in validated settings.
- [x] Persist widget configuration and restore it safely after upgrades; enabled states, refresh intervals, rail dimensions, and card order are migrated through config defaults.
- [x] Persist widget configuration and restore it safely after upgrades; settings are validated and older configs receive safe defaults.
- [ ] Add battery, network throughput, storage, media playback, focus timer, tasks, and expanded performance-monitor widgets where reliable data sources are available.
- [x] Keep weather and daily meme network requests off the GUI thread and cache last-good data locally; weather cache is location-scoped and restored on startup.
- [x] Document widget data sources, refresh behavior, and location/permission behavior in the README and settings descriptions.

## 5. Productivity features

### Quick Actions 2.0 and workflows
- [x] Support user-defined multi-step workflows with a clear editor and preview.
- [x] Support opening apps, folders, websites, and explicitly configured commands.
- [x] Validate workflow steps and arguments; never compose shell command strings.
- [x] Require confirmation for destructive, elevated, or externally impactful actions.
- [x] Add cancellation, progress, per-step error reporting, and safe failure behavior.
- [x] Add workflow import/export with schema validation and versioning.
- [x] Keep workflows local; do not introduce remote execution or third-party code loading.

### Text snippets
- [x] Add an opt-in local snippets manager with shortcuts, categories, search, and preview.
- [x] Expand snippets only through an explicit user action/hotkey; never unexpectedly replace text.
- [x] Support plain text first; preserve multiline text and reduce rich-text clipboard content to plain text rather than rendering untrusted HTML.
- [x] Add local privacy controls, validated backup/export, explicit copy-only behavior, and tests for clipboard-copy failure; automatic text injection is intentionally not supported.

### Window management
- [x] Add discoverable commands for tiling left/right, minimizing all, switching, and closing windows.
- [x] Protect critical/system windows and require confirmation for bulk or destructive actions.
- [ ] Test multiple monitors, mixed DPI, virtual desktops where supported, and elevated-window limitations.
- [ ] Clearly report unavailable Windows APIs or permission boundaries.

### Clipboard manager
- [x] Preserve clipboard history as opt-in.
- [ ] Add rich-text previews with safe formatting limits. (2.0.0 deliberately retains clipboard content as plain text, avoiding untrusted HTML rendering; safe rich-text preservation remains a possible later enhancement.)
- [x] Add age-based retention for unpinned clipboard entries; pinned entries remain. (Rich-text preservation remains open; categories and pinning are supported.)
- [x] Explain local storage and encryption status honestly; never silently collect clipboard content.
- [x] Exclude common credential-shaped formats with a best-effort filter; provide pause, per-entry deletion, clear-unpinned, and confirmed clear-all controls. The filter is explicitly not a guarantee.
- [x] Test bounded large-payload rejection, corrupt/unrelated backup rejection, retention pruning, database migrations, interrupted writes, and restore rollback.

### Command chains
- [x] Add a constrained, explicit command-chain syntax for supported built-in actions.
- [x] Parse into structured actions; never use eval or shell=True.
- [x] Show the complete action plan before execution for saved workflows; destructive/custom commands retain their own confirmation checks.
- [ ] Add per-step confirmation, cancellation, timeout, and partial-failure reporting.
- [x] Ensure command chains cannot bypass existing command safety checks.

## 6. Reliability, accessibility, and compatibility

- [x] Add automated UI interaction coverage for core launcher flows and settings.
- [x] Add widget lifecycle regression tests for every refresh/visibility/theme transition.
- [ ] Add long-duration stability and memory-growth tests.
- [x] Add repeated open/close, repeated activation, and single-instance stress tests.
- [x] Test database migration, SQLite recovery after an interrupted uncommitted write, verified backup/restore, restore rollback on failure, and corrupted configuration.
- [ ] Test offline mode, DNS/network failures, slow endpoints, and malformed provider responses.
- [ ] Test Windows 10 and Windows 11 on real desktops.
- [ ] Test mixed-DPI and multi-monitor layouts, scaling changes, sleep/resume, and display hot-plug.
- [ ] Test global hotkey conflicts, tray lifetime, startup registration, focus behavior, and window activation.
- [ ] Review keyboard-only navigation, visible focus, screen-reader labels where supported, and contrast.
- [x] Verify reduced-motion behavior and scalable UI text.
- [ ] Keep all existing regression tests passing; add tests before fixing discovered regressions.

## 7. Packaging, updates, and distribution

- [x] Audit installer, portable build, and onedir packaging from clean Windows environments.
- [ ] Verify cold launch, warm launch, upgrade from the previous public version, reinstall, rollback, and uninstall.
- [ ] Preserve user settings/database on normal upgrades and document data removal on uninstall.
- [x] Add a secure update-checking flow that validates official release metadata and asset URLs, exposes GitHub-published SHA-256 values, and verifies a user-selected downloaded file against both its expected size and SHA-256 before reporting success. SeekR does not silently download or execute installers.
- [x] Provide in-app update availability, official release notes, and per-version defer controls. Installation stays manual and verified; the app is closed before installer execution and relaunched by the user afterwards (no silent replacement or forced restart).
- [x] Never silently replace a running executable or install an unverified artifact; updates are manual, hashes are verified before reporting success, and installer execution is never automatic.
- [ ] Add code-signing support when a valid signing certificate is available; do not claim signed builds otherwise.
- [x] Publish SHA256 checksums for every release artifact.
- [x] Add user-initiated local diagnostic export. Logs are excluded by default; optional log inclusion applies best-effort redaction, warns users to review the report, and never uploads clipboard, notes, indexed file lists, or search history.
- [ ] Make installer failure recovery and rollback behavior testable.
- [x] Ensure the installer is prominently linked from the README and every release page.

## 8. Documentation and release hygiene

- [x] Synchronize README, application version, changelog, installer metadata, and release workflow versioning.
- [x] Replace stale or contradictory validation claims with current evidence.
- [x] Document each new feature, keyboard shortcut, setting, data source, privacy behavior, and known limitation.
- [ ] Keep a complete Windows manual test record for each release candidate.
- [ ] Publish screenshots captured from the actual release candidate.
- [ ] Provide upgrade notes and migration behavior for existing 1.x user data.
- [x] Update troubleshooting and security/privacy documentation, including local storage, clipboard, backups, and update verification.
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

- Natural-language file metadata filters and plural-aware matching, including local-calendar boundaries for today/yesterday and tests proving today is excluded from yesterday results.
- Clipboard privacy controls now include common credential-pattern filtering, a visible pause switch, per-entry deletion, and a confirmed clear-all action. Plain text and multiline content are retained; rich-text formatting is intentionally reduced to plain text. The sensitive-pattern filter is best-effort, not a guarantee.
- Update metadata handling now accepts only official SeekR release-download URLs with GitHub-provided SHA-256 digests; users can open an asset download or copy its digest explicitly, with no silent download or installation.
- Added a Tools → Database & backups page with consistent SQLite backup creation, integrity verification, backup restore validation, and rollback to the pre-restore snapshot if restoration fails.
- Safe file-index snapshot behavior during cancellation, inaccessible roots and complete scans.
- Persistent widget lifecycle, visibility-aware polling, configurable refresh intervals, reduced-motion behavior for shared controls, theme refresh and regression coverage; the launcher now includes a local task-summary widget. The system card reports CPU, memory, storage, battery and network throughput, and the clock card includes a configurable focus timer.
- Bounded app usage ranking and recent/frequent suggestions; tracking is off by default and disabling it suppresses personalization.
- Clipboard age retention that never expires pinned entries; rich-text and image capture/previews remain open.
- Structured local workflows with validation, import/export, atomic import storage, bounded steps and no shell/script execution; workflows can invoke existing configured commands with tokenized arguments and per-step confirmation.
- Explicitly selected local text snippets, categories and aliases, plus versioned JSON backup/restore; no automatic text injection.
- Local task manager with due dates, notes, completion state, task search and Command Center integration.
- Opt-in on-demand text-content search over indexed files, restricted to configured roots and allowlisted extensions, capped at 500 candidates and 8 MB total reads (with a per-file limit). Persistent content indexing remains out of scope.
- Explicit command chains over existing command entries, with per-step confirmation for destructive/custom-confirmed actions and stop-on-failure behavior.
- Per-window left/right tiling using the selected window's nearest monitor work area, confirmed normal-close requests, and minimize-all with SeekR/shell-process exclusions.
- Shared semantic theme roles, spacing/radius/animation tokens, and visible keyboard-focus styling.
- Leading-> Command Center routing with searchable settings, system/process/network tools, workflows, snippets, clipboard, search shortcuts and widget toggles.
- Manual and opt-in daily GitHub release checks with in-app notifications and official release-page navigation; installer download and execution remain explicit user actions.
- Application index writes now skip unchanged rows; automatic refresh remains first-run/staleness driven and manual refresh remains available.
- CI run `44608000793` passed 281 tests on Windows and Linux runners and completed portable/onedir builds, packaged UI verification, installer compilation, install/launch/UI verification, uninstall, and SHA-256 artifact staging. This run predates the final 2.0.0 version-metadata edits; the current head must pass the same gates before release.

These entries are not a substitute for the release gates below. The remaining checklist items still apply.

## Explicitly deferred to 3.0.0

- Third-party plugin loading and execution.
- Plugin marketplace, discovery, installation, update, and removal.
- Plugin permissions, sandboxing, signing, and trust model.
- Public plugin SDK and developer documentation.

The 2.0.0 work should preserve clean internal provider boundaries, but must not ship a plugin runtime or imply that plugins are supported.
