<div align="center">

<img src="assets/readme/hero.svg" alt="SeekR — Find it. Launch it. Get things done." width="100%">

<br>

[![Latest release](https://img.shields.io/github/v/release/okyanus-11/SeekR?display_name=tag&style=for-the-badge&color=8b5cf6)](https://github.com/okyanus-11/SeekR/releases/latest)
[![License](https://img.shields.io/github/license/okyanus-11/SeekR?style=for-the-badge)](LICENSE)
[![Platform](https://img.shields.io/badge/Windows-10%20%7C%2011-357ec7?style=for-the-badge&logo=windows&logoColor=white)](#requirements)
[![Built with Python](https://img.shields.io/badge/Python-3.10%2B-3776ab?style=for-the-badge&logo=python&logoColor=white)](#development)

<br>

<a href="https://github.com/okyanus-11/SeekR/releases/latest"><img src="https://img.shields.io/badge/⬇%20GET%20SEEKR-Latest%20Release-8b5cf6?style=for-the-badge&logo=windows&logoColor=white" alt="Download the latest SeekR release"></a>

<br>
<sub><a href="https://github.com/okyanus-11/SeekR/releases">All releases</a> · <a href="CHANGELOG.md">Changelog</a> · <a href="docs/INSTALLATION.md">Installation guide</a> · <a href="https://github.com/okyanus-11/SeekR/issues">Report a bug</a></sub>

<br><br>

<kbd>Alt</kbd> + <kbd>Space</kbd> &nbsp; → &nbsp; Search &nbsp; → &nbsp; <kbd>Enter</kbd>

</div>

---

## A better way to get things done.

SeekR is a keyboard-first Windows launcher that puts your apps, files, commands, and everyday tools one shortcut away.

It opens as a **dropdown from the top of your screen**. Type what you need, pick a result, and get straight back to what you were doing.

| ⚡ **Launch** | 🔎 **Find** | 🧰 **Do** |
|:---:|:---:|:---:|
| Open apps and tools in seconds. | Search files, folders, and the web. | Calculate, automate, organize, and control. |

## Why SeekR?

<table>
<tr>
<td width="50%" valign="top">

### ⚡ A launcher that stays out of your way
- Top-anchored dropdown with slide animations
- Global hotkey — `Alt + Space` by default
- Fuzzy matching and typo tolerance
- Recent and frequent result ranking
- Keyboard-first navigation

</td>
<td width="50%" valign="top">

### 🔍 Search beyond your apps
- Start Menu apps and configured folders
- Indexed files and folders
- Optional local text-content search
- Calculator expressions
- Web, Wikipedia, YouTube, and GitHub
- Supported browser bookmarks

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 🧰 A toolkit built in
- Calculator, dictionary, and translation
- Unit and local-time conversion
- JSON, Base64, URL, regex, hash, and color tools
- Screenshots and system information
- Process inspection and window controls

</td>
<td width="50%" valign="top">

### 🚀 Your own workflow
- Notes, tasks, bookmarks, and text snippets
- Multi-step local workflows
- Command chains with failure handling
- SSH profiles using Windows OpenSSH
- SQLite backup and restore

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 🎨 Make it yours
- Graphite, Light, AMOLED, Catppuccin Mocha, Dracula, and Nord
- Accent colors, transparency, and typography
- Adjustable launcher and widget layout
- Configurable refresh and animation behavior

</td>
<td width="50%" valign="top">

### 🐈 Useful at a glance
- Clock and CPU / memory cards
- Weather for a configured location
- Daily cat photo displayed inside the launcher
- Windows media-session controls (where supported)
- Local task summary

</td>
</tr>
</table>

## The dropdown

No centered pop-up interrupting your screen. SeekR slides down from the top edge of the active display and retracts when dismissed. The search field is ready immediately, with optional widget cards alongside your results.

### Optional widgets

| Widget | Details |
|---|---|
| **Clock** | Local time, updated on-device |
| **System** | CPU and memory usage |
| **Weather** | Current conditions for a configured city |
| **Daily cat** | A cat photo shown inside SeekR and cached locally |
| **Media** | Current Windows media session and playback controls, where supported |
| **Task summary** | A compact view of your local tasks |

Each widget can be enabled individually. Card dimensions, refresh intervals, and left/right ordering are configurable. Network-backed widgets retain their last successful content when a refresh fails.

<sub>Weather data comes from Open-Meteo. Daily cat photos come from TheCatAPI. Fresh network content requires an internet connection; cached content can remain available offline.</sub>

## Search examples

Type a normal query or use a keyword prefix:

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

Keywords are case-insensitive. Without a prefix, SeekR can still recognize calculator expressions and rank matching applications and files.

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
2. Download `SeekR-Setup-<version>.exe` for a per-user installation, or `SeekR.exe` for the portable version.
3. Launch SeekR and press **Alt + Space**.
4. Search for an app, try `calc: 42 * 42`, or explore the built-in tools.

The installer does not require administrator privileges or a separate Python installation. It creates a Start Menu shortcut. Uninstalling removes the app but preserves your local SeekR data.

**Need help?** See the [installation and upgrade guide](docs/INSTALLATION.md) or [troubleshooting notes](docs/TROUBLESHOOTING.md).

## Privacy & local data

SeekR keeps its working data on your device. Configuration, database, logs, notes, and optional clipboard history are stored locally.

- Clipboard monitoring is **off by default** and requires opt-in.
- Clipboard text and optional PNG captures are stored locally **without encryption**.
- Turning monitoring off stops future capture; clear saved history separately.
- Sensitive-content detection is heuristic, not a guarantee that every secret will be caught.
- Application usage ranking and file-content search are opt-in.
- Diagnostics reports are generated only when requested and are not uploaded. Logs are excluded by default; redaction is best-effort.

On Windows, user data lives under `%APPDATA%\\SeekR`. Uninstalling the application preserves this folder. Keep backups private.

## Requirements

| | |
|---|---|
| **Supported OS** | 64-bit Windows 10 / Windows 11 |
| **End-user setup** | Installer or portable executable; Python not required |
| **Development** | Python 3.10+ (Python 3.12 recommended) |
| **Core stack** | Python · PySide6 · SymPy · psutil · SQLite |

Linux is used in CI and supports source-mode development and testing. macOS is not currently supported or tested.

## Development

```powershell
git clone https://github.com/okyanus-11/SeekR.git
cd SeekR
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python main.py
```

Run the test suite:

```bash
pytest
```

For headless Linux:

```bash
QT_QPA_PLATFORM=offscreen pytest
```

Build a Windows executable:

```powershell
python build.py
```

For the codebase design, see [Architecture](docs/ARCHITECTURE.md). For packaging, see [Installation](docs/INSTALLATION.md).

## Release quality & transparency

**Latest release: v2.0.2**

The v2.0.2 GitHub Actions release pipeline completed successfully:

- Ubuntu, Windows Latest, and Windows Server 2022 test suites passed.
- Portable and onedir Windows builds completed.
- Packaged launcher UI verification passed.
- Inno Setup installer compiled successfully with corrected 2.0.2 product metadata and upgrade-directory handling.
- Fresh installation, Windows Installed apps version/path registration, Start Menu shortcut target, installed-app launch, UI verification, and uninstallation passed.
- SHA-256 checksums were generated and release assets published.

The installer smoke test now checks more than whether setup exits successfully: it verifies the registered version, install location, and shortcut target. Automated checks do **not** replace physical Windows testing. Mixed-DPI and multi-monitor behavior, sleep/resume, a real upgrade from 1.x with user-data preservation, long-duration stability, and accessibility review still need hands-on verification. Windows executables are unsigned and may trigger a SmartScreen warning.

See the [Windows audit](docs/WINDOWS_AUDIT.md) and [manual test checklist](docs/WINDOWS_MANUAL_TEST.md) for evidence and remaining checks.

## Roadmap

| Version | Planned focus |
|---|---|
| **2.0.2** · Released | Top dropdown launcher |
| **2.0.3** · Planned | Search improvements, widget customization, bug fixes |
| **2.1.0** | System Monitor, Clipboard History, Focus Timer |
| **2.2.0** | Smarter search and personalization |
| **2.3.0** | Automation |
| **3.0.0** | Plugin ecosystem |

Third-party plugins, plugin execution, marketplace installation, permissions, and the public plugin SDK are not included in 2.0.2.

## Localization

The launcher shell and shared navigation are available in nine languages: English, Turkish, Spanish, French, German, Italian, Brazilian Portuguese, Japanese, and Simplified Chinese.

Localization is partial; some longer descriptions, tool content, dialogs, and dynamic messages remain in English.

## Contributing

Bug reports and thoughtful suggestions are welcome. Check the [existing issues](https://github.com/okyanus-11/SeekR/issues) before opening a new one. Include reproduction steps and environment details, but never attach passwords, private clipboard contents, or personal notes.

## License

SeekR is released under the [MIT License](LICENSE).

<div align="center">

---

**Less searching. More doing.**

<sub>Made with Python, PySide6, SymPy, psutil, and SQLite.</sub>

<br>

<a href="https://github.com/okyanus-11/SeekR/releases/latest">Download SeekR</a> · <a href="https://github.com/okyanus-11/SeekR/issues">Report an issue</a> · <a href="CHANGELOG.md">Changelog</a>

</div>
