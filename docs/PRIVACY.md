# SeekR privacy and local data

## Clipboard history

Clipboard monitoring is opt-in and disabled by default. The user must enable clipboard history and accept its consent setting before capture begins. Image capture requires a separate opt-in.

- Text is stored as plain text, including multiline text. Rich-text styling and embedded HTML are not preserved as formatting.
- Optional image captures are normalized to PNG and bounded by file size and image dimensions.
- Clipboard text is stored in the local SQLite database. Optional images are stored as local PNG files.
- Clipboard text and image files are **not encrypted by SeekR**.
- Monitoring can be paused from Tools → Clipboard. Individual entries can be deleted, unpinned entries can be cleared, or all entries (including pinned entries and image files) can be removed after confirmation.
- Age/count retention applies to unpinned entries. Pinned entries are retained until explicitly unpinned or deleted.

The sensitive-content filter checks for several common credential formats, but it is a best-effort heuristic. It cannot reliably recognize every secret. Users should not rely on it to protect passwords, API keys, recovery codes, or other sensitive material.

## Application usage ranking

Application usage tracking is a separate opt-in setting. When disabled, usage-based ranking is not applied. The user can clear the stored usage data from Settings.

## Network features

Weather, web search, dictionary lookups, and update checks contact their configured providers only when used or when their enabled refresh/check behavior runs. Weather uses the city entered in settings rather than precise device location. Update checks read release metadata from the official SeekR GitHub repository; SeekR does not silently download or install an update.

## Diagnostics

SeekR does not upload clipboard contents, notes, file paths, or search history as crash reports. No automatic crash-report upload is included in 2.0.0.

## User data location and removal

Configuration and the SQLite database are stored under the user's application-data directory. Normal uninstall is intended to preserve user data; remove the remaining SeekR data directory manually only if you deliberately want to erase local settings and history. Back up the directory before reinstalling or troubleshooting database issues.
