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
erasure guarantee for database files or backups. The sensitive-content filter
recognizes several common credential formats but is only a heuristic; it cannot
guarantee that every secret is excluded. Optional image captures are stored as
unencrypted PNG files in the SeekR data directory. Use the Clipboard page's
pause control to stop future capture, or its clear-all action to remove pinned
and unpinned history.

## Database backup and restore

Use Tools → Database & backups to create an integrity-checked SQLite backup
before troubleshooting or reinstalling. Backup files are not encrypted and
contain the same local data as the database; store them privately. Restoring a
backup replaces the current database. SeekR validates the backup and attempts
to restore the previous live snapshot if the restore operation fails. Do not
delete the current database manually as a first troubleshooting step.

## Update download verification

SeekR checks release metadata from the official GitHub repository. If you
download an installer or portable archive, use the corresponding **Verify
downloaded…** action and select the local file. A success message means both
the expected file size and SHA-256 digest match GitHub's release metadata. A
mismatch means the file should not be run. SeekR does not automatically run
downloaded installers.

## Launching SeekR again does not bring the window forward

SeekR runs a single instance: a second launch asks the running copy to show its
window and then exits with code 0. Windows can refuse to hand the foreground to
a background process, so the running copy retries activation for about a second
rather than hiding again. If the window still does not appear:

- Confirm the process is running (notification area or Task Manager). A second
  launch that exits immediately is expected, not a crash.
- Check for a full-screen or always-on-top window covering the launcher.
- Start SeekR with `--debug` and look for launcher activation messages in
  `%APPDATA%\SeekR\logs\seekr.log`.
- `--allow-multiple` bypasses the single-instance check; use it only for
  development, never to work around a genuine failure.

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

### Dictionary works offline only for previously looked-up words

SeekR stores successful definitions in its local cache. A word that has never
been looked up still needs an internet connection. If the cache becomes
unreadable, SeekR rebuilds it as new definitions are fetched.

### Quick Connect cannot find OpenSSH

On Windows, SeekR checks the standard %WINDIR%\System32\OpenSSH\ssh.exe
location as well as PATH. If the client is not installed, enable the Windows
OpenSSH Client optional feature. On other systems, install the distribution's
OpenSSH client package and make sure ssh is on PATH. SeekR uses key or agent
authentication and does not store passwords.
