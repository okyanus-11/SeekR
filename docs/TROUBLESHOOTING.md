# Troubleshooting

## SeekR does not start

- On Windows, check that the standalone executable matches the machine
  architecture and that Windows has not quarantined the download. Do not
  disable security software to make an unverified build run.
- The windowed executable does not display command-line output. Check its
  version in Explorer → Properties → Details; from source, run
  `python main.py --version` or `python main.py --debug`.
- Check `%APPDATA%\SeekR\logs\seekr.log` on Windows. The source-mode log is
  stored under the platform application-data directory.

## The global shortcut does not work

Another application may already own the shortcut. Open Settings → General,
choose another combination, and check the visible registration status. The
global hotkey requires an interactive desktop session; remote or restricted
sessions can block it.

## Search does not find a file or application

- Confirm the folder is included in Settings → Files, then run **Index now**.
- Check excluded folders, extensions, hidden-file settings, and the maximum
  index size.
- Refresh the application index in Settings → Applications.
- Files on network shares or redirected profiles can take longer to index.

## Clipboard history

Clipboard history is opt-in. When enabled, copied text is stored in the local
SQLite database in plaintext. Do not copy passwords, private keys, or other
secrets while capture is enabled. Clear history from the Clipboard tools page
if you no longer want those entries retained; deleting rows is not a secure
erasure guarantee for database files or backups.

## Configuration or database problems

Close SeekR before manually copying or moving its data folder. If configuration
JSON is corrupt, SeekR preserves a `config.corrupt.json` copy and loads
defaults; review that copy before resetting settings. Do not delete the SQLite
database unless you accept losing local history, notes, bookmarks, and indexed
metadata.

## Native Windows integrations

Tray behavior, shortcuts, window switching, Snipping Tool, and startup
registration depend on Windows shell APIs and desktop policy. If one fails,
record the Windows build, exact steps, and the relevant log excerpt, then
consult [the Windows manual test checklist](WINDOWS_MANUAL_TEST.md). Do not
include passwords, private clipboard text, or other personal data in a bug
report.
