<!-- SeekR README | Keep release details and feature claims aligned with the shipped application. -->

<div align="center">

<img src="assets/icons/seekr.png" alt="SeekR app icon" width="112" height="112">

# SeekR

### Find it. Launch it. Get things done.

A fast, keyboard-first launcher for Windows — with a dropdown that slides down from the top of your screen.

<br>

[![Latest release](https://img.shields.io/github/v/release/okyanus-11/SeekR?display_name=tag&style=for-the-badge&color=7c83ff)](https://github.com/okyanus-11/SeekR/releases/latest)
[![License](https://img.shields.io/github/license/okyanus-11/SeekR?style=for-the-badge)](LICENSE)
[![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-357ec7?style=for-the-badge&logo=windows&logoColor=white)](#requirements)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab?style=for-the-badge&logo=python&logoColor=white)](#development)

<br>

<a href="https://github.com/okyanus-11/SeekR/releases/download/v2.0.2/SeekR-Setup-2.0.2.exe">
  <img src="https://img.shields.io/badge/⬇%20Download%20SeekR-2.0.2-6c63ff?style=for-the-badge&logo=windows&logoColor=white" alt="Download SeekR 2.0.2">
</a>

<br>
<sub><a href="https://github.com/okyanus-11/SeekR/releases/tag/v2.0.2">Release notes</a> · <a href="https://github.com/okyanus-11/SeekR/releases">All releases</a> · <a href="https://github.com/okyanus-11/SeekR/releases/download/v2.0.2/SeekR.exe">Portable version</a> · <a href="https://github.com/okyanus-11/SeekR/releases/download/v2.0.2/SHA256SUMS.txt">SHA-256 checksums</a></sub>

<br><br>

<kbd>Alt</kbd> + <kbd>Space</kbd> &nbsp; → &nbsp; Type anything &nbsp; → &nbsp; <kbd>Enter</kbd>

</div>

---

## ✦ Meet your new starting point

SeekR brings app and file search, calculations, web shortcuts, system actions, and everyday productivity tools into one focused place.

No maze of menus. No need to reach for the mouse. Just open, type, and go.

| **01 — Launch** | **02 — Search** | **03 — Do** |
|:---:|:---:|:---:|
| A top-anchored dropdown that gets out of your way. | Find apps, files, folders, and information. | Run commands, use tools, and manage your workflow. |

## What's inside?

<table>
<tr>
<td width="50%" valign="top">

### ⚡ A smarter launcher
- Top-edge dropdown with slide-down / slide-up motion
- Fuzzy matching and typo tolerance
- Recent and frequent result ranking
- Configurable global hotkey
- Keyboard-first navigation

</td>
<td width="50%" valign="top">

### 🔎 Search that gets it
- Start Menu apps and configured folders
- Indexed files and folders
- Optional text-file content search
- Calculator expressions
- Web, Wikipedia, YouTube, and GitHub
- Browser bookmarks

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 🧰 Everyday tools
- Calculator, dictionary, and translation
- Unit and time conversion
- Color, JSON, Base64, URL, regex, and hash tools
- Screenshots and system information
- UUID and text utilities

</td>
<td width="50%" valign="top">

### 🚀 Get things done
- Notes, tasks, bookmarks, and snippets
- Local workflows and command chains
- Clipboard history (opt-in)
- Process inspection and window controls
- SSH profiles and database backups

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 🎛 Make it yours
- Six themes: Graphite, Light, AMOLED, Catppuccin Mocha, Dracula, Nord
- Accent colors, typography, and layout controls
- Adjustable widget layout and refresh
- Animation preferences

</td>
<td width="50%" valign="top">

### 🐈 Useful at a glance
- Clock and system usage
- Configurable weather card
- Daily cat photo displayed inside SeekR
- Windows media-session controls (where supported)
- Local task summary

</td>
</tr>
</table>

## The dropdown experience

SeekR doesn't pop up in the middle of your desktop. It drops down from the top edge of your active screen, stays close at hand, and retracts when you're done.

The launcher is horizontally centered on the active display. Its search field is ready for input, while optional widgets provide quick information without taking over your workspace.

### Built-in widgets

| Widget | What it shows |
|---|---|
| **Clock** | Your local time |
| **System** | CPU and memory usage |
| **Weather** | Current conditions for a configured city |
| **Daily cat** | A real cat photo, displayed in the launcher and cached locally |
| **Media** | Windows media-session details and playback controls, where supported |
| **Task summary** | A compact view of your local tasks |

Widgets can be enabled individually. Their refresh intervals, rail width, card height, and left/right ordering are configurable. Network-backed widgets retain their last successful content when a refresh fails.

<sub>Weather data is provided by Open-Meteo. Daily cat photos are provided by TheCatAPI. Fresh network content requires an internet connection; cached content remains available offline.</sub>

## Search without the ceremony

SeekR understands regular queries and optional keyword prefixes. A few examples:

| Type | Example | What happens |
|---|---|---|
| Apps | `discord` | Find and launch an application |
| Files | `file: invoice` | Search indexed files |
| Content | `content: setup guide` | Search configured text-file contents |
| Calculator | `calc: sqrt(144) + 25 * 4` | Evaluate an expression |
| Web | `web: Raspberry Pi 5` | Search the configured web engine |
| Wikipedia | `wiki: ESP32` | Search Wikipedia |
| YouTube | `yt: DOOM soundtrack` | Search YouTube |
| GitHub | `gh: embedded projects` | Search GitHub |
| Dictionary | `define: algorithm` | Look up a definition |
| Translation | `translate: Hello to Turkish` | Open a translation |
| Units | `unit: 100 km to miles` | Convert units |
| Local time | `time: Tokyo` | Look up a location's time |
| System | `sys:` | Show system information |
| Commands | `comm: ipconfig` | Run a built-in command |
| Workflows | `flow: prepare work` | Find and run a workflow |
| Snippets | `snip: signature` | Find saved text |
| Command chains | `chain: taskmgr then explorer` | Run a sequence of commands |
| Tasks | `task: installer` | Search local tasks |
| Window management | `wm: minimize all` | Manage application windows |
| Updates | `update: check` | Check the official releases page |

Keywords are case-insensitive and matched at the start of the query. Without a prefix, SeekR can still recognize calculator expressions and rank matching applications and files.

## Keyboard controls

| Shortcut | Action |
|---|---|
| `Alt + Space` | Show or hide SeekR (default global hotkey) |
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

If another application already uses `Alt + Space`, change the shortcut in **Settings → General**.

## Quick start

### 1. Download

<a href="https://github.com/okyanus-11/SeekR/releases/download/v2.0.2/SeekR-Setup-2.0.2.exe"><strong>Download the Windows installer</strong></a> or grab the <a href="https://github.com/okyanus-11/SeekR/releases/download/v2.0.2/SeekR.exe">portable executable</a>.

The installer works per-user, does not require administrator privileges or a separate Python installation, and creates a Start Menu shortcut.

### 2. Open

Launch SeekR and press <kbd>Alt</kbd> + <kbd>Space</kbd>.

### 3. Find something

Try `discord`, `calc: 42 * 42`, or `file: project`. Press <kbd>Enter</kbd> to run the selected result.

Need the detailed steps? See the [installation and upgrade guide](docs/INSTALLATION.md).

## Personalization & languages

Choose a theme, adjust the accent color, transparency, font family and size, launcher width, result spacing, widget layout, and animation behavior.

The launcher shell and shared navigation are available in nine languages:

**English · Turkish · Spanish · French · German · Italian · Brazilian Portuguese · Japanese · Simplified Chinese**

> Localization is partial. Some longer descriptions, tool content, dialogs, and dynamic messages remain in English.

## Privacy by design

SeekR is designed to keep its working data on your device. Configuration, database, logs, notes, and optional clipboard history are stored locally.

- **Clipboard monitoring is off by default** and requires opt-in.
- Clipboard text and optional PNG captures are stored locally **without encryption**.
- Turning monitoring off stops future capture; clear saved history separately.
- Sensitive-content detection is heuristic and cannot guarantee that every secret is caught.
- Application usage ranking and file-content search are opt-in.
- Diagnostics reports are generated only when requested and are not uploaded by SeekR.
- Diagnostics logs are excluded by default. Redaction is best-effort; review a report before sharing it.

On Windows, user data lives under `%APPDATA%\\SeekR`. Uninstalling SeekR preserves this data. Backups contain the same local information, so keep them private.

Read [Installation & data locations](docs/INSTALLATION.md) before enabling optional data-collection features.

## Requirements

| | |
|---|---|
| **Operating system** | 64-bit Windows 10 or Windows 11 |
| **For users** | Use the installer or portable executable; Python is not required |
| **For development** | Python 3.10+ (Python 3.12 recommended) |
| **Core technologies** | Python, PySide6, SymPy, psutil, SQLite |

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

Run tests:

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

More detail: [Architecture](docs/ARCHITECTURE.md) · [Troubleshooting](docs/TROUBLESHOOTING.md) · [Performance notes](docs/PERFORMANCE.md).

## Quality & release validation

The **v2.0.2 release pipeline completed successfully**:

- Ubuntu test suite — passed
- Windows Latest test suite — passed
- Windows Server 2022 test suite — passed
- Portable executable build and packaged launcher UI verification — passed
- Windows installer build — passed
- Fresh installation, launch verification, and uninstallation — passed
- SHA-256 checksum generation and release publication — passed

Automated checks do not replace real-desktop testing. Physical Windows 10/11 validation is still needed for mixed-DPI and multi-monitor behavior, sleep/resume, upgrades from older versions with user-data preservation, long-duration stability, and accessibility review.

Useful engineering references: [Windows audit](docs/WINDOWS_AUDIT.md) · [Manual test checklist](docs/WINDOWS_MANUAL_TEST.md) · [Performance methodology](docs/PERFORMANCE.md) · [Windows performance notes](docs/WINDOWS_PERFORMANCE.md) · [Changelog](CHANGELOG.md).

## Known limitations

- Full manual validation on physical Windows 10/11 desktops is still outstanding.
- Windows executables are unsigned and may trigger a SmartScreen unfamiliar-app warning.
- Localization covers the launcher shell and shared navigation, not every screen or message.
- GPU utilization depends on counters exposed by the installed driver and Windows configuration.
- First-time dictionary lookups need an internet connection; successful lookups are cached.
- Browser bookmarks may be skipped if profiles are unavailable, corrupt, or blocked by permissions.
- SSH requires the Windows OpenSSH Client; SeekR does not store SSH passwords.
- Screenshot capture and mixed-DPI positioning need additional real-display verification.

See the [Windows audit](docs/WINDOWS_AUDIT.md) for the detailed evidence and limitations.

## Roadmap

| Version | Focus |
|---|---|
| **2.0.2** · Released | Top-anchored dropdown launcher and in-launcher daily cat photo |
| **2.0.3** · Planned | Search improvements, widget customization, and bug fixes |
| **2.1.0** | System Monitor, Clipboard History, and Focus Timer |
| **2.2.0** | Smarter search and personalization |
| **2.3.0** | Automation |
| **3.0.0** | Plugin ecosystem |

Third-party plugins, plugin execution, marketplace installation, plugin permissions, and the public plugin SDK are not included in 2.0.2; they are planned for 3.0.0.

## Contributing

Found a bug or have an idea? Check the [existing issues](https://github.com/okyanus-11/SeekR/issues) before opening a new one. Reproduction steps and environment details are especially helpful. Please do not attach passwords, private clipboard contents, or personal notes.

## License

SeekR is open source under the [MIT License](LICENSE).

Copyright © 2026 Okyanus Bora Şevik.

---

<div align="center">

### Less searching. More doing.

<sub>Made with Python, PySide6, SymPy, psutil, and SQLite.</sub>

<br>

<a href="https://github.com/okyanus-11/SeekR/releases/latest">Get SeekR</a> · <a href="https://github.com/okyanus-11/SeekR/issues">Report an issue</a> · <a href="CHANGELOG.md">Changelog</a>

</div>
