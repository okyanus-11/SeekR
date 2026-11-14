from __future__ import annotations

import time

from core.database import Database


def test_application_upsert_and_search(db):
    db.upsert_apps(
        [
            {"name": "Visual Studio Code", "path": r"C:\Apps\code.exe"},
            {"name": "Discord", "path": r"C:\Apps\discord.exe"},
        ]
    )
    assert db.count_apps() == 2
    found = db.app_candidates("visual")
    assert found[0]["name"] == "Visual Studio Code"
    db.record_app_launch(r"C:\Apps\code.exe")
    recent = db.recent_apps()
    assert recent and recent[0]["name"] == "Visual Studio Code"
    assert db.frequent_apps()[0]["use_count"] == 1

    # Upsert must not duplicate rows for the same path.
    db.upsert_apps([{"name": "VS Code", "path": r"C:\Apps\code.exe"}])
    assert db.count_apps() == 2
    assert db.get_app(1)["name"] == "VS Code"


def test_application_prune(db):
    db.upsert_apps([{"name": "A", "path": "a"}, {"name": "B", "path": "b"}])
    db.upsert_apps([{"name": "A", "path": "a"}], prune_missing=True)
    assert db.count_apps() == 1


def test_file_index_and_queries(db):
    db.upsert_files(
        [
            {"path": "/tmp/report.pdf", "name": "report.pdf", "dir": "/tmp", "ext": ".pdf", "size": 100, "mtime": time.time()},
            {"path": "/tmp/notes.txt", "name": "notes.txt", "dir": "/tmp", "ext": ".txt", "size": 10, "mtime": time.time()},
            {"path": "/tmp/projects", "name": "projects", "dir": "/tmp", "is_dir": True},
        ]
    )
    assert db.count_files() == 3
    assert db.file_candidates("rep")[0]["name"] == "report.pdf"
    assert [row["name"] for row in db.file_candidates("", ext=".txt")] == ["notes.txt"]
    assert db.files_by_extension(".txt")[0]["name"] == "notes.txt"
    assert db.recent_files(limit=5)
    db.delete_files_under("/tmp")
    assert db.count_files() == 0


def test_clipboard_history_rules(db):
    first = db.add_clipboard("hello")
    assert first
    # Identical newest entry is skipped.
    assert db.add_clipboard("hello") is None
    second = db.add_clipboard("world")
    assert second
    db.set_clipboard_pinned(first, True)
    items = db.clipboard_items()
    assert items[0]["id"] == first and items[0]["pinned"] == 1
    db.clear_clipboard(keep_pinned=True)
    remaining = db.clipboard_items()
    assert [item["id"] for item in remaining] == [first]
    db.delete_clipboard(first)
    assert db.clipboard_count() == 0


def test_clipboard_prune_keeps_pinned(db):
    pinned = db.add_clipboard("pinned")
    db.set_clipboard_pinned(pinned, True)
    for index in range(5):
        db.add_clipboard(f"entry {index}")
    db.prune_clipboard(2)
    items = db.clipboard_items()
    # The pinned entry is exempt; the two newest unpinned entries are kept.
    assert len(items) == 3
    assert any(item["id"] == pinned for item in items)


def test_notes_crud(db):
    note_id = db.create_note("Shopping", "Milk\nEggs")
    assert note_id > 0
    note = db.get_note(note_id)
    assert note["title"] == "Shopping"
    db.update_note(note_id, body="Milk", pinned=True)
    note = db.get_note(note_id)
    assert note["body"] == "Milk" and note["pinned"] == 1
    assert db.notes("shop")
    assert db.note_count() == 1
    db.delete_note(note_id)
    assert db.note_count() == 0


def test_history_and_pruning(db):
    db.add_history("search", "seekr")
    db.add_history("search", "calculator")
    db.add_history("app", "Discord")
    assert len(db.history("search")) == 2
    assert db.recent_queries()[0] == "calculator"
    db.prune_history(0)
    db.clear_history(["app"])
    assert db.history("app") == []
    db.clear_history()
    assert db.history() == []


def test_custom_commands_crud(db):
    db.upsert_custom_command(
        {"name": "Ping", "command": "ping", "args": "-n 1", "description": "Ping", "aliases": "net", "confirm": True}
    )
    rows = db.list_custom_commands()
    assert len(rows) == 1 and rows[0]["name"] == "Ping"
    db.upsert_custom_command({"id": rows[0]["id"], "name": "Ping", "command": "ping", "args": "-n 2"})
    assert db.list_custom_commands()[0]["args"] == "-n 2"
    db.delete_custom_command(rows[0]["id"])
    assert db.list_custom_commands() == []


def test_ssh_profiles_and_actions(db):
    db.upsert_ssh_profile({"name": "Home", "host": "192.168.1.2", "port": 2222, "user": "me"})
    profiles = db.list_ssh_profiles()
    assert profiles[0]["host"] == "192.168.1.2" and profiles[0]["port"] == 2222
    db.delete_ssh_profile(profiles[0]["id"])
    assert db.list_ssh_profiles() == []

    db.upsert_quick_action({"title": "Docs", "kind": "open_dir", "target": "/tmp", "description": ""})
    actions = db.list_quick_actions()
    assert actions[0]["title"] == "Docs"
    db.delete_quick_action(actions[0]["id"])
    assert db.list_quick_actions() == []


def test_meta_and_vacuum(tmp_path):
    db = Database(tmp_path / "meta.db")
    db.set_meta("apps_last_index", 123)
    assert db.get_meta("apps_last_index") == "123"
    assert db.get_meta("missing", "fallback") == "fallback"
    db.vacuum()
    db.close()


def test_memory_database():
    db = Database(":memory:")
    db.add_clipboard("memory")
    assert db.clipboard_count() == 1
    db.close()
