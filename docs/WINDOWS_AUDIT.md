# Historical Windows compatibility audit — SeekR 1.0.0

> This report records the 1.0.0 audit and its 2026-11-15 follow-up. It is historical evidence, not a validation report for SeekR 2.0.0. For the current release candidate, use [RELEASE_PLAN_2.0.0.md](RELEASE_PLAN_2.0.0.md) and [WINDOWS_MANUAL_TEST.md](WINDOWS_MANUAL_TEST.md).

Initial audit: 2026-11-14

Windows follow-up: 2026-11-15

## Scope and environment

The source audit inspected every source module, the test suite, the build
script and the runtime assets of SeekR 1.0.0. Its host was a **headless Linux
x86-64 container** (Python 3.12.3, PySide6 6.12.0, psutil 7.2.2, SymPy 1.14.0,
SQLite with WAL). It had:

- no Windows installation or Windows VM,
- no Wine or other Win32 compatibility layer,
- no display server (Qt ran with `QT_QPA_PLATFORM=offscreen`),
- no PyInstaller Windows bootloader (PyInstaller cannot cross-compile).

Consequently this document distinguishes three kinds of evidence:

| Label | Meaning |
|---|---|
| **REAL** | Executed in the referenced environment against real files, SQLite, Qt widgets or the real Python standard library. |
| **SIMULATED** | Windows path/argument/registry behaviour exercised by injecting Windows semantics (for example `os.name == "nt"` or `windows=True`) into real code. |
| **MOCKED Win32** | Code that calls a Win32 API was exercised with a fake implementation of that API. This proves the call sequence and error handling, not Windows behaviour. |
| **UNVERIFIED** | Requires Windows and was not executed. It must not be treated as tested. |

**Final release-validation status (2026-11-15):** On Windows 11 build 26300,
Python 3.12.10 passed **169 tests, 2 skipped**; the Python 3.12 executable and
installer were built and version-checked. The installer was installed,
same-version reinstalled, visibly launched, and uninstalled; the Start Menu
shortcut and uninstaller entry were checked, and an isolated `%APPDATA%`
database plus sentinel survived uninstall. The visible GUI calculated
`calc: 2+2` as `4`. A configured alternate global hotkey worked, but repeated
packaged show requests did not consistently make the launcher visible in this
scripted test; the machine's default `Alt+Space` was already owned by another
application. The repeated-activation cause was identified and fixed after this
run; see "Post-validation fix: repeated packaged activation" below. Linux CI, older-version upgrade, signing/SmartScreen and several
native shell behaviors remain unverified. See the final evidence below.

## Method

1. Read the whole repository: entry point, core services, all feature services,
   all search providers, Qt windows/pages, build script, assets, tests and
   documentation.
2. Grepped for platform branches, subprocess use, shell invocation, hard-coded
   paths, encoding assumptions, thread boundaries and Win32 `ctypes` calls.
3. Ran the existing suite to establish a baseline (128 passing tests on Linux).
4. Repaired concrete defects (below), keeping the architecture and all features.
5. Added `tests/test_windows_compat.py` with 26 tests, each explicitly labelled
   `[REAL]`, `[SIMULATED]` or `[MOCKED Win32]`.
6. Ran the full suite, byte-compilation, `main.py --version`, and PyInstaller
   packaging on Linux as far as it is meaningful.
7. Parsed the shipped `.ico` and the generated Windows version resource with
   PyInstaller's own parsers to validate their structure.

## Defects found and fixed

### Launcher, focus, hotkey and tray

| # | Finding | Fix | Evidence |
|---|---|---|---|
| 1 | Window enumeration used 32-bit `HWND` ctypes signatures; 64-bit handles were truncated. The enumeration callback also called `GlobalFree` on a pointer it did not own. | Correct 64-bit signatures, callback lifetime handling, no invalid free. | Code review; non-Windows fallback test |
| 2 | Setting a new hotkey could leave SeekR with **no** working hotkey when re-registration failed. | Register the new combination first; restore the previous one on failure; expose `last_error`; Settings verifies registration and reverts the field. | `test_hotkey_registration_and_failure_reporting` (MOCKED Win32) |
| 3 | The tray menu object had no retained reference and could be garbage-collected; the tray could not be enabled after starting with it disabled. | Retain `_tray_menu`, create the tray lazily when the setting changes, avoid duplicates. | `test_tray_menu_is_retained_and_created_on_demand` (REAL Qt / availability mocked) |
| 4 | Windows could leave the frameless launcher behind other windows after a hotkey press. | Added a platform `force_foreground()` helper and applied it only on Windows; no-op elsewhere. | Code review; Linux fallback test |
| 5 | "Hide when focus is lost" could hide the launcher while a modal child dialog was open. | Skip deactivation hiding while a modal dialog is active. | Code review; existing GUI tests |
| 6 | `general.start_minimized` was stored but ignored at startup. | Honoured by the entry point when `--hidden` is not given. | Code review |
| 7 | Appearance changes reopened the launcher instead of repainting it. | Added `refresh_appearance()` and used it for live theme/config changes. | Existing GUI tests |
| 8 | Single-instance code could signal activation twice and left sockets/server objects open. | One explicit activation signal, tracked and closed sockets, server closed at exit. | `test_single_instance_forwards_activation` (REAL, Linux backend) |
| 9 | Startup registration was not reconciled with the configuration. | Compare the Run-key/autostart state at startup and correct the stored setting. | `test_startup_registry_toggle` (MOCKED Win32) |

### Application discovery

| # | Finding | Fix | Evidence |
|---|---|---|---|
| 10 | `applications.index_start_menu` was ignored; disabling Start Menu indexing still scanned it. | The switch is honoured, with a helpful empty-state message. | `test_application_scan_respects_start_menu_toggle` (SIMULATED) |
| 11 | Program Files scanning assumed non-empty environment variables, included `WindowsApps`/recycle-bin noise, produced duplicates and could raise on unreadable directories. | Robust root resolution, skip markers, case-insensitive dedupe, `onerror` handling, depth cap. | `test_program_files_scan_is_robust` (SIMULATED) |
| 12 | Application scanning ran synchronously from the search provider, freezing the launcher on first use. | Provider returns an "Indexing applications…" result and requests a background re-index; results refresh afterwards. | `test_application_provider_never_indexes_on_the_gui_thread` (REAL) |
| 13 | Applications from user-chosen portable folders could not be added at all. | Added `applications.directories`, a Windows-aware scanner (`.lnk`, `.exe`; `.desktop` elsewhere) and a Settings → Applications list editor. | `test_custom_application_folder_scans_lnk_files` (SIMULATED path) |
| 14 | `.lnk`/`.exe` paths with spaces or arguments were vulnerable to quote handling. | Shared Windows-correct argument splitter is used for commands; `.lnk` files are opened through the shell, executables launched with an argument vector. | `test_split_args_windows_quoting` (REAL parser, Windows rules) |


### File search, indexing and paths

| # | Finding | Fix | Evidence |
|---|---|---|---|
| 16 | Default folders were assumed to be `~/Desktop`, `~/Documents`, `~/Downloads`, wrong under OneDrive redirection and localised Windows profiles. | Resolve Windows Known Folders through `SHGetKnownFolderPath` with a safe fallback. | `test_known_folder_fallback_and_defaults` (MOCKED Win32 / SIMULATED) |
| 17 | Hidden/system files were not detected on Windows; only dotfiles were skipped. | `FILE_ATTRIBUTE_HIDDEN`/`SYSTEM` are checked via `GetFileAttributesW` with the correct signature. | `test_windows_hidden_attribute_detection` (MOCKED Win32) |
| 18 | Directory traversal could follow junctions/symlinks into cycles or unrelated trees on Windows. | Do not traverse reparse points/symlinks by default; skip protected/system locations; keep depth and entry limits. | Code review; indexing tests |
| 19 | Reaching `max_files` was reported as a user cancellation. | Separate `limit_reached` from `cancelled`, with a clear status message. | `test_file_index_limit_is_not_reported_as_cancellation` (REAL, 1002 files) |
| 20 | Indexing errors on individual directories could abort the whole run. | Per-entry and per-directory error handling; the run continues and reports skipped paths. | Code review; indexing tests |
| 21 | Text previews assumed UTF-8, garbling Notepad-style UTF-16 files. | Detect UTF-16 LE/BE and UTF-8 BOMs, then fall back to the platform preferred encoding. | `test_text_preview_decodes_windows_utf16` (REAL) |
| 22 | `reveal in Explorer` built fragile quoting and did not select the file. | `explorer.exe /select,"<path>"` construction with validation, and a separate open-folder path. | `test_explorer_select_command` (REAL) |

### Windows features

| # | Finding | Fix | Evidence |
|---|---|---|---|
| 23 | `powercfg` was invoked by bare name and its exit status was ignored, so failures looked like success. | Resolve the absolute system executable, return `(returncode, output)`, handle non-zero exits and decode errors. | `test_powercfg_uses_exit_status` (MOCKED subprocess) |
| 24 | Critical Windows processes (and SeekR itself) could be terminated from the process manager. | Refuse protected PIDs/names and self-termination with an explanatory result. | `test_critical_processes_are_protected` (REAL on Linux names + policy) |
| 25 | Snipping Tool launch failed when the `ms-screenclip:` handler was absent; screenshot location was not configurable in the UI. | Direct URI launch with a documented fallback, race-safe file checks, and a Settings → Files screenshot-folder editor. | `test_screenshot_directory_setting_is_used` (REAL) |
| 26 | Firefox bookmarks ignored the WAL file, so recent bookmarks were missing or the copy was inconsistent. | Copy `places.sqlite` together with `-wal`/`-shm` before reading. | Code review |
| 27 | Commands ignored `general.confirm_destructive_actions`, decoded output strictly, and relied on Unix-only signals for sleep/lock. | Honour the setting, decode with replacement, use ctypes on Windows with a portable fallback, improve Recycle Bin messages. | Code review; command tests |
| 28 | GPU/system information blocked the GUI thread with PowerShell/WMI, and CPU sampling blocked for 150 ms per refresh. | Non-blocking CPU sampling, cached GPU snapshot refreshed by a daemon thread, UTF-8 PowerShell output and `errors="replace"`. | `test_gpu_probe_never_blocks` and `test_windows_gpu_query_forces_utf8` (MOCKED subprocess) |
| 29 | SSH detection and terminal launching used Unix assumptions on Windows. | Detect `ssh.exe`/OpenSSH; use Windows Terminal when available or launch `ssh` directly in a new console without constructing a `cmd.exe` command. | Code review |
| 30 | Default screenshot, quick-action and notes locations used POSIX assumptions. | Known-folder/`%APPDATA%` based defaults. | Path tests |

### Configuration, database and build

| # | Finding | Fix | Evidence |
|---|---|---|---|
| 31 | Configuration directory used one platform-neutral path and could fall back inside the install tree. | `%APPDATA%\SeekR` on Windows, `~/.config/SeekR` on Linux, Application Support on macOS; `SEEKR_HOME` override; executable location never used for user data. | `test_windows_paths_survive_config_roundtrip` (REAL config, Windows path strings) |
| 32 | Configuration writes must survive interruption and Windows replace semantics; corrupt JSON must not block startup. | Reviewed the existing same-directory temporary-file + `os.replace` write and corrupt-file backup; retained and covered by tests. | Existing config tests |
| 33 | `--onedir` packaging reported/detected the wrong artifact path. | `output_target()` resolves `dist/SeekR.exe`, `dist/SeekR`, or `dist/SeekR/SeekR` per platform/mode. | `test_build_output_paths` (REAL) |
| 34 | The build could leave its spec and version resource in the source root. | `--specpath build`, version resource written to `build/version_info.txt`. | Build run below |
| 35 | The Windows icon and version metadata were not structurally validated. | Generated multi-size ICO; parsed it and the version resource with PyInstaller's parsers. | Build validation below |

## Verification actually performed

### Windows follow-up (2026-11-15)

Environment: Windows 11 build 26300, PowerShell 5.1, Python 3.14.7,
PySide6 6.12.0. This is a real Windows run, separate from the initial Linux
audit above.

- `tools\windows_test.ps1`: **11 PASS, 0 FAIL, 1 SKIPPED**. It installed and
  checked dependencies, byte-compiled sources, ran the full suite, checked
  `main.py --version`, built `dist\SeekR.exe` and verified its version metadata.
- `pytest -q -ra`: **168 passed, 2 skipped**. The skips are
  `tests/test_commands.py:47` (only meaningful off Windows) and
  `tests/test_features.py:184` (requires a real Windows shortcut). The
  process-isolated repeated-show regression test also ran in this Windows
  suite.
- `python -m pip check`: no broken requirements. `python main.py --version`
  printed `SeekR 1.0.0`.
- PyInstaller built a **62.8 MiB** Windows one-file executable. Windows file
  metadata reports `ProductName=SeekR` and `ProductVersion=1.0.0`.
- The frozen app started with `--hidden --no-hotkey` using an isolated
  `SEEKR_HOME` and created its startup log. A later process audit found that
  the earlier smoke test had left a PyInstaller child running; PID 20728 was
  identified and stopped during final validation. The earlier smoke test
  therefore did not establish reliable child-process cleanup.
- `ISCC.exe` 6.7.3 compiled `dist\installer\SeekR-Setup-1.0.0.exe` without
  warnings after updating the architecture identifiers.

The local Python version was 3.14.7, not the Python 3.12 configured in CI. The
Linux CI job and current post-hardening changes have not been run locally on
Linux; the earlier 154-test Linux result belongs to the initial audit.

### Test suite

Command (Linux, offscreen Qt):

```bash
QT_QPA_PLATFORM=offscreen SEEKR_HOME=/tmp/seekr_test pytest -q
```

Result: **154 passed, 0 failed, 0 skipped** (exit code 0). This includes the
pre-existing 128-test suite and 26 new Windows-compatibility tests. The new
tests are labelled by evidence type; none of them claims to have executed a
Win32 API. `python -m compileall` over `core`, `features`, `ui`, `main.py`,
`build.py` and `tests` succeeds. `python main.py --version` prints
`SeekR 1.0.0`.

Windows coverage inside the 26 tests includes: argument quoting, Explorer
selection, Known Folder fallbacks, hidden attributes, Program Files scanning,
Start Menu toggle, custom shortcut folders, non-blocking application indexing,
mock hotkey registration/failure rollback, mock Run-key startup, mocked
`powercfg`, UTF-8 PowerShell GPU parsing and caching, file-limit semantics,
critical-process protection, real single-instance forwarding on the Linux
backend, tray menu lifetime/lazy creation, non-Windows window fallback, build
artifact paths, config round-trips with Windows paths, UTF-16 text previews and
the screenshot directory setting.

### Packaging

PyInstaller 6.22.3 was installed and `python build.py --onedir` and
`python build.py` were executed **on Linux**. They produced:

- `dist/SeekR/SeekR` (onedir, 13.5 MiB directory build)
- `dist/SeekR` (onefile, 73.0 MiB, ELF x86-64 — not a Windows executable)

Both were launched with `QT_QPA_PLATFORM=offscreen` and an isolated
`SEEKR_HOME`. `--version` printed `SeekR 1.0.0`; the GUI initialised, registered
all providers, created `seekr.db` and logs in the isolated data directory, and
indexed in the background. This proves the frozen import graph, asset
bundling and data-directory logic work in a PyInstaller build **on Linux**. It
does not prove the Windows executable works.

The generated `assets/icons/seekr.ico` contains seven PNG-compressed entries
(16, 24, 32, 48, 64, 128, 256 px); PyInstaller's Windows icon reader accepts
all of them. The generated `build/version_info.txt` parses as a
`VSVersionInfo` with product name `SeekR`, version `1.0.0`, description,
company, copyright and original filename `SeekR.exe`. The initial Linux audit
could not produce a Windows executable; the subsequent native Windows build
and metadata verification are recorded above.

## Final release validation (2026-11-15)

Environment: Windows 11 build 26300, Python 3.12.10, PyInstaller 6.22.3,
Inno Setup 6.7.3. No files were committed or pushed and no release was
published.

### PASS

- `QT_QPA_PLATFORM=windows python -m pytest -q -ra` in the isolated Python
  3.12.10 environment: **169 passed, 2 skipped**. Skips:
  `tests/test_commands.py:47` (only meaningful off Windows) and
  `tests/test_features.py:184` (requires a real Windows shortcut).
- The process-isolated repeated-show regression test passed as part of that
  suite; separate packaged GUI activation results are recorded below.
- `python -m compileall -q core features ui tests` and `python -m pip check`.
- Python 3.12 Windows build produced `dist\SeekR.exe` (63,839,004 bytes).
  Explorer version metadata reports `ProductName=SeekR`,
  `ProductVersion=1.0.0`, and `FileVersion=1.0.0`. PyInstaller's archive
  reader found 850 entries and the embedded `assets\icons\seekr.ico` and
  `assets\icons\seekr.png`.
- Inno Setup compiled `dist\installer\SeekR-Setup-1.0.0.exe`
  (65,132,673 bytes). Its product name/version are SeekR/1.0.0. Both artifacts
  are **unsigned**.
- The installer used its documented default per-user path,
  `%LOCALAPPDATA%\Programs\SeekR`; the Start Menu shortcut resolved to the
  installed `SeekR.exe`, and the 1.0.0 uninstall entry was present.
- First visible packaged launch appeared after **20.14 seconds** in this
  environment. The GUI search `calc: 2+2` visibly displayed `4`.
- Same-version reinstall completed successfully. Uninstall removed the
  binaries, shortcuts and registry entry (directory cleanup completed
  shortly after the uninstaller returned). A database and sentinel under an
  isolated `%APPDATA%\SeekR` test profile remained intact.
- A non-conflicting `Ctrl+Alt+Shift+F11` registered and hid/showed the
  launcher. The machine's default `Alt+Space` was already registered by
  another application; SeekR reported that conflict rather than claiming
  success.

### FAIL / UNVERIFIED

- **FAIL (cause fixed afterwards, re-test pending) — repeat packaged GUI
  activation was inconsistent.** A second process logged that it had forwarded
  a show request; one packaged activation was observed, but later scripted
  repeated launches exited successfully without a visible primary window. The
  cause was located after that run and is documented under "Post-validation
  fix: repeated packaged activation" below. This does not invalidate the
  passing process-isolated socket tests, but user-facing repeated activation is
  not release-verified and needs manual retest on a clean Windows desktop.
- **UNVERIFIED — older-version upgrade.** Only same-version reinstall was
  possible without an earlier installer.
- **UNVERIFIED — Linux CI.** WSL is installed without a Linux distribution;
  Docker and Podman are unavailable. The current workflow was not pushed or
  run remotely.
- **UNVERIFIED — default hotkey on a clean machine.** `Alt+Space` was occupied
  on this host. A custom hotkey worked; test the default on a clean desktop.
- **UNVERIFIED — signing and SmartScreen.** Both local artifacts report
  `NotSigned`; no signing certificate or reputation check was available.
- **UNVERIFIED — tray interactions**, clean user-initiated quit, Start Menu
  `.lnk` enumeration and launching, Windows power/screenshot APIs, startup
  registry toggle, browser profiles, clipboard integration, multi-monitor/DPI,
  Windows 10, and packaged performance.

## Linux CI-equivalent run (2026-11-15, post-takeover)

Environment: Ubuntu 24.04 container, Python 3.12.3, PySide6 6.12.0,
`QT_QPA_PLATFORM=offscreen`. A minimal container image does not ship the Qt
system libraries, so `libegl1`, `libglvnd0`, `libxkbcommon0`, `libfontconfig1`,
`libfreetype6`, `libpng16-16t64` and `libbrotli1` were extracted locally for
this run; the GitHub Actions workflow now installs the required set explicitly
instead of relying on the runner image.

- `pytest -q`: **171 passed, 0 failed, 0 skipped** against the code as handed
  over, then **176 passed** after the activation and quit regression tests
  described below.
- `python -m compileall -q core features ui tests main.py build.py`: clean.
- `python main.py --version`: `SeekR 1.0.0`.
- `python build.py` (Linux, not Windows): `dist/SeekR`, a 73.0 MiB one-file
  build.

This is a real Linux run of the current code. It does not replace the Windows
runs above and says nothing about Windows-only APIs.

## Post-validation fix: repeated packaged activation (2026-11-15)

The Windows run above recorded that a second process logged a forwarded show
request while the running instance did not consistently make its window
visible. Inspecting the activation path found four defects (A–D), all in SeekR's
own code rather than in PySide6 or the installer. A fifth, unrelated defect (E)
was found while smoke-testing the frozen build.

| # | Defect | Fix | Evidence |
|---|---|---|---|
| A | `LauncherWindow.show_launcher()` never stopped the "hide when focus is lost" timer. Windows refuses `SetForegroundWindow` from a process that did not receive the last input event, so a programmatically raised window could be visible but inactive, and the deactivation timer then hid it 140 ms later: a request that was forwarded successfully producing no visible window. | Showing the launcher cancels any pending hide and opens a 1.0 s activation grace period. While it runs, a visible-but-inactive window retries foreground activation every 120 ms instead of hiding. The deadline is absolute, so retries always terminate, and the grace is skipped once `WindowActivate` confirms activation, so clicking away still hides the window. | `test_show_survives_a_refused_foreground_activation` (SIMULATED Windows activation refusal), `test_hide_on_focus_loss_still_hides_after_the_activation_grace` (REAL Qt) |
| B | A fade-out still in flight when a show request arrived could complete and hide the window that had just been re-shown. | Hide operations are generation-stamped; a fade superseded by a show no longer hides anything. | `test_a_superseded_hide_animation_cannot_hide_a_reshown_launcher` (REAL Qt animation) |
| C | The launching process asked the running instance to raise its window without transferring its own permission to take the foreground. | `SingleInstance.notify_existing()` calls `AllowSetForegroundWindow(ASFW_ANY)` first, best effort and Windows only. | Code review, and a no-op off Windows verified by the full suite. **UNVERIFIED on Windows.** |
| D | `SeekRApplication.show_launcher()` discarded a request silently when the launcher had not been constructed yet. | Logs a warning instead of failing silently. No request can be dropped in practice: no event-loop work runs between the single-instance server starting and the signal being connected. | `test_single_instance_show_request_reveals_the_launcher` (REAL socket) |
| E | **Quitting did not quit.** `SeekRApplication.quit()` called `app.quit()`, which was a no-op for the entire application lifetime once the controller was running: the event loop survived a `quit()` issued at 100, 300, 600, 900, 1200, 2000 and 3000 ms (7 of 7 runs), while `app.exit(0)` stopped it in all 6 runs at the same delays. The tray's **Quit SeekR** action therefore left the process running. | The quit path calls `app.exit(0)` directly, the primitive that `quit()` is documented to be equivalent to. | `test_controller_quit_stops_the_event_loop` (REAL Qt event loop, subprocess with its own watchdog so a regression fails instead of hanging). Confirmed to fail with the old `app.quit()` and pass with `app.exit(0)`. |

### End-to-end packaged check (Linux, offscreen Qt)

The frozen `dist/SeekR` one-file build was started with `--hidden --no-hotkey`
and an isolated `SEEKR_HOME`. Five consecutive `./dist/SeekR` launches each
logged `SeekR is already running; asked the existing instance to show` and
exited with code 0; the primary logged `Show request received from another
instance` five times, stayed alive, and recorded no exception (5 forwarded, 5
handled). This verifies that the packaged forwarding path and the new
activation code execute cleanly in a frozen build, and it closes the
diagnostic gap that made the original failure hard to read. It is **not**
evidence about Windows foreground behaviour, which still requires a real
Windows desktop.

One harness detail matters for future validation: a PyInstaller one-file
program runs as a bootloader parent plus a child (and the child can spawn
further children), so killing the PID you started leaves the real application
running. The earlier note in this document about a leftover PyInstaller child
has the same cause. Kill the whole process group, or close SeekR from its own
Quit action, rather than a single PID.

The quit defect above was found while smoke-testing this frozen binary and is
reproducible in source mode as well. The reproduction is on Linux with
offscreen Qt; whether Windows behaves identically has not been established
here, but `exit(0)` is the primitive `quit()` is documented to be equivalent
to, so calling it directly is safe on every platform. The
frozen build was not re-run through a tray-initiated quit because the packaged
build exposes no non-interactive quit hook; that path needs manual confirmation
on a desktop (manual tests T04 and T09).

## Second post-validation fix: Windows single-instance forwarding (2026-11-15)

A Windows 11 build of the patched tree (Python 3.12.10, PySide6 6.12.0,
PyInstaller 6.22.3) exposed a defect that Linux cannot reproduce:
`test_single_instance_forwards_only_one_show` failed deterministically (0/5 in
isolation) with `notify_existing()` returning `False`. Stage instrumentation
showed the socket connected, the four-byte payload was accepted, and the
primary emitted `show_requested` on every run: only the return value was wrong.

Cause: `notify_existing()` treated `waitForBytesWritten()` as proof of
delivery. Qt returns `False` from that call when the write buffer is already
empty, which is what Windows does for a write this small. `main.py` then took
the `False` branch, so instead of forwarding and exiting, the second process
called `listen()`. That runs `QLocalServer.removeServer(key)`, destroying the
running instance's socket name, and started a second application instance with
its own window, database connection and hotkey registration.

That explains the reported symptom class better than a pure focus problem. The
activation grace period added earlier therefore fixes the visible-but-inactive
case only; it is not the complete explanation.

Fix: only wait for pending bytes when `bytesToWrite() > 0`; an empty buffer
means the payload has already been handed to the OS. Linux after the change:
`176 passed`, and `-k single_instance` `2 passed`. **Not yet re-verified on
Windows** - the rebuilt executable has to demonstrate it.

The previously recorded Windows baseline of 169 passed / 2 skipped is
inconsistent with this result, because neither the failing test nor the
`waitForBytesWritten` gate changed between that commit and the tree tested
here. Either that baseline did not execute this test, or it referred to
different code.

## Third post-validation fix: Windows single-instance connect retry (2026-11-15)

The Windows offscreen reproduction of `test_single_instance_forwards_only_one_show`
still reported `notify_existing() -> False` even after the second fix: stage
instrumentation showed `connect=True`, `bytesToWrite=4`, `waitBW=True` and
`received=1` (the primary did emit `show_requested`), yet the call returned
`False`. The flush gate added by the second fix was therefore not the whole
story — the second process never reached it.

Cause: under the offscreen QPA the event dispatcher pumps pipe events more
slowly, so `connectToServer` + `waitForConnected` can fail spuriously on the
first attempt even though a retry (or a separate probe) connects and the
request is delivered. The earlier "connect=True" in the diagnostic was a
separate probe, not the call's own connection. `waitForBytesWritten` likewise
reports `False` for a buffer already handed to the OS.

Fix: `notify_existing()` now retries `connectToServer`/`waitForConnected`
within the overall timeout budget (sleeping briefly between attempts) and
ignores the `waitForBytesWritten` return value, only using it to push the
payload through. Linux after the change: `176 passed`, `-k single_instance`
`2 passed`. **Not yet re-verified on Windows** — the rebuilt executable has
 to demonstrate it, and the offscreen reproduction is the proxy test.

## Remaining release blockers after this work

1. **Native Windows re-validation of repeated activation** (manual tests L06,
   L11, L12) after the fix above. The regression tests simulate the Windows
   activation refusal; they do not perform it.
2. **Real older-version upgrade** (manual tests I04–I06). The installer's
   in-place upgrade and user-data preservation are correct by inspection and
   same-version reinstall passed, but no upgrade from an earlier build has been
   run.
3. **Clean-machine default hotkey** (`Alt+Space`) and possibly-unavailable
   combinations (L02, L07, L08).
4. **Signing and SmartScreen** (I07). Both artifacts are unsigned by design at
   this stage; no certificate exists.
5. **Windows 10** and **visible GUI/native shell behaviour** (L01–L12, S01–S20,
   T01–T11) beyond the checks already recorded above.
6. **Git tag does not match the released code.** The `v1.0.0` tag still points
   at commit `2e4f1a9`, while `main` has moved on to the release-preparation
   commit. Tagging, release notes and artifacts must be reconciled before
   publishing; that decision was deliberately left to the repository owner.

## Residual risks

- **Mocked Win32 signatures can still be wrong in detail.** The 64-bit HWND
  and `GetFileAttributesW` signatures were corrected against the Windows API
  documentation, but the automated suite does not individually verify every
  call against the live API.
- **COM/shell behaviour** (`.lnk` icons, Start Menu, tray) can differ between
  Windows versions, shell replacements and locked-down enterprise profiles.
- **Frozen Windows imports** can differ from Linux. PyInstaller's Windows
  analysis, visible installed first launch and isolated-profile installation
  passed, but optional feature paths and other profile configurations were not
  exhaustively tested.
- **PNG-compressed icons** are accepted by current PyInstaller and Windows
  Vista+, but Explorer rendering was not inspected.
- **Packaged-build performance** is not measured; NTFS, Defender, one-file
  extraction and cold starts can change startup and indexing behavior
  substantially. Source-mode measurements are recorded separately.

## Reproduce this audit

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate ; Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt

python -m compileall core features ui main.py build.py tests
python main.py --version
QT_QPA_PLATFORM=offscreen pytest -q        # Linux headless
python build.py --onedir                   # Linux build for packaging checks
```

## Remaining Windows release checklist

The automated checks above passed on one Windows 11 machine. Before claiming
full native compatibility or publishing, run the remaining checks on clean
Windows 10 and Windows 11 machines and record the results:

1. Install, launch, upgrade and uninstall the generated setup program; verify
   shortcuts, first-run data in `%APPDATA%\SeekR`, and that existing user data
   survives upgrades and uninstall.
2. Launch `dist\SeekR.exe` visibly; verify the window, icon, no console and no
   missing-module dialog.
3. Complete `docs/WINDOWS_MANUAL_TEST.md`; automated tests cannot cover the
   hotkey, tray, DPI or visual behaviour.
4. Exercise every Phase 6 item: Alt+Space, Escape, app/file/calculator/web/
   command search, settings, all themes, tools pages, clipboard, notes
   persistence, tray, clean exit, restart with preserved settings.
5. Check hotkey conflict handling with another app owning `Alt+Space`.
6. Check a non-admin account, a path with spaces and Unicode, a OneDrive-
   redirected profile, 125%/150%/200% DPI, and a second monitor.
7. Measure the packaged build on representative hardware and record the OS,
   hardware, workload and methodology in `docs/WINDOWS_PERFORMANCE.md`.
