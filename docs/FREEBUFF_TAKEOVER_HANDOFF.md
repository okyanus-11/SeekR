# SeekR — Freebuff Takeover Brief

**Last verified against GitHub:** 2026-11-24 19:16 Türkiye time  
**Repository:** https://github.com/okyanus-11/SeekR  
**Default / sole working branch:** `main`  
**Verified HEAD:** `471ad729ff9968be1c77ab733d4fe84dd957e9ae`  
**Latest public release:** `v2.0.2` (Python + PySide6)  
**Current objective:** Finish SeekR 2.0.3 as the real, native Rust Windows desktop application.  
**Audience:** Freebuff (assume you have never heard of SeekR or spoken to its creator).

---

## 0. Read this first — the actual assignment

You are taking over an existing Windows desktop launcher project, not starting a new app and not merely reviewing a prototype.

The owner wants **SeekR 2.0.3 completed, tested, packaged, and published**. The owner explicitly selected Rust as the implementation direction because the application needs to become faster, lighter, more reliable, and easier to extend. The current published Python/PySide6 v2.0.2 is the fallback and must remain intact until the Rust replacement is genuinely ready.

Your job is to continue implementation, not produce another handoff, roadmap-only response, architecture essay, or green-compile victory lap. Work through the actual code, implement the missing functionality, run the tests, validate the Windows app, produce release artifacts, and publish only when the acceptance gates are satisfied. **Publication of a working release is the finish line.**

The current repository contains a serious ambiguity created by the previous assistant: it changed Python release metadata and documentation to a 2.0.3 candidate, while the owner had selected Rust for the 2.0.3 takeover. That Python candidate is not the requested Rust release. Do not silently treat it as the final objective. Preserve v2.0.2 as the stable downloadable release, separate the Python candidate from the Rust release identity, and resolve the version/documentation contradiction deliberately before publishing anything.

Do not claim a feature works because it exists in a Python module, a Rust type, a Slint control, a unit test, or a successful compile. Verify the complete user-visible behavior in the actual Rust Windows app.

## 1. Product: what SeekR is supposed to be

SeekR is a fast, keyboard-driven Windows desktop launcher and productivity hub. The user opens it with a configurable global hotkey (default `Alt + Space`), types naturally, navigates results from the keyboard, and launches or performs actions without hunting through Start, Explorer, or separate utility apps.

The product should feel immediate: fast startup, near-instant search, smooth interaction, low idle CPU/RAM, no UI freezes, no crashes, and dependable background work. It should look polished and cohesive rather than like a developer preview. It should behave like a proper Windows desktop application: hotkey, tray, active-monitor placement, single-instance activation, startup preference, clean close/reopen, installer, portable build, upgrade and uninstall.

**Quality priorities, in order:**
1. Reliability and responsiveness. No freezes, stale UI, lost input, or broken reopen.
2. Fast startup and search; expensive work must not block the UI thread.
3. Low memory and CPU use, including while idle.
4. Feature completeness and preservation of existing workflows.
5. Polished, consistent, responsive UI and sensible keyboard interaction.
6. Safe persistence, migration, packaging, and release engineering.
7. Modular architecture that can support future features without turning into a monolith.

The owner is quality-focused and has repeatedly been frustrated by incomplete work, missing requested features, premature stopping, handoffs that omit context, and claims that are not backed by real verification. Do not rush, skip a feature silently, or stop after writing a plan. Be honest and precise about what is actually complete.

## 2. Product history and version policy

- **v2.0.2** is the latest public release and the known-good Python/PySide6 implementation. Its public assets are `SeekR-Setup-2.0.2.exe`, `SeekR.exe`, and `SHA256SUMS.txt`. Do not overwrite or invalidate this release.
- The Python codebase is still present on `main` and contains a substantial working product, tests, installer scripts, and Windows integration. It is the behavioral reference and fallback.
- The Rust/Slint crate is currently a small preview, not a replacement yet.
- The current main branch also contains Python 2.0.3 candidate metadata, changelog and release notes from the previous assistant. These changes are not a published release and do not satisfy the Rust objective.
- Do not tag or publish a Python build as the Rust v2.0.3 replacement.
- Keep the release workflow's tag/version guard and existing-release protection. Never bypass them to make a release appear complete.

**Versioning decision to resolve:** establish one unambiguous product version/release identity for the Rust 2.0.3 target while keeping the Python 2.0.3 candidate clearly separate or reverting its candidate metadata/docs to the v2.0.2 fallback state. Align Cargo/package metadata, Windows executable metadata, installer metadata, README, changelog, release notes, tag, artifact names, and checksums. Explain the decision in the repo. Do not let the Python candidate accidentally become the official 2.0.3 release.

## 3. Repository state verified on 2026-11-24

Repository metadata:
- Public repository: `okyanus-11/SeekR`
- Default branch: `main`
- HEAD: `471ad729ff9968be1c77ab733d4fe84dd957e9ae`
- HEAD commit: **“Sample the installer payload during the stability soak”**
- Latest public release observed: `v2.0.2`, published 2026-11-20.
- Branch policy from project instructions: work on `main` only; do not create a feature branch unless the owner explicitly changes this instruction.

Recent commits on main include:
- `471ad729` Sample the installer payload during the stability soak
- `8620fcfd` Prepare 2.0.3 candidate release notes
- `4617a143` Set the Python release candidate version to 2.0.3
- `dd7bbec6` Terminate the packaged app process tree after stability sampling
- `76bc0fe9` Match packaged reinstall launch smoke to CI startup check
- `83b1df9e` Add Windows upgrade and stability release gates
- `0d3a46d7` Require matching version tags to publish releases

The last two Python-related candidate commits are the source of the version ambiguity described above. The recent Python reliability changes may be retained as useful fallback maintenance, but they are not Rust implementation work.

### Current top-level structure

- `core/`: Python application composition, configuration, database, search, workers, hotkeys, startup, logging, paths, models, errors.
- `features/`: Python feature providers and services (applications, bookmarks, calculator, clipboard, color tools, command center, commands, date/time, developer tools, diagnostics, dictionary, emoji search, file content/query/search, media, notes, power, process manager, quick actions/connect, quicklook, screenshots, snippets, system info, tasks, updates, utilities, web search, window management/search, workflows).
- `ui/`: Python launcher, widgets, settings, tools, themes, localization, dialogs and components.
- `tests/`: broad Python test suite covering core features, GUI, config, database, themes, localization, Windows compatibility, workflows, updates, etc.
- `src/`: Rust crate (`main.rs`, `search.rs`, `config.rs`, `lib.rs`).
- `ui/launcher.slint`: current native Slint shell.
- `.github/workflows/ci.yml`: Python test matrix and Windows packaging/release workflow.
- `.github/workflows/rust.yml`: Rust formatting, Clippy, tests and Windows optimized preview builds.
- `installer/seekr.iss`: Inno Setup installer definition.
- `docs/`: architecture, install, performance, privacy, troubleshooting, manual Windows test, migration and prior handoff documents.
- `tools/`: Windows stability/performance/test scripts and benchmark/icon utilities.

Important documents to read, but verify against current source:
- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/RUST_MIGRATION.md`
- `docs/CODEX_HANDOFF_2.0.3.md` (historical and partly stale; do not blindly follow it)
- `docs/INSTALLATION.md`
- `docs/WINDOWS_MANUAL_TEST.md`
- `docs/PERFORMANCE.md`
- `docs/PRIVACY.md`
- `docs/TROUBLESHOOTING.md`
- `CHANGELOG.md`

## 4. What the existing product does — parity inventory

The Python app is the product reference. Before porting, inspect the actual Python provider/UI/config/database implementations and tests. This inventory is a guide, not permission to replace working behavior with placeholders.

### Launcher and search
- Keyboard-first launcher, configurable global hotkey (default `Alt + Space`).
- App and file discovery, search ranking, fuzzy matching/typo tolerance, suggestions/history where configured.
- Selectable result rows and keyboard navigation.
- Primary and secondary actions, action cycling, context menu, copy/open behavior.
- Calculator expressions and copyable results.
- Search providers are isolated so one provider failure should not crash the whole launcher.
- Background indexing/search, cancellation/stale-query protection, responsive typing.
- Search aliases and configurable search behavior.
- Result limit and provider ordering/ranking should remain deterministic and useful.

### Search prefixes documented by the current README
Support only when the underlying action is actually implemented and verified:
- `file:` — indexed files
- `content:` — configured text-file contents (opt-in)
- `calc:` — calculator
- `web:` — configured web search
- `wiki:` — Wikipedia
- `yt:` — YouTube
- `gh:` — GitHub
- `define:` — dictionary/definition
- `translate:` — translation
- `unit:` — unit conversion
- `time:` — local time lookup
- `sys:` — system information
- `comm:` — built-in command
- `flow:` — workflow lookup/run
- `snip:` — saved snippets
- `chain:` — command chain
- `task:` — local tasks
- `wm:` — window management
- `update:` — official SeekR update check

Plain queries should rank matching applications/files and recognize calculator expressions where applicable. Do not add a visible prefix that only returns a fake result or a nonfunctional button.

### Launcher widgets
The existing product advertises optional cards beside the search results:
- **Clock:** local time/date and configurable focus timer.
- **System:** CPU, memory, storage, battery and network activity.
- **Weather:** current conditions for configured location.
- **Daily cat:** cat photo displayed in the launcher, fetched from TheCatAPI, validated, size-limited and cached locally; retain last-good content offline.
- **Media:** Windows media-session metadata and playback controls where supported; opt-in.
- **Tasks:** compact summary of open/overdue local tasks.

Widget expectations:
- Per-widget enable/disable.
- Configurable rail width and card height.
- Persistent left/right rail ordering.
- Configurable refresh intervals.
- Settings survive restart.
- Background network/metric collection; no blocking the UI.
- Cache useful last-good data and show stale/offline state clearly.
- Respect reduced-motion preferences.
- Do not show a widget as available if its provider/action is a placeholder.

### Settings, tools and other existing workflows
The Python implementation includes extensive settings and tools surfaces. Inventory them from `ui/settings_window.py`, `ui/tools_window.py`, `ui/tools/*`, `features/*`, and the test suite. Existing documented tools/pages include:
- Calculator, developer tools, date/time, color tools, dictionary.
- Screenshots, system information, process manager, power actions.
- Clipboard history/controls, quick notes, bookmarks, quick connect.
- Quick actions, workflows, text snippets, tasks.
- Database and backups, diagnostics.
- Themes (Graphite, Light, AMOLED, Catppuccin Mocha, Dracula, Nord), accent color, typography, launcher sizing, hotkey, search behavior, refresh intervals, reduced motion and focus styling.
- Localization: English, Turkish, Spanish, French, German, Italian, Brazilian Portuguese, Japanese and Simplified Chinese (partial translations are acknowledged).
- Startup integration, tray behavior, window management, update checks, local diagnostics export.

Some of these are later-version additions or are not explicitly required to be ported into 2.0.3. Do not silently omit a feature that is part of the 2.0.2 product without recording a clear scope/compatibility decision. The immediate 2.0.3 target is the existing launcher/search/widget experience plus reliability and native Windows integration. Do not pull the entire later roadmap into this release.

### Privacy and data handling
- User data is local by default. On Windows, Python's current data directory is under `%APPDATA%\\SeekR`; Rust config currently resolves to `%APPDATA%\\SeekR\\config.json`.
- Config and SQLite database are outside the install directory; uninstall should preserve user data.
- Clipboard monitoring is off by default and requires explicit opt-in. Clipboard contents and optional PNG captures are stored locally and are not encrypted. Stopping monitoring stops future capture; saved history is cleared separately.
- Sensitive clipboard filtering is heuristic, not a guarantee.
- Application usage ranking and file-content search are opt-in.
- Diagnostics reports are user-initiated; logs excluded by default, redaction best-effort; reports are not uploaded.
- Update checks read official GitHub release metadata; downloading/installing remains explicit.
- Do not weaken privacy defaults or collect more data to simplify implementation.
- Preserve unknown configuration keys and protect malformed user files. Never overwrite a malformed config just because parsing failed.

## 5. Rust preview: verified implementation and current gaps

### Current stack
- Crate: `seekr-native`, currently `0.1.0`
- Rust edition 2024, declared minimum Rust 1.95+
- Slint 1.19 desktop UI
- Serde / serde_json configuration
- `meval` calculator
- `arboard` clipboard
- `chrono` local clock
- `tempfile` for atomic configuration writes
- Windows-specific code is currently embedded in search provider modules; it should be isolated as the native architecture grows.

### What the Rust preview actually implements
- Slint desktop window and basic shell.
- Provider-oriented search abstraction with panic/error containment.
- Built-in `calc:` evaluation and clipboard copy.
- Windows Start Menu shortcut discovery (bounded recursion).
- Bounded shallow name/path indexing under Desktop, Documents and Downloads; it does not inspect file contents.
- Basic matching/ranking and typo tolerance.
- Initial app/file index construction on a worker thread.
- Previous/Next selection controls and an activation callback.
- Widget enabled-state, dimension and left/right order preferences in config.
- Legacy Python widget preference import and preservation of unrelated/unknown config keys.
- Atomic JSON save implementation and tests.
- Live local clock text updated once per second.
- Rust CI builds optimized Windows preview executables.

### What is missing or only a visual/persistence stub
- Results are currently rendered as one formatted text block, not a proper interactive list with rows, icons, metadata, hover/focus/selection states, and per-result actions.
- Search callback currently obtains results while holding the engine mutex; inspect exact code and move all potentially expensive query work off the UI thread. Add generation IDs/cancellation or stale-query suppression so old results cannot overwrite newer input.
- Search index construction is in the background, but the current design needs a robust lifecycle and safe handoff when indexing completes.
- Search provider behavior is very limited compared with the Python product. Many documented prefixes and providers do not exist in Rust.
- Launch currently uses Explorer on a path; validate correct behavior for `.lnk`, `.url`, executables, files, directories, permissions and errors. A result without a target/copy action must not pretend to launch.
- Only the clock has live data. System/tasks/weather/cat/media controls are not full widget implementations; enabled state and layout persistence are not feature parity.
- No complete dashboard/widget rendering and no real provider lifecycle/refresh/cache/offline behavior.
- Global hotkey integration is absent.
- Tray icon/menu and correct hide/show lifecycle are absent.
- Single-instance activation and repeated show/hide behavior are absent or unverified.
- Active-monitor-aware placement, top-anchored dropdown behavior and multi-DPI behavior are absent or unverified.
- Startup preference/integration is absent or unverified.
- Complete settings UI, themes, localization and tools surfaces are absent.
- SQLite database layer and migration are not implemented in Rust.
- Safe migration currently covers only a narrow slice of widget preferences. It is not a complete configuration/database migration.
- No supported Rust installer or portable release path.
- No actual interactive Windows 10/11 runtime or long-duration stability sign-off.
- The current Slint shell is a prototype layout, not the polished existing SeekR experience.

**Important:** `cargo fmt`, Clippy, tests and a successful optimized build do not prove that the Rust desktop application is usable or release-ready.

## 6. Critical known bugs and user-reported behavior

The existing Python app has had serious Windows lifecycle/repaint issues:
- Launcher can freeze/become unresponsive after rapidly dismissing and reopening it.
- Launcher has also been reported to freeze after approximately two minutes.
- Rebuilding the executable did not reliably fix the rapid-reopen issue.
- Previous local desktop smoke testing was inconclusive: a temporary PyInstaller wrapper failed to load QtCore, and later desktop automation could not reliably target the window.
- The user reported antivirus blocked something attempted during local testing. The exact file was not identified. Do not disable, bypass, or evade antivirus, and do not blindly rerun a blocked binary.

The previous assistant added Python mitigations on main: opaque surface instead of translucent layered rendering, position-only dropdown animation, hide/show generation/focus protections, background system metrics, nonblocking single-instance socket handling, bounded dictionary response reads, and result-row initialization before first show. Python CI also gained a packaged three-minute soak, process-tree cleanup, reinstall/uninstall checks, and upgrade/data-preservation checks.

These mitigations are useful history, not proof the bug is fixed in Rust. The native app needs its own correct lifecycle and repeated interactive tests.

## 7. Latest CI/release facts observed

As of this handoff:
- Python workflow run **45432261710** for HEAD `471ad729` completed successfully.
- Python workflow run **45428159763** completed successfully.
- Earlier Python runs **45247912028** and **45245547840** failed; later changes led to the successful newer runs.
- Rust workflow run **45239697979** was observed completed successfully for commit `f9a140a1`; this is an older Rust revision, not proof the current HEAD's Rust state is validated. Re-run/check the Rust workflow on current HEAD.
- Latest public release remains **v2.0.2**. No v2.0.3 release was present.
- Python workflow `ci.yml` runs Windows 2022, Windows latest and Ubuntu tests; it packages portable and onedir Windows builds, verifies packaged UI, performs a stability sample, and tests install/reinstall/uninstall and upgrade/data preservation.
- Rust workflow `rust.yml` runs formatting, Clippy, tests and optimized builds on Windows 2022 and Windows latest, then uploads preview artifacts. It does not package an installer, exercise interactive UI behavior, or perform a long-duration visible desktop test.

Recheck all workflow runs and logs at the beginning of the takeover. Statuses can change, and the IDs above are a snapshot, not a substitute for a fresh check.

## 8. Architecture and migration requirements

Use the Python implementation as a behavioral reference, not as code that must be copied line-for-line. Preserve a modular, testable architecture:

- **Application/lifecycle composition root:** owns app startup/shutdown, tray, hotkey, single-instance activation, window visibility, startup integration and coordinated service lifetimes.
- **Search engine:** owns query parsing, provider registry, ranking, deduplication, result limits, history/suggestions and action metadata.
- **Search providers:** independent, bounded, fault-isolated providers. One provider failure must not break other results or the UI.
- **Indexing:** asynchronous, cancellable, bounded and observable. Never scan user folders synchronously in the UI callback.
- **UI:** typed result models, actual result list, keyboard navigation, mouse selection, action menu and responsive layout. Keep expensive operations out of UI event handlers.
- **Widgets:** independent providers/models with explicit refresh cadence, cancellation, cache and stale/error state; layout and settings are persisted separately from transient widget data.
- **Persistence:** versioned validated config and SQLite repository layer. Atomic writes, backups, migration reports, rollback and unknown-key preservation.
- **Platform integration:** isolate Windows APIs (hotkey, tray, monitor/DPI, startup, media session, shell launch, clipboard) behind clear modules.
- **Diagnostics:** structured local logging and actionable error reporting without leaking private content.

Choose async/runtime and UI integration deliberately. Avoid unnecessary complexity or heavy always-on background loops. Do not hold a global mutex while performing filesystem scans, network calls, database work, process sampling, or UI callbacks. Avoid blocking the UI thread. Bound queues and caches. Ensure worker threads/tasks terminate or are safely cancelled on shutdown. Make repeated open/hide/show idempotent.

### Persistence and migration
- Keep data out of the installation directory.
- Preserve the Python user's existing `%APPDATA%\\SeekR` config and database.
- Inventory the actual Python JSON schema, SQLite schema, paths, migrations, WAL behavior, notes/tasks/snippets/workflows/clipboard/etc. before implementing migration.
- Back up the original config and database before migration. Use a versioned migration, validate the migrated result, and retain rollback/recovery if any step fails.
- Never delete/replace the original data until the new database passes integrity checks and the user can use the migrated data.
- Unknown config keys must survive read/write cycles.
- Malformed config must be preserved for recovery; report the problem and use safe defaults without silently overwriting it.
- Test fresh profile, existing v2.0.2 profile, interrupted migration, repeated migration, downgrade/fallback, and uninstall/reinstall.

## 9. Required execution order

Do not just repeat this list back. Execute it, committing focused changes and reporting evidence.

### Phase A — establish truth
1. Pull/read latest `main`; verify HEAD, tags, branches, releases, open issues and current Actions runs.
2. Read the source and tests, not only docs. Compare Python behavior to Rust behavior feature by feature.
3. Audit version metadata and every reference to 2.0.3. Separate the Python candidate from the Rust release objective without damaging v2.0.2.
4. Produce a concrete parity matrix in the repository: feature, Python reference location, Rust implementation location, tests, status, known limitations.
5. Run Rust formatting, Clippy, tests and Windows builds on current HEAD. Capture failures and fix them.

### Phase B — make the native launcher real
6. Replace text-rendered results with a typed, interactive result list. Include selected/focused states, mouse click, arrow navigation, Enter, Escape, page movement, action cycling, context menu and copy/open actions.
7. Implement robust search scheduling: background execution, debounce, generation/request IDs, stale-result rejection, bounded work, cancellation where practical, clear indexing/loading/empty/error states.
8. Improve app/file discovery and matching. Verify shell shortcuts actually launch correctly. Add provider tests and realistic Windows integration tests.
9. Implement the required 2.0.3 search behavior and only advertise prefixes/actions that work. Add tests for parsing, ranking, deduplication, typo tolerance, provider failure and actions.

### Phase C — widgets and customization
10. Build a real widget dashboard, not just checkboxes and persisted text fields.
11. Port the existing Clock, System, Tasks, Weather, Daily Cat and Media widgets with their documented behavior, opt-in/privacy settings, caching and refresh rules.
12. Implement enable/disable, dimensions, left/right order, refresh intervals and persistence. Verify restart restores the same layout and enabled state.
13. Ensure background providers cannot freeze the launcher; pause/slow refresh while hidden where appropriate; cancel cleanly at shutdown.

### Phase D — Windows desktop integration and lifecycle
14. Implement configurable global hotkey (default Alt+Space), with collision/error reporting and reliable unregister.
15. Implement tray icon/menu, show/hide/quit semantics and a true single-instance activation protocol.
16. Implement active-monitor placement, top-anchored dropdown behavior, DPI/multi-monitor handling and focus management.
17. Implement startup preference and safe shutdown/reopen. Avoid duplicate timers, event handlers, workers or windows after repeated toggles.
18. Verify app launch → hide → reopen rapidly many times, type/search while indexing, sleep/resume, display changes, hotkey collision, tray actions and close/quit.

### Phase E — data, settings and packaging
19. Implement versioned config and SQLite access with safe migration, backup/rollback and integrity checks.
20. Port the settings and tools that are in 2.0.3 scope; create explicit parity/scope decisions for all remaining v2.0.2 surfaces. No silent regressions.
21. Produce a portable executable and per-user installer. Python must not be required on end-user machines.
22. Verify fresh install, upgrade from v2.0.2, launch/use, uninstall, reinstall and data preservation. Ensure uninstaller preserves user data.
23. Align product metadata, installer version, release notes, README, changelog and checksums to the exact Rust binary that will ship.

### Phase F — release sign-off
24. Run all Rust tests/lints/builds and all relevant Python fallback tests.
25. Run Windows packaging and migration tests on clean profiles and a v2.0.2 profile.
26. Perform real visible desktop testing on Windows 10 and Windows 11 where available. Automated hidden-process sampling is not enough.
27. Repeatedly test rapid reopen and sessions substantially longer than two minutes; monitor memory/CPU and UI responsiveness.
28. Test multi-monitor/mixed DPI, sleep/resume, tray, hotkey, keyboard-only use, widget refresh and persistence.
29. Inspect final installer and portable artifacts; verify metadata and SHA-256 checksums.
30. Only after every gate passes, tag and publish the Rust v2.0.3 release. Verify the release page and uploaded assets after publication.

## 10. Definition of done — nothing less

A Rust v2.0.3 release is complete only when all applicable boxes are demonstrably true:

- [ ] Rust implementation is the actual shipped app; Python candidate is not accidentally published as its replacement.
- [ ] Search is interactive, responsive, correctly ranked and supports the promised actions.
- [ ] Search/index work is off the UI thread and stale queries cannot overwrite current results.
- [ ] Search providers are fault-isolated, bounded and tested.
- [ ] Required widgets render real data and work; customization persists after restart.
- [ ] Hotkey, tray, single instance, active-monitor placement, startup, hide/show/reopen and clean shutdown work on Windows.
- [ ] No rapid-reopen or roughly-two-minute freeze; root causes are understood, fixes have regression coverage, and repeated desktop tests pass.
- [ ] Existing user settings and database content are preserved or safely migrated with backup/rollback.
- [ ] Privacy defaults and opt-in behavior are preserved.
- [ ] Installer and portable executable are built from the Rust implementation and smoke-tested.
- [ ] Fresh install, upgrade from v2.0.2, uninstall and reinstall are verified; user data survives.
- [ ] Rust formatting, Clippy, tests, optimized builds, packaging checks and relevant fallback tests pass.
- [ ] Windows 10/11 visible runtime validation is recorded; CI compilation alone is not accepted.
- [ ] README, changelog, release notes, version metadata, installer metadata, tag, assets and checksums all describe the exact shipped build.
- [ ] Release is actually published and its assets verified.

If a gate cannot be completed because the environment lacks a Windows desktop, hardware, permissions or signing certificate, state that limitation explicitly and do not claim the release is fully ready. Do not fake test results.

## 11. Roadmap after 2.0.3

Keep future scope out of the current release unless a dependency is essential.

- **2.1.0:** System Monitor, Clipboard History, Focus Timer (as dedicated expanded features).
- **2.2.0:** Smart Search and personalization/adaptive ranking.
- **2.3.0:** Automation and user-configurable workflows.
- **3.0.0:** Plugin ecosystem and extensibility.

Plugins are deliberately deferred to 3.0.0. Do not spend 2.0.3 time building a plugin marketplace or unrelated future features.

## 12. Working rules for Freebuff

- Treat this brief as context, not as a substitute for inspecting the latest repository. Verify every current fact before acting.
- Work directly on `main`, consistent with the owner's current branch policy. Do not create branches unless explicitly authorized.
- Make real, incremental code changes. Commit focused, descriptive changes.
- Do not delete the Python fallback or damage the published v2.0.2 release.
- Do not replace requested functionality with mock data, static text, nonfunctional controls or TODO placeholders.
- Do not claim feature parity based on a compile or unit test alone.
- Never run expensive work on the UI thread.
- Never bypass antivirus or Windows security controls. If a binary is blocked, identify the exact file and investigate safely.
- Preserve user data and privacy defaults.
- Do not stop after producing a plan, partial prototype, or another handoff. Continue implementing and validating until release is actually published, or clearly identify the specific external blocker preventing completion.
- Be transparent: distinguish implemented, tested, manually verified, and released. Never label an unverified feature “done.”
- When reporting progress, say what changed, which files, which tests ran, their actual results, and what remains. Avoid vague “fixed” claims.

## 13. First actions for the takeover session

1. Verify repository HEAD is still `471ad729ff9968be1c77ab733d4fe84dd957e9ae` or record the new one.
2. Inspect all branches/tags/releases and current Actions runs. Confirm only `main` is the intended work branch.
3. Read `README.md`, `docs/ARCHITECTURE.md`, `docs/RUST_MIGRATION.md`, `docs/WINDOWS_MANUAL_TEST.md`, `docs/PRIVACY.md`, and this file.
4. Inspect the full Rust files and the matching Python source/tests for each feature; do not rely on summaries.
5. Reconcile the Python 2.0.3 candidate metadata with the Rust 2.0.3 objective before any release action.
6. Run current Rust CI and inspect its logs. The previously observed successful Rust run is older than current HEAD.
7. Create/update the parity matrix and start implementing the highest-impact missing Rust functionality.

**The owner wants a finished product, not another prototype. Finish SeekR 2.0.3 properly.**
