<!--
  SeekR — README
  Keep this file focused on the product, its real capabilities, and the evidence
  behind each release. Detailed procedures live in /docs.
-->

<div align="center">

# SeekR

### Find it. Launch it. Get things done.

**A fast, keyboard-first desktop launcher for Windows.**

Search apps and files, calculate, run commands, manage local tasks, and reach a suite of everyday tools — from one focused, floating window.

<br>

[![Latest release](https://img.shields.io/github/v/release/okyanus-11/SeekR?display_name=tag&style=for-the-badge&color=7c83ff)](https://github.com/okyanus-11/SeekR/releases/latest)
[![License](https://img.shields.io/github/license/okyanus-11/SeekR?style=for-the-badge)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%20%2F%2011-357ec7?style=for-the-badge&logo=windows)](#requirements)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab?style=for-the-badge&logo=python&logoColor=white)](#development)

<br>

<a href="https://github.com/okyanus-11/SeekR/releases/latest"><strong>⬇ Download SeekR for Windows</strong></a>
<br>
<sub>Installer · Portable executable · SHA-256 checksums</sub>

<br><br>

<sub>Press <kbd>Alt</kbd> + <kbd>Space</kbd> · Type · Press <kbd>Enter</kbd></sub>

</div>

---

## What is SeekR?

SeekR is a keyboard-driven Windows launcher built with **Python and PySide6**. It brings application search, file discovery, calculations, web search, system actions, and productivity utilities into one lightweight workflow.

It is designed to stay out of your way: open it with a global hotkey, type naturally or use a keyword, and choose an action without navigating layers of menus.

**Current release: 2.0.0** · **License: MIT**

> **Release transparency:** 2.0.0 passed the published Ubuntu, Windows Latest, and Windows Server 2022 CI matrix, plus portable/onedir packaging and installer install/launch/uninstall smoke checks. It has **not** completed the full manual validation on physical Windows 10/11 desktops. Mixed-DPI and multi-monitor behavior, sleep/resume, a real 1.x upgrade, and long-duration stability still need hands-on verification. Builds are unsigned. See the [Windows audit](docs/WINDOWS_AUDIT.md) and [manual checklist](docs/WINDOWS_MANUAL_TEST.md).

## At a glance

| | |
|---|---|
| **Launcher** | Frameless, always-on-top search window with fuzzy matching, typo tolerance, recent/frequent ranking, and configurable global hotkey. |
| **Search** | Applications, indexed files, folders, document content (opt-in), web, Wikipedia, YouTube, GitHub, and custom search engines. |
| **Everyday tools** | Calculator, dictionary, translation, date/time, unit conversion, emoji search, color conversion, screenshots, and system information. |
| **Productivity** | Notes, tasks, bookmarks, reusable snippets, multi-step workflows, command chains, and quick actions. |
| **System controls** | Process inspection, window switching/tiling, power schemes, SSH profiles, clipboard manager, and database backups. |
| **Personalization** | Six themes, custom accents, typography and layout controls, animations, and optional launcher widgets. |

## The launcher

SeekR is more than a search box. Its launcher can show optional information cards around the results, while keeping the central search workflow uncluttered.

**Optional widgets**
- **Clock** — local time at a glance.
- **System** — CPU and memory usage.
- **Weather** — current conditions for a city you configure.
- **Daily meme** — a cached wholesome meme.
- **Media** — current Windows media-session information and playback controls, where supported.
- **Task summary** — a compact view of your local tasks.

Widgets can be enabled individually. Their refresh intervals, rail width, card height, and left/right ordering are configurable. Network-backed cards keep and label their last successful data when a refresh fails; they do not need to block the launcher.

> Weather is provided by Open-Meteo. Network widgets require an internet connection for fresh data; local widgets do not.

## Search capabilities

| Search area | Examples and capabilities |
|---|---|
| **Applications** | Find Start Menu apps and configured application folders; use aliases, exclusions, and launch history. |
| **Files & folders** | Search indexed locations, filter by extension/date/size, open or copy paths, and inspect metadata. |
| **Content search** | Search inside configured text files with `content:`. This is opt-in and applies configured extension, folder, and size limits. |
| **Calculator** | Safe SymPy-backed expressions, trigonometry, roots, logarithms, percentages, constants, unit conversion, and history. |
| **Web** | Google, Bing, DuckDuckGo, YouTube, Wikipedia, GitHub, and custom URL-template engines. |
| **Dictionary & translation** | Look up definitions (cached after a successful lookup) and open Google Translate for 20+ language names. |
| **Commands** | Built-in and user-defined commands, aliases, history, argument-safe execution, and confirmation for destructive actions. |
| **Bookmarks** | Read supported Chromium and Firefox browser bookmarks, with recovery/fallback handling. |
| **QuickLook** | Preview supported images and text-like documents without executing the files. |

## Built-in tools

The Tools window groups utilities into dedicated pages:

- **Developer tools:** UUID generation, Base64 encode/decode, JSON format/validation, URL encode/decode, hashes (MD5/SHA-1/SHA-256/SHA-512), color conversion, regex testing, timestamp conversion, text-case conversion, character/word counts, and hexadecimal conversion.
- **Files & capture:** full-screen and region screenshots, configurable save location, and file indexing controls.
- **System:** live system information, process inspection, and Windows power schemes.
- **Personal productivity:** clipboard history, quick notes, bookmarks, workflows, text snippets, tasks, and quick actions.
- **Connectivity:** SSH profiles through the system OpenSSH client.
- **Maintenance:** SQLite database backup/restore and local diagnostics report export.

The diagnostics export is user-initiated and stays on the device. Logs are excluded by default; if included, redaction is best-effort. Review a report before sharing it.

## Command Center and workflows

Press `>` to open the **Command Center**, a searchable palette for settings, tools, network actions, workflows, snippets, clipboard, search shortcuts, and widget toggles.

Build local **workflows** from validated application, folder, website, and copy actions. Workflows support preview, progress, cancellation, per-step errors, and versioned JSON import/export. **Command chains** let you sequence existing named commands with stop-on-failure behavior and confirmation for destructive steps.

## Quick start

### 1. Install

Download the latest **SeekR-Setup** installer from the [GitHub Releases page](https://github.com/okyanus-11/SeekR/releases/latest). It installs per-user, does not require administrator privileges or a separate Python installation, and creates a Start Menu shortcut.

Prefer not to install? Download the portable `SeekR.exe` from the same release.

### 2. Open

Launch SeekR and press `Alt+Space` (the default global hotkey). If another application already owns that shortcut, choose a different combination in **Settings → General**.

### 3. Search

Try a plain query such as `discord`, or use one of the keywords below.

For detailed installation, upgrade, build, and data-location instructions, see [docs/INSTALLATION.md](docs/INSTALLATION.md).

## Keyword reference

Keywords are case-insensitive and are matched at the start of the query.

| Keyword | Example | Action |
|---|---|---|
| `>` | `> workflows` | Open Command Center |
| `app:` | `app: discord` | Search applications |
| `file:` | `file: invoice` | Search indexed files |
| `content:` | `content: installation guide` | Search configured text-file contents |
| `calc:` | `calc: sqrt(144) + 25 * 4` | Calculate an expression |
| `web:` | `web: Raspberry Pi 5` | Search the configured web engine |
| `wiki:` | `wiki: ESP32` | Search Wikipedia |
| `yt:` | `yt: DOOM soundtrack` | Search YouTube |
| `gh:` | `gh: ESP32 projects` | Search GitHub |
| `translate:` | `translate: Hello to Turkish` | Open a translation |
| `define:` | `define: algorithm` | Look up a definition |
| `unit:` | `unit: 100 km to miles` | Convert units |
| `time:` | `time: Tokyo` | Look up local time |
| `sys:` | `sys:` | Show system information |
| `comm:` | `comm: ipconfig` | Run a built-in command |
| `flow:` | `flow: prepare work` | Find and run a workflow |
| `snip:` | `snip: signature` | Find a saved text snippet |
| `chain:` | `chain: taskmgr then explorer` | Run a command chain |
| `task:` | `task: installer` | Search local tasks |
| `wm:` | `wm: minimize all` | Manage application windows |
| `update:` | `update: check` | Check the official releases page |

Without a keyword, SeekR still recognizes calculator expressions and ranks matching applications and files.

## Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `Alt+Space` | Show or hide the launcher (configurable global hotkey) |
| `↑` / `↓` | Move through results |
| `PageUp` / `PageDown` | Move by six rows |
| `Enter` | Run the selected result's primary action |
| `Tab` / `Shift+Tab` | Cycle through available actions |
| `Ctrl+1…9` | Run an action by its position |
| `Ctrl+C` | Copy the selected result when no text is selected |
| `Ctrl+,` | Open Settings |
| `Ctrl+T` | Open Tools |
| `Ctrl+R` | Re-index applications and files |
| `Esc` | Clear action selection, then hide the launcher |
| Right-click a result | Open its context menu |

## Personalize it

Choose from **Graphite, Light, AMOLED, Catppuccin Mocha, Dracula,** and **Nord**. Adjust accent color, transparency, font family and size, launcher width, result spacing, widget layout, and animation behavior.

The launcher shell, shared controls, common headings, and Tools navigation are available in nine languages: English, Turkish, Spanish, French, German, Italian, Brazilian Portuguese, Japanese, and Simplified Chinese. This is **partial localization**; longer descriptions, tool content, dialogs, and many dynamic messages remain in English.

## Privacy and local data

SeekR is designed to keep its working data on your device. Configuration, database, logs, notes, and optional clipboard history are stored locally.

**Important storage details:**
- Clipboard monitoring is **off by default** and requires opt-in.
- Clipboard text and optional PNG image captures are stored **unencrypted** on the local device.
- Disabling clipboard monitoring stops future capture; it does not erase existing entries. Use the clear controls to delete saved history.
- The sensitive-content filter is heuristic, not a guarantee that every password, token, or secret will be detected.
- Application usage ranking and file-content search are also opt-in.
- Diagnostics reports are generated only when requested and are not uploaded by SeekR.

On Windows, user data is stored under `%APPDATA%\\SeekR`. Uninstalling the application preserves this data. Backups contain the same local data and should be kept private.

Read the full [privacy and local-data notes](#privacy-and-local-data) in this README and [installation guide](docs/INSTALLATION.md) before enabling clipboard capture.

## Requirements

**For users**
- 64-bit Windows 10 or Windows 11.
- The release installer or portable executable.
- No separate Python installation required.

**For development**
- Python 3.10 or newer (Python 3.12 recommended).
- PySide6, psutil, SymPy, and tzdata. Install the pinned dependencies from the repository requirements files.

Linux is used in CI and supports source-mode development/testing. macOS is not currently a supported or tested platform.

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

For headless Linux environments:

```bash
QT_QPA_PLATFORM=offscreen pytest
```

Build a Windows executable:

```powershell
python build.py
```

See [docs/INSTALLATION.md](docs/INSTALLATION.md) for build options and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the codebase design.

## Quality and release validation

The published 2.0.0 workflow completed successfully:

| CI environment | Result |
|---|---:|
| Ubuntu | 328 passed · 2 skipped |
| Windows Latest | 326 passed · 4 skipped |
| Windows Server 2022 | 326 passed · 4 skipped |

The Windows packaging workflow also passed portable and onedir builds, packaged UI checks, installer compilation, install/launch/uninstall smoke tests, and checksum staging. These automated checks are not a substitute for physical-desktop testing.

Useful engineering documents:
- [Windows audit and evidence](docs/WINDOWS_AUDIT.md)
- [Manual Windows test checklist](docs/WINDOWS_MANUAL_TEST.md)
- [Windows performance notes](docs/WINDOWS_PERFORMANCE.md)
- [Performance methodology](docs/PERFORMANCE.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Changelog](CHANGELOG.md)

## Known limitations

- Full manual validation on physical Windows 10/11 desktops remains outstanding, including mixed-DPI/multi-monitor behavior, sleep/resume, a real upgrade from 1.x, and long-duration stability.
- The Windows binaries are unsigned and may trigger a SmartScreen unfamiliar-app warning.
- Localization covers the launcher shell and shared navigation, not every screen or message.
- GPU utilization depends on performance counters exposed by the installed driver and Windows configuration.
- First-time dictionary lookups require an internet connection; previously retrieved definitions are cached locally.
- Firefox/Chromium bookmarks can be skipped when profiles are unavailable, corrupt, or blocked by permissions.
- SSH requires the Windows OpenSSH Client; SeekR does not store SSH passwords.
- Screenshot capture and mixed-DPI positioning still need additional real-display verification.

See [the detailed limitations and Windows audit](docs/WINDOWS_AUDIT.md) for current evidence.

## Roadmap

**2.0.0** focuses on a broader local productivity toolkit, configurable widgets, workflows, tasks, snippets, and maintenance tools.

A plugin marketplace is planned for **3.0.0**. Plugins are **not included in 2.0.0**: the Settings → Plugins page is a Coming Soon placeholder, and this release does not load or execute plugin code.

## Contributing

Bug reports, reproducible issues, and thoughtful suggestions are welcome. Before opening an issue, check the [existing issues](https://github.com/okyanus-11/SeekR/issues). Please include reproduction steps and relevant environment details, but never attach passwords, private clipboard contents, or personal notes.

## License

SeekR is released under the [MIT License](LICENSE).

Copyright © 2026 Okyanus Bora Şevik.

<div align="center">
<br>
<strong>Less searching. More doing.</strong>
<br>
<sub>Made with Python, PySide6, SymPy, psutil, and SQLite.</sub>
</div>
