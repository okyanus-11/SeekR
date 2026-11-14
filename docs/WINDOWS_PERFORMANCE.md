# SeekR — Windows performance

## Status: not measured on Windows

No Windows measurement is reported here. SeekR 1.0.0 was audited on a headless
Linux x86-64 container with no Windows VM, no Wine and no physical Windows
machine. Reporting Linux timings as Windows results would be false, so this
document deliberately contains **no Windows numbers**.

The Linux measurements in [PERFORMANCE.md](PERFORMANCE.md) describe the
algorithmic hot paths only. They do **not** predict Windows startup,
filesystem/Defender overhead, shell icon extraction or GDI/Qt rendering cost.

## What must be measured

On a real Windows 10/11 machine, record all of the following with the hardware
and OS written down:

| Metric | How to measure |
|---|---|
| Cold startup (first run after reboot, no OS cache) | Time from launching `SeekR.exe` until the launcher is visible. Repeat 5×; report median and range. |
| Warm startup | Launch, quit, relaunch within a minute; time until visible. Repeat 5×. |
| Hotkey-to-visible latency | Timestamp before `Alt+Space` and when the window is painted; repeat 20×. |
| Search latency | `tools/benchmark.py` plus a manually measured keystroke-to-results time for app, file and calculator queries. |
| Calculator latency | `tools/benchmark.py` calculator benchmark; also type `calc: sqrt(144) + 25 * 4`. |
| Application discovery | Time a full Start Menu re-index from Settings → Applications; record number of shortcuts. |
| File indexing | Index a fixed tree (e.g. 10,000 files, 2 GB) and record elapsed time and CPU; note NTFS, SSD/HDD and Defender state. |
| Idle CPU | Task Manager / `Get-Counter` over 5 minutes with the launcher hidden and clipboard monitoring enabled. |
| Idle memory | Working set and private bytes after 5 minutes idle, then after opening Settings and Tools once. |
| Executable size/startup | `dist\SeekR.exe` size; onedir size; extraction overhead of the onefile build. |

Suggested commands (run from the repository root in PowerShell):

```powershell
.venv\Scripts\python tools\benchmark.py
Measure-Command { Start-Process .\dist\SeekR.exe -ArgumentList '--version' -Wait }
Get-Counter '\Process(SeekR)\Working Set - Private' -SampleInterval 5 -MaxSamples 12
```

For startup timing, use a stopwatch or ETW/Windows Performance Recorder rather
than `Measure-Command` on a process that keeps running; `--version` only
measures interpreter/bundle startup, not GUI readiness.

## Recording template

Copy this table into the document when measurements exist:

| Field | Value |
|---|---|
| Windows edition/version/build | |
| CPU / RAM / storage | |
| GPU and driver | |
| Display scaling / resolution / monitor count | |
| Defender / third-party antivirus state | |
| Build type (onefile / onedir) | |
| Cold startup median (range) | |
| Warm startup median (range) | |
| Hotkey-to-visible median | |
| Search / calculator medians | |
| Application discovery (count, seconds) | |
| File indexing (files, GB, seconds) | |
| Idle CPU / idle private memory | |
| Tester / date | |

## Known performance risks on Windows

- **Onefile extraction:** the onefile executable unpacks to a temporary folder
  on every launch. This can dominate cold start, especially with real-time
  antivirus scanning. The onedir build avoids it and is the recommended
  troubleshooting build.
- **Defender:** scanning the bundled Qt DLLs and the SQLite database can add
  substantial first-run latency.
- **Icon extraction:** `.lnk` icon extraction through the shell is slower than
  the cached glyph fallback; a large Start Menu may take noticeably longer than
  on Linux.
- **Network/redirected profiles:** OneDrive-redirected Desktop/Documents can
  make file indexing and existence checks slower.
- **PowerShell/WMI:** system information now runs off the GUI thread and is
  cached, but the first GPU query can take hundreds of milliseconds on some
  machines.

Until the table above is filled on real Windows, the Windows release must be
described as functionally unverified and performance-unmeasured.
