# SeekR architecture

## Layers

```
main.py
  └── core.application.SeekRApplication        (composition root)
        ├── core.config_manager.ConfigManager  (JSON, validated, atomic)
        ├── core.database.Database             (SQLite, WAL, per-thread)
        ├── core.search_engine.SearchEngine    (keywords, ranking, dedupe)
        ├── features.*                         (services + providers)
        └── ui.*                               (launcher, settings, tools)
```

Features never import `ui`. Anything that needs the interface goes through
`core.hooks.UIHooks`:

```python
class UIHooks(Protocol):
    def hide_launcher(self) -> None: ...
    def copy_text(self, text: str) -> bool: ...
    def open_url(self, url: str) -> bool: ...
    def notify(self, message: str, level: str = "info") -> None: ...
    def confirm(self, title: str, message: str) -> bool: ...
    def open_settings(self, page: str | None = None) -> None: ...
    def open_tools(self, page: str | None = None) -> None: ...
    def open_notes(self, note_id: int | None = None) -> None: ...
    def fill_query(self, query: str) -> None: ...
    def show_error(self, title: str, message: str) -> None: ...
```

`NullHooks` implements the protocol for tests and background use.

## Search pipeline

1. `SearchEngine.search(text)` resolves a keyword prefix (`web:`, `calc:`, …)
   through a single map built from provider keywords plus validated user
   aliases. Aliases cannot shadow real keywords.
2. With a keyword, only that provider runs and receives the remainder of the
   query. An empty remainder asks the provider for `empty_help()`.
3. Without a keyword, every provider with `auto = True` runs. Provider
   exceptions are caught and converted into an "unavailable" result; one bad
   provider cannot break the launcher.
4. Results are weighted by the provider, sorted by score, deduplicated by
   `(title, subtitle)` per provider, truncated to the configured limit, and —
   when the query is empty — merged with suggestions and history.

`SearchResult` carries display fields, a primary callback, optional secondary
`ResultAction`s and `copy_text`. Execution is handled by the launcher, which
also owns action cycling (`Tab`, `Ctrl+1…9`) and the context menu.

## Threading

- File indexing and application scanning run in `QThreadPool` jobs
  (`core.workers`) with `CancelToken` support and progress/error callbacks.
- Clipboard polling uses a `QTimer` on the GUI thread reading the clipboard
  (a cheap operation) and writes through the database layer.
- Process sampling and system snapshots are short-lived `psutil` calls; long
  refreshes are timer-driven and skipped when a page is hidden.
- All database writes are serialized with a lock; reads use per-thread
  connections. `:memory:` databases share one locked connection.

## Persistence

`ConfigManager` deep-copies defaults, merges user data, coerces types, clamps
ranges and validates special keys (colors, hotkeys, aliases, provider lists).
Saves are atomic (`NamedTemporaryFile` + `os.replace`). Invalid files are
renamed to `config.corrupt.json` and defaults are loaded.

`Database` owns the schema and every query. Timestamps are Unix floats for easy
retention maths. Clipboard rows store a hash for deduplication; pinned rows are
exempt from pruning.

## Extension points

- **New provider:** subclass `SearchProvider`, implement `search`, register it
  in `SeekRApplication._register_providers()` (or from a future plugin host).
- **New settings page:** subclass `SettingsPage`, add it to
  `SettingsWindow.PAGES`.
- **New tool page:** subclass `ToolTab`, add it to `ToolsWindow.PAGES`.
- **Theme:** add a palette to `ui/themes.py`; every widget uses palette roles
  rather than hard-coded colors.

## Failure handling

- A global `sys.excepthook` logs the traceback and shows a dialog instead of
  silently dying.
- Optional platform features (hotkey, power schemes, bookmarks, screenshots)
  return structured `(ok, message)` results; the UI displays the message.
- Subprocesses are always launched with argument lists (`shell=False`) and
  destructive operations require explicit confirmation.
