# Installation

## Requirements
- Windows 10 or Windows 11 (primary supported platform)
- Python 3.11+
- Git

## Install from source (PowerShell)

```powershell
git clone https://github.com/okyanus-11/SeekR.git
cd SeekR
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

If activation is blocked, use `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` and `.\.venv\Scripts\python.exe main.py`.

## Build a standalone executable

```powershell
pip install -r requirements-dev.txt
python build.py
```

Build on Windows for a Windows executable. On first launch, review Settings and choose which folders to index. Clipboard history is opt-in. See README for hotkeys, Windows integration and troubleshooting.
