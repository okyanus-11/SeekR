<div align="center">

<img src="assets/readme/hero.svg" alt="SeekR — Find it. Launch it. Get things done." width="100%">

<br>

[![Latest release](https://img.shields.io/github/v/release/okyanus-11/SeekR?display_name=tag&style=for-the-badge&color=8b5cf6)](https://github.com/okyanus-11/SeekR/releases/latest)
[![CI](https://github.com/okyanus-11/SeekR/actions/workflows/ci.yml/badge.svg)](https://github.com/okyanus-11/SeekR/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/okyanus-11/SeekR?style=for-the-badge)](LICENSE)
[![Platform](https://img.shields.io/badge/Windows-10%20%7C%2011-357ec7?style=for-the-badge&logo=windows&logoColor=white)](#requirements)

<br>

<a href="https://github.com/okyanus-11/SeekR/releases/latest"><img src="https://img.shields.io/badge/⬇%20GET%20SEEKR-Latest%20Release-8b5cf6?style=for-the-badge&logo=windows&logoColor=white" alt="Download the latest SeekR release"></a>

<br>
<sub><a href="https://github.com/okyanus-11/SeekR/releases">All releases</a> · <a href="CHANGELOG.md">Changelog</a> · <a href="docs/INSTALLATION.md">Installation guide</a> · <a href="docs/TROUBLESHOOTING.md">Troubleshooting</a> · <a href="https://github.com/okyanus-11/SeekR/issues">Report a bug</a></sub>

<br><br>

<kbd>Alt</kbd> + <kbd>Space</kbd> &nbsp; → &nbsp; Search &nbsp; → &nbsp; <kbd>Enter</kbd>

</div>

---

## A better way to get things done

SeekR is a keyboard-first Windows launcher that puts your apps, files, commands and everyday tools one shortcut away. It drops down from the top edge of your screen, stays out of the way, and gets you back to work in a keystroke.

No start menu hunting. No window switching. Just **Alt + Space**, type, **Enter**.

| ⚡ Launch | 🔎 Find | 🧰 Do |
|:---:|:---:|:---:|
| Apps and tools in seconds | Files, folders, contents, web | Calculate, convert, automate, organize |

### Current release — v2.0.2.1

A maintenance release on top of 2.0.2 that fixes four real defects:

- **System widget no longer freezes the launcher.** Windows performance counters used to run on the GUI thread every two seconds.
- **Single-instance activation can't stall the UI.** Socket reads are non-blocking now, with a bounded per-connection buffer.
- **File-query date filters can't crash.** `today` / `yesterday` no longer hit the Windows `datetime.timestamp()` edge case.
- **Update checks understand four-part versions**, so `2.0.2.1` correctly sorts above `2.0.2`.

Full details: [release notes](docs/RELEASE_NOTES_2.0.2.1.md) · [changelog](CHANGELOG.md).

## Why SeekR?

<table>
<tr>
<td width="50%" valign="top">

### ⚡ A launcher that stays out of your way
- Top-anchored dropdown with slide animations
- Global hotkey — `Alt + Space` by default
- Fuzzy matching and typo tolerance
- Recent and frequent result ranking
- Keyboard-first, mouse-friendly

</td>
<td width="50%" valign="top">

### 🔍 Search beyond your apps
- Start Menu apps and configured folders
- Indexed files and folders
- Optional local text-content search
- Calculator expressions
- Web, Wikipedia, YouTube and GitHub
- Supported browser bookmarks

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 🧰 A toolkit built in
- Calculator, dictionary and translation
- Unit and local-time conversion
- JSON, Base64, URL, regex, hash and color tools
- Screenshots and system information
- Process inspection and window controls

</td>
<td width="50%" valign="top">

### 🚀 Your own workflow
- Notes, tasks, bookmarks and text snippets
- Multi-step local workflows
- Command chains with failure handling
- SSH profiles using Windows OpenSSH
- SQLite backup and restore

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 🎨 Make it yours
- Graphite, Light, AMOLED, Catppuccin Mocha, Dracula and Nord
- Accent colors, typography and reduced motion
- Adjustable launcher and widget layout
- Configurable refresh and animation behavior

</td>
<td width="50%" valign="top">

### 🐈 Useful at a glance
- Clock and focus timer
- CPU, memory, storage, battery and network card
- Weather for a configured location
- Daily cat photo inside the launcher
- Windows media-session controls (where supported)

</td>
</tr>
</table>

## The dropdown

No centered pop-up interrupting your screen. SeekR slides down from the top edge of the active display and retracts when dismissed. The search field is ready immediately, with optional widget cards alongside your results.

### Optional widgets

| Widget | What it shows | Notes |
|---|---|---|
| **Clock** | Local time and date, plus a focus timer | On-device only |
| **System** | CPU, memory, storage, battery, network | Collected off the UI thread in 2.0.2.1 |
| **Weather** | Current conditions for a configured city | Open-Meteo; last good data kept offline |
| **Daily cat** | A cat photo inside SeekR | TheCatAPI; cached locally |
| **Media** | Current Windows media session and controls | Where the OS exposes a session |
| **Tasks** | A compact summary of local tasks | Local SQLite data |

Each widget can be enabled individually. Card dimensions, refresh intervals and left/right ordering are configurable, and network-backed widgets keep their last successful content when a refresh fails.

## Search examples

Type a normal query, or use a keyword prefix:

| Try this | What it does |
|---|---|
| `discord` | Find an installed application |
| `file: invoice` | Search indexed files |
| `content: setup guide` | Search configured text-file contents |
| `calc: sqrt(144) + 25 * 4` | Calculate an expression |
| `web: Raspberry Pi 5` | Search the configured web engine |
| `wiki: ESP32` | Search Wikipedia |
| `yt: DOOM soundtrack` | Search YouTube |
| `gh: embedded projects` | Search GitHub |
| `define: algorithm` | Look up a definition |
| `translate: Hello to Turkish` | Open a translation |
| `unit: 100 km to miles` | Convert units |
| `time: Tokyo` | Look up local time |
| `sys:` | Show system information |
| `comm: ipconfig` | Run a built-in command |
| `flow: prepare work` | Find and run a workflow |
| `snip: signature` | Find a saved snippet |
| `chain: taskmgr then explorer` | Run a command chain |
| `task: installer` | Search local tasks |
| `wm: minimize all` | Manage application windows |
| `update: check` | Check the official releases page |

Keywords are case-insensitive. Without a prefix, SeekR still recognizes calculator expressions and ranks matching applications and files.

## Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `Alt + Space` | Show or hide SeekR |
| `↑` / `↓` | Move through results |
| `Page Up` / `Page Down` | Move six rows |
| `Enter` | Run the selected result's primary action |
| `Tab` / `Shift + Tab` | Cycle through available actions |
| `Ctrl + 1…9` | Run an action by position |
| `Ctrl + ,` | Open Settings |
| `Ctrl + T` | Open Tools |
| `Ctrl + R` | Re-index apps and files |
| `Esc` | Clear action selection, then hide |
| Right-click a result | Open its context menu |

If another application already uses `Alt + Space`, choose another shortcut in **Settings → General**.

## Get started

1. Open the **[latest SeekR release](https://github.com/okyanus-11/SeekR/releases/latest)**.
2. Download `SeekR-Setup-2.0.2.1.exe` for a per-user install, or `SeekR.exe` for the portable build.
3. Launch SeekR and press **Alt + Space**.
4. Search for an app, try `calc: 42 * 42`, or explore the built-in tools.

The installer needs neither administrator rights nor Python. It creates a Start Menu shortcut; uninstalling removes the app but **keeps your data** in `%APPDATA%\SeekR`.

**Need help?** [Installation and upgrade guide](docs/INSTALLATION.md) · [Troubleshooting](docs/TROUBLESHOOTING.md)

## Privacy & local data

SeekR keeps its working data on your device. Configuration, database, logs, notes and optional clipboard history are stored locally.

- Clipboard monitoring is **off by default** and requires opt-in.
- Clipboard text and optional PNG captures are stored locally **without encryption**.
- Turning monitoring off stops future capture; clear saved history separately.
- Sensitive-content detection is heuristic — not a guarantee every secret is caught.
- Application usage ranking and file-content search are opt-in.
- Diagnostics reports are generated only when requested and are never uploaded. Logs are excluded by default; redaction is best-effort.
- Update checks read GitHub release metadata; downloads only happen after you choose them.

User data lives under `%APPDATA%\SeekR` on Windows. Keep backups private.

## Requirements

| | |
|---|---|
| **Supported OS** | 64-bit Windows 10 / Windows 11 |
| **End-user setup** | Installer or portable executable — Python not required |
| **Development** | Python 3.10+ (3.12 recommended) |
| **Core stack** | Python · PySide6 · SymPy · psutil · SQLite |

Linux is used in CI and supports source-mode development and testing. macOS is not supported or tested.

## Development

```powershell
git clone https://github.com/okyanus-11/SeekR.git
cd SeekR
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python main.py
```

Run the suite:

```bash
pytest
```

Headless Linux:

```bash
QT_QPA_PLATFORM=offscreen pytest
```

Build a Windows executable (one-file by default, `--onedir` for the installer layout):

```powershell
python build.py
python build.py --onedir
```

Then compile the installer with Inno Setup 6:

```powershell
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" installer\seekr.iss
```

| Area | Where |
|---|---|
| Application composition, config, database, search | `core/` |
| Feature providers (apps, files, tools, workflows…) | `features/` |
| Launcher, widgets, settings, themes, i18n | `ui/` |
| Tests (330+ cases) | `tests/` |
| Windows test / performance / stability scripts | `tools/` |
| Architecture, installation, privacy, audits | `docs/` |

See [Architecture](docs/ARCHITECTURE.md) for the design and [Installation](docs/INSTALLATION.md) for packaging details.

## Release quality & verification

**Latest release: v2.0.2.1**

Each release is built and published by GitHub Actions, not from a developer machine:

- Test suites run on **Ubuntu**, **Windows Server 2022** and **Windows Latest**.
- Portable one-file and onedir Windows builds are produced and their executable metadata is checked.
- The packaged launcher UI is verified headlessly.
- The Inno Setup installer is compiled, then installed, launched, UI-verified, uninstalled and checked for leftover files.
- `SHA256SUMS.txt` is generated from the exact uploaded binaries.
- Release assets are uploaded only after the Windows build job succeeds.

Automated checks do **not** replace physical testing. Mixed-DPI and multi-monitor behavior, sleep/resume, upgrading from an older 1.x install with data preservation, long-duration sessions and accessibility review still need hands-on validation. Executables are unsigned and may trigger a SmartScreen warning.

Evidence and open checks: [Windows audit](docs/WINDOWS_AUDIT.md) · [manual test checklist](docs/WINDOWS_MANUAL_TEST.md) · [performance notes](docs/PERFORMANCE.md)

## Roadmap

| Version | Focus |
|---|---|
| **2.0.2.1** · Released | Reliability fixes: widget freeze, single-instance stalls, date filters, version parsing |
| **2.0.3** · Planned | Search improvements, widget customization, further Windows polish |
| **2.1.0** | System Monitor, Clipboard History, Focus Timer as full surfaces |
| **2.2.0** | Smarter search and personalization |
| **2.3.0** | Automation |
| **3.0.0** | Plugin ecosystem |

Third-party plugins, plugin execution, marketplace installation, permissions and the public plugin SDK are not part of any current release.

## Localization

The launcher shell and shared navigation are available in nine languages: English, Turkish, Spanish, French, German, Italian, Brazilian Portuguese, Japanese and Simplified Chinese.

Localization is partial; some longer descriptions, tool content, dialogs and dynamic messages remain in English.

## Contributing

Bug reports and thoughtful suggestions are welcome. Check the [existing issues](https://github.com/okyanus-11/SeekR/issues) before opening a new one. Include reproduction steps and environment details — but never attach passwords, private clipboard contents or personal notes.

## License

SeekR is released under the [MIT License](LICENSE).

<div align="center">

---

**Less searching. More doing.**

<sub>Made with Python, PySide6, SymPy, psutil and SQLite.</sub>

<br>

<a href="https://github.com/okyanus-11/SeekR/releases/latest">Download SeekR</a> · <a href="https://github.com/okyanus-11/SeekR/issues">Report an issue</a> · <a href="CHANGELOG.md">Changelog</a>

</div>
