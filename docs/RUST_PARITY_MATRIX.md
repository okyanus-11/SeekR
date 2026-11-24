# SeekR native (Rust) parity matrix

Reference product: the published Python/PySide6 **v2.0.2** fallback.
Target: native **Rust 2.0.3**.

Legend:

- **Yes** — implemented, with automated tests where the logic allows it.
- **Partial** — some behavior exists; the row lists exactly what is missing.
- **No** — not implemented.
- **Verified** — actually exercised on this Windows machine, not just compiled.

> Compilation, Clippy and unit tests do not prove desktop behavior. Rows marked
> "compiled" were built and their logic unit-tested, but the interactive part
> has not been manually exercised.

## Launcher and search

| Feature | Python reference | Rust implementation | Tests | Status |
| --- | --- | --- | --- | --- |
| Interactive result list (rows, selection, hover, click) | `ui/launcher_window.py` result list | `ui/launcher.slint` `ResultRow` + `ListView` | compiled | Partial — no icons, no context menu, no per-row secondary actions |
| Keyboard navigation (↑/↓/Enter/Escape) | launcher key handling | `FocusScope.key-pressed`, `ListView` selection | compiled | Partial — page movement and Tab action-cycling missing; arrow-key propagation from `LineEdit` not manually confirmed |
| Mouse activation | launcher result rows | `TouchArea.clicked` | compiled | compiled |
| Background search, debounce, stale-result rejection | `core/workers.py`, generation guards | `src/main.rs` worker thread + `Request.generation` | unit-tested scheduling invariants | Yes (logic) |
| Fault-isolated providers (error + panic containment) | provider isolation | `SearchEngine::search_results` `catch_unwind` | `provider_errors_do_not_abort_search`, `provider_panics_are_contained` | Yes |
| Deterministic ranking + deduplication | ranking in `core/search.py` | `search.rs` score sort + dedupe | `ranking_is_deterministic_for_equal_scores`, `duplicate_targets_are_removed` | Yes |
| Typo tolerance | fuzzy matcher | Levenshtein token match | `typo_matching_requires_a_close_title_token` | Yes |
| `calc:` and plain arithmetic | calculator provider | `calculator` / `auto_calculator` | 5 tests | Yes |
| `time:` | date/time provider | `local_time()` | `time_prefix_returns_a_copyable_local_time` | Yes |
| `app:` / `file:` filters | category filters | `QueryKind::Apps` / `Files` | `app_and_file_prefixes_only_return_their_own_category` | Yes |
| Start Menu application index | `features/applications` | `WindowsAppsProvider` | compiled | Partial — `.lnk`/`.url`/`.exe` discovery only |
| User-folder file index (Desktop/Documents/Downloads) | `features/file_search` | `WindowsFilesProvider`, depth 2, 3000 cap | compiled | Partial — names only, no contents, no watcher |
| Shell launch (`.lnk`, `.url`, docs, folders) | shell integration | `explorer.exe <path>` | compiled | not manually verified |
| Copy action for calculator/time | clipboard copy | `arboard` via `SearchEngine::launch` | unit-tested rejection path | compiled |

## Documented search prefixes

| Prefix | Status |
| --- | --- |
| `calc:` | Yes |
| `time:` | Yes |
| `app:` | Yes |
| `file:` | Yes |
| `content:`, `web:`, `wiki:`, `yt:`, `gh:`, `define:`, `translate:`, `unit:`, `sys:`, `comm:`, `flow:`, `snip:`, `chain:`, `task:`, `wm:`, `update:` | **No** — intentionally not advertised in the native UI |

Unknown prefixes stay plain queries, so `wiki: rust` searches for that literal
text instead of silently returning a fake result.

## Widgets

| Widget | Status |
| --- | --- |
| Clock | Yes — live local time, 1 s timer |
| System (CPU/RAM/disk/battery/network) | No |
| Tasks | No |
| Weather | No |
| Daily cat | No |
| Media session | No |
| Per-widget enable/disable, rail width, card height, left/right order, persistence | Partial — preferences are stored atomically and restored on restart; there is no dashboard rendering them yet |

## Windows desktop integration

| Feature | Status |
| --- | --- |
| Single instance + activate existing window | **Yes — verified on Windows** (second launch exited 0, one process remained) |
| Global hotkey `Alt+Space` | Implemented via `RegisterHotKey` on a dedicated thread; registered without error during the smoke run. Activation not manually confirmed. |
| Tray icon and menu | No |
| Active-monitor placement / top-anchored dropdown / DPI | No |
| Startup preference | No |
| Hide/show lifecycle | Partial — launching a result hides the window; the hotkey re-shows it |
| Clean shutdown | Yes — `quit_event_loop` on Close |

## Settings, data, packaging

| Feature | Status |
| --- | --- |
| Versioned config with atomic writes, unknown-key preservation, malformed-file protection | Yes — 6 tests in `src/config.rs` |
| Legacy Python widget preference import | Partial — widget keys only |
| SQLite database and migration | No |
| Backups / rollback / integrity checks | No |
| Full settings and tools surfaces | No — only widget preferences |
| Themes, accent, typography, localization | No |
| Installer / portable release packaging | No — the Python installer is unchanged |
| Checksums, release notes, signed artifacts | No |

## Known verification gaps

1. No automated UI test: the Slint window is compiled but never driven by a
   test harness.
2. Arrow/Enter/Escape propagation from the std `LineEdit` to the surrounding
   `FocusScope` was not observed interactively.
3. Hotkey activation, monitor placement, DPI changes, sleep/resume and tray
   behavior remain unverified or unimplemented.
4. No long-session or rapid-reopen soak has been run against the native app.

These gaps are why the native build is **not** published as v2.0.3 yet.
