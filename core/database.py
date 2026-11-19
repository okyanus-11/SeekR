"""SQLite storage for applications, files, clipboard, notes and history."""

from __future__ import annotations

import atexit
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Iterable, Sequence

from . import paths
from .errors import DatabaseError
from .logging_setup import get_logger

log = get_logger(__name__)

SCHEMA_VERSION = 5

_SCHEMA = """
CREATE TABLE IF NOT EXISTS apps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    path TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL DEFAULT 'start_menu',
    args TEXT NOT NULL DEFAULT '',
    icon_path TEXT NOT NULL DEFAULT '',
    created REAL NOT NULL,
    last_used REAL NOT NULL DEFAULT 0,
    use_count INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_apps_name ON apps(name);

CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    name_lower TEXT NOT NULL,
    dir TEXT NOT NULL,
    ext TEXT NOT NULL DEFAULT '',
    is_dir INTEGER NOT NULL DEFAULT 0,
    size INTEGER NOT NULL DEFAULT 0,
    mtime REAL NOT NULL DEFAULT 0,
    indexed REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_files_name ON files(name_lower);
CREATE INDEX IF NOT EXISTS idx_files_ext_mtime ON files(ext, mtime DESC);

CREATE TABLE IF NOT EXISTS clipboard (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    hash TEXT NOT NULL,
    pinned INTEGER NOT NULL DEFAULT 0,
    created REAL NOT NULL,
    source TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_clipboard_hash ON clipboard(hash);
CREATE INDEX IF NOT EXISTS idx_clipboard_created ON clipboard(created DESC);

CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    pinned INTEGER NOT NULL DEFAULT 0,
    created REAL NOT NULL,
    updated REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    value TEXT NOT NULL,
    created REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_history_kind ON history(kind, created DESC);

CREATE TABLE IF NOT EXISTS custom_commands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    command TEXT NOT NULL,
    args TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    aliases TEXT NOT NULL DEFAULT '',
    confirm INTEGER NOT NULL DEFAULT 1,
    created REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS ssh_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    host TEXT NOT NULL,
    port INTEGER NOT NULL DEFAULT 22,
    user TEXT NOT NULL DEFAULT '',
    key_path TEXT NOT NULL DEFAULT '',
    extra_args TEXT NOT NULL DEFAULT '',
    created REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS quick_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    kind TEXT NOT NULL,
    target TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created REAL NOT NULL
);



CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    due_date TEXT NOT NULL DEFAULT '',
    completed INTEGER NOT NULL DEFAULT 0,
    created REAL NOT NULL,
    updated REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tasks_status_due ON tasks(completed, due_date, created);

CREATE TABLE IF NOT EXISTS snippets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '',
    shortcut TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    created REAL NOT NULL,
    updated REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snippets_title ON snippets(title COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS workflows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    steps_json TEXT NOT NULL,
    created REAL NOT NULL,
    updated REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_workflows_title ON workflows(title COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS kv (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


class Database:
    """Thread-aware SQLite wrapper.

    Every thread gets its own connection (SQLite objects are not shareable);
    in-memory databases use a single shared connection guarded by a lock.
    """

    def __init__(self, path: str | Path | None = None):
        self.path = str(path) if path is not None else str(paths.database_path())
        self._lock = threading.RLock()
        self._local = threading.local()
        self._shared: sqlite3.Connection | None = None
        self._closed = False
        self._is_memory = self.path == ":memory:" or self.path.startswith("file::memory:")
        try:
            self._init_schema()
        except sqlite3.Error as exc:
            raise DatabaseError(f"Could not initialise database: {exc}") from exc
        atexit.register(self.close)

    # -------------------------------------------------------------- internals
    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=8.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        if not self._is_memory:
            try:
                connection.execute("PRAGMA journal_mode = WAL")
            except sqlite3.Error:
                pass
            connection.execute("PRAGMA synchronous = NORMAL")
        return connection

    def connection(self) -> sqlite3.Connection:
        """Return this thread's connection."""
        if self._is_memory:
            with self._lock:
                if self._shared is None:
                    self._shared = self._connect()
                    self._shared.executescript(_SCHEMA)
                    self._shared.commit()
                return self._shared
        connection = getattr(self._local, "conn", None)
        if connection is None:
            connection = self._connect()
            self._local.conn = connection
            self._local.conn.executescript(_SCHEMA)
            self._local.conn.commit()
        return connection

    def _init_schema(self) -> None:
        if not self._is_memory:
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            conn = self.connection()
            conn.executescript(_SCHEMA)
            clipboard_columns = {row["name"] for row in conn.execute("PRAGMA table_info(clipboard)")}
            if "category" not in clipboard_columns:
                conn.execute("ALTER TABLE clipboard ADD COLUMN category TEXT NOT NULL DEFAULT ''")
            conn.execute("DROP INDEX IF EXISTS idx_files_ext")
            conn.execute(
                "INSERT OR REPLACE INTO kv(key, value) VALUES('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )
            conn.commit()

    def _query(self, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        try:
            cursor = self.connection().execute(sql, params)
            return cursor.fetchall()
        except sqlite3.Error as exc:
            log.error("Query failed (%s): %s", exc, sql.strip()[:120])
            return []

    def _query_one(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Row | None:
        rows = self._query(sql, params)
        return rows[0] if rows else None

    def _write(self, sql: str, params: Sequence[Any] = ()) -> int:
        try:
            conn = self.connection()
            with self._lock:
                cursor = conn.execute(sql, params)
                conn.commit()
                return cursor.lastrowid or cursor.rowcount
        except sqlite3.Error as exc:
            log.error("Write failed (%s): %s", exc, sql.strip()[:120])
            return -1

    def _write_many(self, sql: str, rows: Iterable[Sequence[Any]]) -> int:
        try:
            conn = self.connection()
            with self._lock:
                cursor = conn.executemany(sql, rows)
                conn.commit()
                return cursor.rowcount
        except sqlite3.Error as exc:
            log.error("Batch write failed (%s): %s", exc, sql.strip()[:120])
            return 0

    # ------------------------------------------------------------------ meta
    def set_meta(self, key: str, value: Any) -> None:
        self._write(
            "INSERT INTO kv(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )

    def get_meta(self, key: str, default: str | None = None) -> str | None:
        row = self._query_one("SELECT value FROM kv WHERE key = ?", (key,))
        return row["value"] if row else default

    # ------------------------------------------------------------------- apps
    def upsert_apps(self, apps: Iterable[dict[str, Any]], prune_missing: bool = False) -> int:
        """Insert or update application records keyed by path."""
        now = time.time()
        rows = [
            (
                app.get("name", ""),
                app.get("path", ""),
                app.get("source", "start_menu"),
                app.get("args", ""),
                app.get("icon_path", ""),
                now,
            )
            for app in apps
            if app.get("path")
        ]
        if not rows:
            return 0
        written = self._write_many(
            """INSERT INTO apps(name, path, source, args, icon_path, created)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(path) DO UPDATE SET
                 name = excluded.name,
                 source = excluded.source,
                 args = excluded.args,
                 icon_path = excluded.icon_path""",
            rows,
        )
        if prune_missing:
            keep = {row[1] for row in rows}
            existing = self._query("SELECT path FROM apps")
            stale = [(row["path"],) for row in existing if row["path"] not in keep]
            if stale:
                self._write_many("DELETE FROM apps WHERE path = ?", stale)
        return written

    def all_apps(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._query("SELECT * FROM apps ORDER BY name COLLATE NOCASE")]

    def app_candidates(self, like: str, limit: int = 400) -> list[dict[str, Any]]:
        pattern = f"%{like}%"
        rows = self._query(
            "SELECT * FROM apps WHERE name LIKE ? COLLATE NOCASE OR path LIKE ? COLLATE NOCASE LIMIT ?",
            (pattern, pattern, limit),
        )
        return [dict(row) for row in rows]

    def get_app(self, app_id: int) -> dict[str, Any] | None:
        row = self._query_one("SELECT * FROM apps WHERE id = ?", (app_id,))
        return dict(row) if row else None

    def record_app_launch(self, path: str) -> None:
        self._write(
            "UPDATE apps SET last_used = ?, use_count = use_count + 1 WHERE path = ?",
            (time.time(), path),
        )

    def recent_apps(self, limit: int = 6) -> list[dict[str, Any]]:
        rows = self._query(
            "SELECT * FROM apps WHERE use_count > 0 ORDER BY last_used DESC LIMIT ?", (limit,)
        )
        return [dict(row) for row in rows]

    def frequent_apps(self, limit: int = 6) -> list[dict[str, Any]]:
        rows = self._query(
            "SELECT * FROM apps WHERE use_count > 0 ORDER BY use_count DESC, last_used DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in rows]

    def count_apps(self) -> int:
        row = self._query_one("SELECT COUNT(*) AS n FROM apps")
        return int(row["n"]) if row else 0

    def clear_apps(self) -> None:
        self._write("DELETE FROM apps")

    # ------------------------------------------------------------------ files
    def upsert_files(self, entries: Iterable[dict[str, Any]], indexed_at: float | None = None) -> int:
        now = time.time() if indexed_at is None else float(indexed_at)
        rows = [
            (
                entry["path"],
                entry["name"],
                entry["name"].lower(),
                entry.get("dir", str(Path(entry["path"]).parent)),
                entry.get("ext", ""),
                1 if entry.get("is_dir") else 0,
                int(entry.get("size", 0) or 0),
                float(entry.get("mtime", 0) or 0),
                now,
            )
            for entry in entries
            if entry.get("path") and entry.get("name")
        ]
        if not rows:
            return 0
        return self._write_many(
            """INSERT INTO files(path, name, name_lower, dir, ext, is_dir, size, mtime, indexed)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(path) DO UPDATE SET
                 name = excluded.name,
                 name_lower = excluded.name_lower,
                 dir = excluded.dir,
                 ext = excluded.ext,
                 is_dir = excluded.is_dir,
                 size = excluded.size,
                 mtime = excluded.mtime,
                 indexed = excluded.indexed""",
            rows,
        )

    def file_candidates(self, like: str, limit: int = 800, ext: str | None = None) -> list[dict[str, Any]]:
        pattern = f"%{like}%"
        if ext:
            rows = self._query(
                "SELECT * FROM files WHERE name_lower LIKE ? AND ext = ? LIMIT ?",
                (pattern, ext.lower(), limit),
            )
        else:
            rows = self._query(
                "SELECT * FROM files WHERE name_lower LIKE ? ORDER BY mtime DESC LIMIT ?",
                (pattern, limit),
            )
        return [dict(row) for row in rows]

    def files_by_extension(self, ext: str, limit: int = 800) -> list[dict[str, Any]]:
        rows = self._query(
            "SELECT * FROM files WHERE ext = ? ORDER BY mtime DESC LIMIT ?",
            (ext.lower(), limit),
        )
        return [dict(row) for row in rows]

    def recent_files(self, limit: int = 5, directories: Sequence[str] = ()) -> list[dict[str, Any]]:
        if directories:
            scopes = [(directory, directory.rstrip("/\\"))
                      for directory in directories if directory]
            if not scopes:
                return []
            clauses = " OR ".join(
                "(dir IN (?, ?) OR (substr(dir, 1, ?) = ? AND "
                "substr(dir, ?, 1) IN ('/', char(92))))"
                for _ in scopes
            )
            params: list[Any] = []
            for original, prefix in scopes:
                params.extend((original, prefix, len(prefix), prefix, len(prefix) + 1))
            params.append(limit)
            rows = self._query(
                f"SELECT * FROM files WHERE is_dir = 0 AND ({clauses}) ORDER BY mtime DESC LIMIT ?",
                params,
            )
        else:
            rows = self._query(
                "SELECT * FROM files WHERE is_dir = 0 ORDER BY mtime DESC LIMIT ?", (limit,)
            )
        return [dict(row) for row in rows]

    def count_files(self) -> int:
        row = self._query_one("SELECT COUNT(*) AS n FROM files")
        return int(row["n"]) if row else 0

    def prune_files_not_seen(self, directories: Sequence[str], seen_paths: Iterable[str]) -> int:
        """Remove stale indexed paths after a complete scan, using a temp table."""
        scopes = [str(Path(directory)) for directory in directories if directory]
        if not scopes:
            return 0
        clauses = []
        params: list[Any] = []
        for directory in scopes:
            prefix = directory.rstrip("/\\")
            if not prefix:
                clauses.append("(dir = ? OR substr(dir, 1, 1) = ?)")
                params.extend((directory, directory[:1]))
                continue
            clauses.append(
                "(dir IN (?, ?) OR (substr(dir, 1, ?) = ? AND "
                "substr(dir, ?, 1) IN ('/', char(92))))"
            )
            params.extend((directory, prefix, len(prefix), prefix, len(prefix) + 1))
        if not clauses:
            return 0
        try:
            conn = self.connection()
            with self._lock:
                conn.execute("CREATE TEMP TABLE IF NOT EXISTS seen_file_paths (path TEXT PRIMARY KEY)")
                conn.execute("DELETE FROM seen_file_paths")
                conn.executemany(
                    "INSERT OR IGNORE INTO seen_file_paths(path) VALUES (?)",
                    ((str(path),) for path in seen_paths),
                )
                cursor = conn.execute(
                    "DELETE FROM files WHERE (" + " OR ".join(clauses) + ") "
                    "AND path NOT IN (SELECT path FROM seen_file_paths)",
                    params,
                )
                conn.commit()
                return cursor.rowcount
        except sqlite3.Error as exc:
            log.error("Could not prune stale file index rows: %s", exc)
            return 0

    def prune_files_before(self, directories: Sequence[str], indexed_before: float) -> int:
        """Remove stale indexed rows under configured roots after a complete scan."""
        scopes = [str(Path(directory)) for directory in directories if directory]
        if not scopes:
            return 0
        clauses = []
        params: list[Any] = []
        for directory in scopes:
            prefix = directory.rstrip("/\\")
            if not prefix:
                continue
            clauses.append(
                "(dir IN (?, ?) OR (substr(dir, 1, ?) = ? AND "
                "substr(dir, ?, 1) IN ('/', char(92))))"
            )
            params.extend((directory, prefix, len(prefix), prefix, len(prefix) + 1))
        if not clauses:
            return 0
        params.append(float(indexed_before))
        return self._write(
            "DELETE FROM files WHERE (" + " OR ".join(clauses) + ") AND indexed < ?",
            params,
        )

    def clear_files(self) -> None:
        self._write("DELETE FROM files")

    def delete_files_under(self, directory: str) -> None:
        if not directory:
            return
        # Use a separator boundary instead of LIKE "path%": otherwise removing
        # /home/alex also deletes indexed files under /home/alexander.
        prefix = directory.rstrip("/\\")
        if not prefix:
            self._write("DELETE FROM files")
            return
        self._write(
            """DELETE FROM files
               WHERE dir IN (?, ?) OR (
                   substr(dir, 1, ?) = ?
                   AND substr(dir, ?, 1) IN ('/', char(92))
               )""",
            (directory, prefix, len(prefix), prefix, len(prefix) + 1),
        )

    # -------------------------------------------------------------- clipboard
    def add_clipboard(self, text: str, source: str = "", dedupe: bool = True) -> int | None:
        if not text or not text.strip():
            return None
        digest = self._hash_text(text)
        if dedupe:
            row = self._query_one("SELECT id, text FROM clipboard ORDER BY created DESC LIMIT 1")
            if row is not None and row["text"] == text:
                return None
        note_id = self._write(
            "INSERT INTO clipboard(text, hash, pinned, created, source) VALUES (?, ?, 0, ?, ?)",
            (text, digest, time.time(), source),
        )
        return note_id if note_id and note_id > 0 else None

    @staticmethod
    def _hash_text(text: str) -> str:
        import hashlib

        return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()

    def clipboard_items(self, search: str = "", limit: int = 100) -> list[dict[str, Any]]:
        if search:
            rows = self._query(
                "SELECT * FROM clipboard WHERE text LIKE ? OR category LIKE ? ORDER BY pinned DESC, created DESC LIMIT ?",
                (f"%{search}%", f"%{search}%", limit),
            )
        else:
            rows = self._query(
                "SELECT * FROM clipboard ORDER BY pinned DESC, created DESC LIMIT ?", (limit,)
            )
        return [dict(row) for row in rows]

    def set_clipboard_category(self, item_id: int, category: str) -> None:
        self._write(
            "UPDATE clipboard SET category = ? WHERE id = ?",
            (str(category).strip()[:40], int(item_id)),
        )

    def set_clipboard_pinned(self, item_id: int, pinned: bool) -> None:
        self._write("UPDATE clipboard SET pinned = ? WHERE id = ?", (1 if pinned else 0, item_id))

    def delete_clipboard(self, item_id: int) -> None:
        self._write("DELETE FROM clipboard WHERE id = ?", (item_id,))

    def clear_clipboard(self, keep_pinned: bool = False) -> None:
        if keep_pinned:
            self._write("DELETE FROM clipboard WHERE pinned = 0")
        else:
            self._write("DELETE FROM clipboard")

    def prune_clipboard(self, limit: int, retention_days: int | None = None) -> None:
        """Apply count and optional age limits to unpinned clipboard entries.

        Pinned entries are deliberately retained until the user deletes them.
        """
        if retention_days is not None:
            cutoff = time.time() - max(1, int(retention_days)) * 86400
            self._write(
                "DELETE FROM clipboard WHERE pinned = 0 AND created < ?",
                (cutoff,),
            )
        self._write(
            """DELETE FROM clipboard WHERE pinned = 0 AND id NOT IN (
                   SELECT id FROM clipboard WHERE pinned = 0 ORDER BY created DESC LIMIT ?
               )""",
            (max(1, int(limit)),),
        )

    def clipboard_count(self) -> int:
        row = self._query_one("SELECT COUNT(*) AS n FROM clipboard")
        return int(row["n"]) if row else 0

    # ------------------------------------------------------------------ notes
    def create_note(self, title: str, body: str = "", pinned: bool = False) -> int:
        now = time.time()
        note_id = self._write(
            "INSERT INTO notes(title, body, pinned, created, updated) VALUES (?, ?, ?, ?, ?)",
            (title.strip() or "Untitled note", body, 1 if pinned else 0, now, now),
        )
        return note_id if note_id > 0 else -1

    def update_note(
        self, note_id: int, title: str | None = None, body: str | None = None, pinned: bool | None = None
    ) -> None:
        fields: list[str] = []
        params: list[Any] = []
        if title is not None:
            fields.append("title = ?")
            params.append(title.strip() or "Untitled note")
        if body is not None:
            fields.append("body = ?")
            params.append(body)
        if pinned is not None:
            fields.append("pinned = ?")
            params.append(1 if pinned else 0)
        if not fields:
            return
        fields.append("updated = ?")
        params.append(time.time())
        params.append(note_id)
        self._write(f"UPDATE notes SET {', '.join(fields)} WHERE id = ?", params)

    def delete_note(self, note_id: int) -> None:
        self._write("DELETE FROM notes WHERE id = ?", (note_id,))

    def get_note(self, note_id: int) -> dict[str, Any] | None:
        row = self._query_one("SELECT * FROM notes WHERE id = ?", (note_id,))
        return dict(row) if row else None

    def notes(self, search: str = "", limit: int = 200) -> list[dict[str, Any]]:
        if search:
            rows = self._query(
                """SELECT * FROM notes WHERE title LIKE ? OR body LIKE ?
                   ORDER BY pinned DESC, updated DESC LIMIT ?""",
                (f"%{search}%", f"%{search}%", limit),
            )
        else:
            rows = self._query(
                "SELECT * FROM notes ORDER BY pinned DESC, updated DESC LIMIT ?", (limit,)
            )
        return [dict(row) for row in rows]

    def note_count(self) -> int:
        row = self._query_one("SELECT COUNT(*) AS n FROM notes")
        return int(row["n"]) if row else 0

    # ---------------------------------------------------------------- history
    def add_history(self, kind: str, value: str) -> None:
        if not value:
            return
        self._write(
            "INSERT INTO history(kind, value, created) VALUES (?, ?, ?)",
            (kind, value, time.time()),
        )

    def history(self, kind: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        if kind:
            rows = self._query(
                "SELECT * FROM history WHERE kind = ? ORDER BY created DESC, id DESC LIMIT ?",
                (kind, limit),
            )
        else:
            rows = self._query(
                "SELECT * FROM history ORDER BY created DESC, id DESC LIMIT ?", (limit,)
            )
        return [dict(row) for row in rows]

    def recent_queries(self, limit: int = 5) -> list[str]:
        rows = self._query(
            """SELECT value, MAX(created) AS latest, MAX(id) AS latest_id FROM history
               WHERE kind = 'search'
               GROUP BY value ORDER BY latest DESC, latest_id DESC LIMIT ?""",
            (limit,),
        )
        return [row["value"] for row in rows]

    def prune_history(self, days: int) -> None:
        cutoff = time.time() - max(1, days) * 86400
        self._write("DELETE FROM history WHERE created < ?", (cutoff,))

    def clear_history(self, kinds: Sequence[str] | None = None) -> None:
        if kinds:
            placeholders = ",".join("?" for _ in kinds)
            self._write(f"DELETE FROM history WHERE kind IN ({placeholders})", list(kinds))
        else:
            self._write("DELETE FROM history")

    # --------------------------------------------------------------- commands
    def list_custom_commands(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._query("SELECT * FROM custom_commands ORDER BY name")]

    def upsert_custom_command(self, data: dict[str, Any]) -> int:
        command_id = data.get("id")
        now = time.time()
        if command_id:
            self._write(
                """UPDATE custom_commands SET name = ?, command = ?, args = ?, description = ?,
                   aliases = ?, confirm = ? WHERE id = ?""",
                (
                    data["name"],
                    data["command"],
                    data.get("args", ""),
                    data.get("description", ""),
                    data.get("aliases", ""),
                    1 if data.get("confirm", True) else 0,
                    command_id,
                ),
            )
            return int(command_id)
        return self._write(
            """INSERT INTO custom_commands(name, command, args, description, aliases, confirm, created)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(name) DO UPDATE SET command = excluded.command, args = excluded.args,
                   description = excluded.description, aliases = excluded.aliases, confirm = excluded.confirm""",
            (
                data["name"],
                data["command"],
                data.get("args", ""),
                data.get("description", ""),
                data.get("aliases", ""),
                1 if data.get("confirm", True) else 0,
                now,
            ),
        )

    def delete_custom_command(self, command_id: int) -> None:
        self._write("DELETE FROM custom_commands WHERE id = ?", (command_id,))

    # -------------------------------------------------------------------- ssh
    def list_ssh_profiles(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._query("SELECT * FROM ssh_profiles ORDER BY name")]

    def upsert_ssh_profile(self, data: dict[str, Any]) -> int:
        profile_id = data.get("id")
        if profile_id:
            self._write(
                """UPDATE ssh_profiles SET name = ?, host = ?, port = ?, user = ?,
                   key_path = ?, extra_args = ? WHERE id = ?""",
                (
                    data["name"],
                    data["host"],
                    int(data.get("port", 22)),
                    data.get("user", ""),
                    data.get("key_path", ""),
                    data.get("extra_args", ""),
                    profile_id,
                ),
            )
            return int(profile_id)
        return self._write(
            """INSERT INTO ssh_profiles(name, host, port, user, key_path, extra_args, created)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(name) DO UPDATE SET host = excluded.host, port = excluded.port,
                   user = excluded.user, key_path = excluded.key_path, extra_args = excluded.extra_args""",
            (
                data["name"],
                data["host"],
                int(data.get("port", 22)),
                data.get("user", ""),
                data.get("key_path", ""),
                data.get("extra_args", ""),
                time.time(),
            ),
        )

    def delete_ssh_profile(self, profile_id: int) -> None:
        self._write("DELETE FROM ssh_profiles WHERE id = ?", (profile_id,))

    # --------------------------------------------------------- quick actions
    def list_quick_actions(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._query("SELECT * FROM quick_actions ORDER BY title")]

    def upsert_quick_action(self, data: dict[str, Any]) -> int:
        action_id = data.get("id")
        if action_id:
            self._write(
                "UPDATE quick_actions SET title = ?, kind = ?, target = ?, description = ? WHERE id = ?",
                (
                    data["title"],
                    data["kind"],
                    data["target"],
                    data.get("description", ""),
                    action_id,
                ),
            )
            return int(action_id)
        return self._write(
            "INSERT INTO quick_actions(title, kind, target, description, created) VALUES (?, ?, ?, ?, ?)",
            (
                data["title"],
                data["kind"],
                data["target"],
                data.get("description", ""),
                time.time(),
            ),
        )

    def delete_quick_action(self, action_id: int) -> None:
        self._write("DELETE FROM quick_actions WHERE id = ?", (action_id,))



    # ------------------------------------------------------------------- tasks
    def list_tasks(self, include_completed: bool = True) -> list[dict[str, Any]]:
        where = "" if include_completed else "WHERE completed = 0"
        rows = self._query(
            f"SELECT * FROM tasks {where} ORDER BY completed ASC, CASE WHEN due_date = '' THEN 1 ELSE 0 END, due_date ASC, created DESC"
        )
        return [dict(row) for row in rows]

    def get_task(self, task_id: int) -> dict[str, Any] | None:
        row = self._query_one("SELECT * FROM tasks WHERE id = ?", (int(task_id),))
        return dict(row) if row else None

    def upsert_task(self, data: dict[str, Any]) -> int:
        now = time.time()
        task_id = data.get("id")
        values = (
            data["title"], data.get("notes", ""), data.get("due_date", ""),
            1 if data.get("completed") else 0, now,
        )
        if task_id:
            self._write(
                "UPDATE tasks SET title = ?, notes = ?, due_date = ?, completed = ?, updated = ? WHERE id = ?",
                (*values, int(task_id)),
            )
            return int(task_id)
        return self._write(
            "INSERT INTO tasks(title, notes, due_date, completed, created, updated) VALUES (?, ?, ?, ?, ?, ?)",
            (*values[:4], now, now),
        )

    def set_task_completed(self, task_id: int, completed: bool) -> None:
        self._write(
            "UPDATE tasks SET completed = ?, updated = ? WHERE id = ?",
            (1 if completed else 0, time.time(), int(task_id)),
        )

    def delete_task(self, task_id: int) -> None:
        self._write("DELETE FROM tasks WHERE id = ?", (int(task_id),))

    # ---------------------------------------------------------------- snippets
    def list_snippets(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._query("SELECT * FROM snippets ORDER BY title COLLATE NOCASE")]

    def get_snippet(self, snippet_id: int) -> dict[str, Any] | None:
        row = self._query_one("SELECT * FROM snippets WHERE id = ?", (int(snippet_id),))
        return dict(row) if row else None

    def upsert_snippet(self, data: dict[str, Any]) -> int:
        now = time.time()
        snippet_id = data.get("id")
        values = (
            data["title"], data.get("category", ""), data.get("shortcut", ""),
            data["content"], now,
        )
        if snippet_id:
            self._write(
                "UPDATE snippets SET title = ?, category = ?, shortcut = ?, content = ?, updated = ? WHERE id = ?",
                (*values, int(snippet_id)),
            )
            return int(snippet_id)
        return self._write(
            "INSERT INTO snippets(title, category, shortcut, content, created, updated) VALUES (?, ?, ?, ?, ?, ?)",
            (*values[:4], now, now),
        )

    def delete_snippet(self, snippet_id: int) -> None:
        self._write("DELETE FROM snippets WHERE id = ?", (int(snippet_id),))

    # --------------------------------------------------------------- workflows
    def list_workflows(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._query("SELECT * FROM workflows ORDER BY title COLLATE NOCASE")]

    def get_workflow(self, workflow_id: int) -> dict[str, Any] | None:
        row = self._query_one("SELECT * FROM workflows WHERE id = ?", (int(workflow_id),))
        return dict(row) if row else None

    def upsert_workflow(self, data: dict[str, Any]) -> int:
        now = time.time()
        workflow_id = data.get("id")
        if workflow_id:
            self._write(
                "UPDATE workflows SET title = ?, description = ?, steps_json = ?, updated = ? WHERE id = ?",
                (data["title"], data.get("description", ""), data["steps_json"], now, int(workflow_id)),
            )
            return int(workflow_id)
        return self._write(
            "INSERT INTO workflows(title, description, steps_json, created, updated) VALUES (?, ?, ?, ?, ?)",
            (data["title"], data.get("description", ""), data["steps_json"], now, now),
        )


    def insert_workflows_atomic(self, rows: Sequence[dict[str, Any]]) -> int:
        """Insert a validated import as one SQLite transaction."""
        now = time.time()
        try:
            conn = self.connection()
            with self._lock:
                with conn:
                    conn.executemany(
                        "INSERT INTO workflows(title, description, steps_json, created, updated) VALUES (?, ?, ?, ?, ?)",
                        [
                            (row["title"], row.get("description", ""), row["steps_json"], now, now)
                            for row in rows
                        ],
                    )
            return len(rows)
        except sqlite3.Error as exc:
            raise DatabaseError(f"Could not import workflows: {exc}") from exc

    def delete_workflow(self, workflow_id: int) -> None:
        self._write("DELETE FROM workflows WHERE id = ?", (int(workflow_id),))

    def vacuum(self) -> None:
        """Compact the database file."""
        try:
            conn = self.connection()
            with self._lock:
                conn.execute("VACUUM")
                conn.commit()
        except sqlite3.Error as exc:
            raise DatabaseError(f"Could not compact the database: {exc}") from exc

    # ------------------------------------------------------------------ close
    def close_thread_connection(self) -> None:
        """Close the current thread's connection before a pooled worker is reused."""
        if self._is_memory:
            return
        connection = getattr(self._local, "conn", None)
        if connection is not None:
            try:
                connection.close()
            finally:
                self._local.conn = None

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            if self._is_memory and self._shared is not None:
                self._shared.close()
                self._shared = None
            else:
                connection = getattr(self._local, "conn", None)
                if connection is not None:
                    connection.close()
                    self._local.conn = None
        except sqlite3.Error:
            log.debug("Ignoring error while closing the database", exc_info=True)


__all__ = ["Database", "SCHEMA_VERSION"]
