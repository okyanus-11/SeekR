# SeekR — Windows manual GUI test checklist

Use this checklist **on a real Windows 10 or Windows 11 PC** after
`tools\windows_test.ps1` has reported PASS. Automated tests cannot verify
hotkeys, the Windows shell, tray behaviour, DPI, or how the app actually looks
and feels.

Record the result of every row. Mark a test **PASS** only after performing it.
Use **FAIL** with a short note, or **N/A** with the reason (for example, no
second monitor). Do not edit the application or its configuration just to make
a test pass.

## Test environment

Record this before starting:

| Field | Value |
|---|---|
| Windows edition and build (`winver`) | |
| CPU / RAM | |
| Display resolution and scaling (100%, 125%, 150%, 200%) | |
| Number of monitors | |
| Python version (`py -3 --version`) | |
| SeekR executable path and SHA-256 | |
| Git commit / build date | |
| Tester and date | |

## Before testing

1. Run the automated checks:
   `powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\windows_test.ps1`
2. Confirm `windows_test_results.txt` says `RESULT: PASS`.
3. Close any existing SeekR process, including one in the notification area.
4. Note whether this is a fresh profile or an existing SeekR install.
   If you need a clean profile, back up `%APPDATA%\SeekR` first. Do not delete
   a profile containing data you need.
5. Start `dist\SeekR.exe` by double-clicking it.

## Results

Use the **Result** and **Notes** columns in the tables below.

### Installation, upgrade and uninstall

Run these on a clean Windows profile before the GUI checks. Tests I04–I06 cover
the older-version upgrade that has not been validated yet; skip I04 only if no
earlier SeekR build is available and record it as N/A.

| ID | Test | Steps | Expected | Result | Notes |
|---|---|---|---|---|---|
| I01 | Fresh install | Run `SeekR-Setup-<version>.exe` as a normal user (no administrator elevation). | Installs under `%LOCALAPPDATA%\Programs\SeekR`; Start Menu shortcut and an entry in Settings → Apps appear; no UAC prompt. | | |
| I02 | Launch installed app | Start SeekR from the Start Menu shortcut. | Launcher appears with no console window; shortcut target is the installed `SeekR.exe`. | | |
| I03 | Same-version reinstall | Run the same installer again while SeekR is closed. | Completes without error; settings, notes and history are preserved. | | |
| I04 | Older-version upgrade | Install the previous SeekR build, create data (a note, a clipboard entry with history enabled, a changed hotkey/theme), then run the new installer. | Upgrade completes; binaries and shortcuts are replaced; settings, notes and history are preserved; no duplicate Start Menu or uninstall entries; version in Explorer → Properties → Details matches the new build. | | |
| I05 | Uninstall preserves data | Uninstall from Settings → Apps. | Binaries, shortcuts and uninstall entry are removed; `%APPDATA%\SeekR` still contains the configuration and database. | | |
| I06 | Reinstall after uninstall | Reinstall and launch. | Previous settings, notes and history load; nothing is duplicated or lost. | | |
| I07 | Signing and SmartScreen | Check the downloaded installer and executable in Explorer → Properties → Digital Signatures, and record any SmartScreen prompt on first run. | Result is recorded honestly. These builds are expected to be **unsigned** until a certificate exists; do not describe them as signed or reputation-verified. | | |

### Launcher and hotkey

| ID | Test | Steps | Expected | Result | Notes |
|---|---|---|---|---|---|
| L01 | First launch | Double-click `dist\SeekR.exe`. | Launcher appears centred on the active monitor, search box focused, no console window. | | |
| L02 | Alt+Space opens | Press `Alt+Space` while another app has focus. | SeekR comes to the foreground with the search box focused. | | |
| L03 | Alt+Space hides | Press `Alt+Space` again. | Launcher hides; the previous app remains usable. | | |
| L04 | Escape | Open SeekR, type a query, press `Esc`. | Selection/action clears; a second `Esc` hides the launcher. | | |
| L05 | Click outside | Open SeekR and click another application. | Launcher hides when “Hide when focus is lost” is enabled; it does not hide while a SeekR dialog is open. | | |
| L06 | Single instance | With SeekR running, launch `dist\SeekR.exe` again. | No second process/window; the existing launcher comes forward. | | |
| L07 | Hotkey conflict | Start another app that owns `Alt+Space` (or set SeekR's hotkey to a combination another app owns). | Settings shows a clear registration error; SeekR does not silently claim success. Change the hotkey and verify it works. | | |
| L08 | Custom hotkey | Settings → General: set a new combination, apply, close Settings, then use it. | New combination opens SeekR; old one no longer does. | | |
| L09 | Focus after dialog | Open a confirmation dialog, cancel it, return to SeekR. | Launcher remains visible and accepts keyboard input. | | |
| L10 | DPI and monitors | Repeat L01–L03 on each monitor and at 100%, 125%, 150% and 200% scaling if available. | Window is readable, fully on-screen, not clipped, and appears where expected. | | |
| L11 | Repeated activation | With SeekR running and hidden, launch `dist\SeekR.exe` five times in a row, waiting about a second between launches. Repeat with SeekR visible and focused. | Every launch exits immediately and the existing launcher appears in front with the search box focused. Never two windows, never a silent no-op, never a window that flashes and disappears. | | |
| L12 | Activation from different sources | Raise the launcher once each via `Alt+Space`, the tray **Open SeekR** action, and a second executable launch, after giving another application focus in between. | All three bring the window forward and focus the search box. | | |

### Application discovery and launching

| ID | Test | Steps | Expected | Result | Notes |
|---|---|---|---|---|---|
| A01 | Start Menu discovery | Open Settings → Applications, click **Refresh index**; wait for completion. | Installed Start Menu applications appear; no crash on unreadable shortcuts. | | |
| A02 | Launch an app | Search for a normal installed app and press `Enter`. | The app launches and SeekR hides. | | |
| A03 | Path with spaces | Search for an app installed under `C:\Program Files\...` and launch it. | Launches correctly; no “file not found” caused by quoting. | | |
| A04 | Shortcut with arguments | Use a `.lnk` or configured application that supplies arguments (or Quick Actions). | Arguments reach the target intact; quoted values are not mangled. | | |
| A05 | Additional folder | Settings → Applications → **Additional application folders**: add a folder containing a `.lnk` or `.exe`; refresh. | Items are found and launch; removing the folder removes them on refresh. | | |
| A06 | Exclusions | Exclude an application in Settings → Applications; search again. | Excluded application no longer appears. | | |
| A07 | Icons | Inspect application results. | Real icons appear where Windows provides them; fallback glyphs appear instead of broken images. | | |
| A08 | Context menu | Right-click an application result. | Actions are present and work (launch, open location, copy path where offered). | | |

### File search and indexing

| ID | Test | Steps | Expected | Result | Notes |
|---|---|---|---|---|---|
| F01 | Add folder | Settings → Files: add a test folder containing a few files; click **Index now**. | Folder indexes without freezing the UI; progress/status is visible. | | |
| F02 | File search | Search `file:` plus part of a filename. | Matching files/folders appear; opening one works. | | |
| F03 | Unicode filename | Add a file named with Turkish/non-Latin characters and search for it. | File is found and opens. | | |
| F04 | Spaces/special characters | Index and open a path containing spaces, `&`, parentheses or `#`. | Search, preview and open work; no shell-quoting failure. | | |
| F05 | Permission errors | Index a folder containing a protected/unreadable subfolder. | Other files still index; the UI does not crash or report a false success. | | |
| F06 | Hidden files | Toggle **Include hidden files** and re-index. | Hidden/system entries appear only when enabled. | | |
| F07 | Exclusions | Add an excluded folder/extension and re-index. | Excluded entries do not appear. | | |
| F08 | Limit | Index a very large tree (or set a low entry limit in a disposable test profile). | Status reports the entry limit clearly; it is not described as a cancellation. | | |
| F09 | Responsiveness | Search while indexing runs. | Launcher remains responsive; searches return or show progress without freezing. | | |
| F10 | QuickLook | Preview a text file and an image from file results. | Text/image previews render; unsupported types show a clear message rather than executing. | | |
| F11 | Reveal in Explorer | Use the open-location action for a file. | Explorer opens with the file selected (or its folder open). | | |

### Core search providers

| ID | Test | Steps | Expected | Result | Notes |
|---|---|---|---|---|---|
| C01 | Calculator | Type `calc: sqrt(144) + 25 * 4` and `25 * 48`. | Results show `112` and `1200`; `Enter` copies the value. | | |
| C02 | Calculator errors | Type `calc: 1 / 0` or invalid syntax. | Clear error result; no crash. | | |
| C03 | Unit conversion | Type `unit: 100 km to miles`. | A sensible converted result appears. | | |
| C04 | Web search | Type `web: python packaging` and run it. | The configured browser opens the correct search URL. | | |
| C05 | Keyword searches | Try `wiki:`, `yt:`, `gh:` and `translate:`. | Each opens the expected website or generates its URL. | | |
| C06 | Empty-query suggestions | Open SeekR with an empty box. | Recent apps/files/search suggestions appear (unless disabled). | | |

### Commands and confirmation

| ID | Test | Steps | Expected | Result | Notes |
|---|---|---|---|---|---|
| X01 | Safe command | Run `comm: ipconfig` (or another built-in safe command). | Output appears in the result/preview; no console window flashes. | | |
| X02 | Destructive command | Run a command marked destructive, for example a Recycle Bin action. | A confirmation dialog appears; Cancel performs nothing. | | |
| X03 | Global confirmation setting | Disable destructive confirmation in Settings → General, then retry X02. | Confirmation is skipped only when the setting is disabled; re-enable it afterwards. | | |
| X04 | Custom command with quotes | Create a custom command whose arguments include a quoted value with spaces. | Arguments are passed exactly, without literal quote characters. | | |
| X05 | Missing executable | Create/run a custom command pointing to a missing executable. | Clear error message; SeekR remains running. | | |

### Clipboard and notes

| ID | Test | Steps | Expected | Result | Notes |
|---|---|---|---|---|---|
| B01 | Clipboard capture | Enable clipboard history, copy several text snippets in another app, open SeekR and search for them. | Copied entries appear and can be pasted/reused. | | |
| B02 | Clipboard controls | Pin, delete and clear entries. | Each action works and survives a restart. | | |
| B03 | Notes autosave | Create a note, type text, wait for autosave, close SeekR. | Note is saved. | | |
| B04 | Notes persistence | Restart SeekR and open Tools → Quick notes. | Note and its text are still present. | | |
| B05 | Notes search | Search for note text from the launcher. | Matching notes appear. | | |

### Settings, themes and tools

| ID | Test | Steps | Expected | Result | Notes |
|---|---|---|---|---|---|
| S01 | Settings pages | Open Settings and visit every page: General, Appearance, Widgets, Search, Applications, Files, Web, Calculator, Commands, Clipboard, Privacy, Advanced, Plugins, About. | Every page renders without errors; Plugins clearly says Coming Soon with no fake install action. | | |
| S02 | Persistence | Change a visible setting (for example result count or font size), close and restart SeekR. | Setting is preserved. | | |
| S03 | Hotkey settings | Change the hotkey and restart. | New hotkey persists and registers. | | |
| S04 | Screenshot folder, full-screen and region capture | Settings → Files → Screenshots: choose a folder, capture the full desktop, then use Capture region and drag a selection across one display. Repeat with all connected displays at mixed scaling if available. | Both full-screen and region captures save PNGs directly in the configured folder. Check clipping, scaling, selection coordinates and monitor offsets. The Snipping Tool is an optional external alternative. | | |
| S05 | Theme: Dark | Settings → Appearance: select Dark. | Launcher, Settings and Tools use the dark theme immediately. | | |
| S06 | Theme: Light | Select Light. | All open windows repaint light; text remains readable. | | |
| S07 | Theme: AMOLED | Select AMOLED. | True-black surfaces; readable contrast. | | |
| S08 | Theme: Catppuccin Mocha | Select Catppuccin Mocha. | Theme applies consistently. | | |
| S09 | Theme: Dracula | Select Dracula. | Theme applies consistently. | | |
| S10 | Theme: Nord | Select Nord. | Theme applies consistently. | | |
| S11 | Accent and transparency | Change accent, transparency, font family/size, width and animation toggle. | Changes apply live, remain readable, and persist after restart. | | |
| S12 | Tools pages | Open Tools and visit all 14 pages: Calculator, Developer tools, Date & time, Color, Dictionary, Screenshots, System, Processes, Power, Clipboard, Quick notes, Bookmarks, Quick Connect, Quick actions. | Every page opens and its visible controls respond; unavailable data says so instead of inventing values. | | |
| S13 | Developer tools | Exercise a few utilities: UUID, Base64 encode/decode, JSON format/validate, hash, regex, timestamp, case/count/hex. | Results are correct; invalid input produces a clear error. | | |
| S14 | System information | Open Tools → System. | CPU, memory, disks, OS and other available values populate without freezing the UI; GPU shows driver utilisation where GPU Engine counters or vendor telemetry are available, or an honest unavailable state. | | |
| S15 | Processes | Search processes and open details. Try terminating a harmless test process and a protected system process. | Harmless process can be terminated after confirmation; critical/system process is refused with an explanation. | | |
| S16 | Power | Open Tools → Power and switch a power scheme (if available). | Schemes list; switching succeeds or shows the exact `powercfg` error. | | |
| S17 | Window switching | Type `win:` and switch to another window. | Window list is real; switching works or explains why Windows blocked it. | | |
| S18 | Bookmarks | Open Tools → Bookmarks with at least one browser profile available. | Readable bookmarks appear; locked/unreadable profiles are skipped with a message. | | |
| S19 | Quick Connect | Add/validate an SSH profile; never enter a password into SeekR. | Profile validation and launch behaviour are clear; no password is stored. | | |
| S20 | Quick actions | Create one quick action for a folder, one website and one application with arguments; run each. | Each action performs exactly what it says. | | |
| S21 | Default widget layout | Reset settings to defaults, open the launcher and inspect both sides of the results list. | Clock and System usage appear in the left rail; Weather and Daily meme appear in the right rail. All four cards have visible content and do not cover the search results. | | |
| S22 | Widget toggles | Settings → Widgets: disable and re-enable each card individually. | Only the selected card hides/shows; the remaining cards stay visible and the rails collapse when both cards on a side are disabled. | | |
| S23 | Widget persistence | Change the four widget toggles, close and restart SeekR. | Each enabled/disabled choice persists and the layout matches the saved settings. | | |
| S24 | Weather lookup | Set a valid city, wait for the lookup, then try an invalid city. | Valid conditions and the Open-Meteo attribution appear; invalid locations show an honest unavailable message without hiding the card or freezing the launcher. | | |
| S25 | Weather offline | Disconnect the network with Weather enabled, then reopen the launcher. | The Weather card remains visible and reports unavailable; the clock and system usage continue updating. | | |
| S26 | Daily meme | Open the launcher online, then test with network unavailable and after restarting on the same day. | Meme title/preview/link appear when the service responds; failures leave the card visible with an unavailable state; a valid daily result is cached. | | |

### Tray, startup and shutdown

| ID | Test | Steps | Expected | Result | Notes |
|---|---|---|---|---|---|
| T01 | Tray icon | Enable Settings → General → Show tray icon. | Exactly one SeekR icon appears in the notification area. | | |
| T02 | Tray menu | Right-click the tray icon. | Menu includes Open SeekR, Settings, Tools, Re-index, Quit; all work. | | |
| T03 | Tray show/hide | Use the tray icon to show and hide SeekR. | No duplicate windows or icons; launcher focuses correctly. | | |
| T04 | Tray quit | Choose Quit from the tray menu. | Process exits; icon disappears; no orphaned SeekR process. | | |
| T05 | Startup enable | Settings → General → Start with Windows: enable it. Sign out and back in (or reboot). | SeekR starts at login as configured; no console window. | | |
| T06 | Startup disable | Disable the setting, sign out/in. | SeekR does not start automatically. | | |
| T07 | Startup path | With startup enabled, move the executable and rerun it; toggle the setting off/on. | Registry entry points to the current executable; stale path is corrected after toggling. | | |
| T08 | Notifications | Trigger a background completion or error notification with the tray enabled. | A native notification/balloon appears and does not crash the app. | | |
| T09 | Clean close | Close SeekR from its tray/menu path. | No error dialog, no lingering process, log ends cleanly. | | |
| T10 | Restart persistence | Restart SeekR. | Settings, notes, clipboard history, hotkey, theme and window preferences are preserved; no duplicate data or loss. | | |
| T11 | Second launch after restart | Launch the executable again while running. | Existing instance is activated; still only one process. | | |

### Error reporting

For every failure, record:

- Test ID and exact steps.
- Expected and actual result.
- Whether it reproduces after a restart and in a fresh Windows user profile.
- A screenshot of the window and any dialog.
- `%APPDATA%\SeekR\logs\seekr.log` (copy it before restarting if the log
  rotates).
- `windows_test_results.txt` from the automated run.
- Windows edition/build, display scaling, and SeekR executable hash.

Attach these to a GitHub issue at
<https://github.com/okyanus-11/SeekR/issues>. Do not include secrets, passwords
or private clipboard/note content.

## Sign-off

| Field | Value |
|---|---|
| Automated report result | |
| Total PASS / FAIL / N/A | |
| Blocking failures | |
| Tester signature/date | |
| Windows versions covered | |

Only after this checklist passes on the target Windows versions should the
README describe SeekR as **verified on Windows**.
