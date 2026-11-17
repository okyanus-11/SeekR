from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

from core.config_manager import ConfigManager
from features import applications as applications_module
from features import bookmarks, color_tools, emoji_search, power, process_manager, quicklook, screenshots, system_info
from features.applications import AppService
from features.clipboard import ClipboardProvider, ClipboardService
from features.files import FileIndexer, FileService, FilesProvider
from features.notes import NotesService
from features.quick_actions import QuickActionService
from features import quick_connect, dictionary
from features.quick_connect import build_ssh_argv, validate_profile
from core.workers import CancelToken


# ------------------------------------------------------------------------ files
@pytest.fixture
def indexed_files(config, db, tmp_path):
    root = tmp_path / "docs"
    (root / "notes").mkdir(parents=True)
    (root / "report.txt").write_text("quarterly report", encoding="utf-8")
    (root / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (root / "notes" / "plan.md").write_text("# plan", encoding="utf-8")
    (root / ".secret.txt").write_text("hidden", encoding="utf-8")
    (root / "node_modules").mkdir()
    (root / "node_modules" / "skip.js").write_text("ignored", encoding="utf-8")
    config.set("files.directories", [str(root)])
    service = FileService(config, db)
    stats = service.index()
    return service, stats, root


def test_file_index_finds_documents(indexed_files, config):
    service, stats, root = indexed_files
    assert stats["indexed"] >= 3
    results = service.search("report")
    assert results and results[0][1]["name"] == "report.txt"
    assert service.search("plan")
    assert not any(row["name"] == ".secret.txt" for _, row in service.search("secret"))
    assert not any(row["name"] == "skip.js" for _, row in service.search("skip"))


def test_file_search_does_not_widen_single_token_matches(config, db, monkeypatch):
    db.upsert_files(
        [
            {
                "path": f"/tmp/document-{index:06}.txt",
                "name": f"document-{index:06}.txt",
                "ext": ".txt",
            }
            for index in range(100)
        ]
    )
    service = FileService(config, db)
    original = db.file_candidates
    queries = []

    def track_candidates(query, limit=800, ext=None):
        queries.append(query)
        return original(query, limit=limit, ext=ext)

    monkeypatch.setattr(db, "file_candidates", track_candidates)

    results = service.search("document-000099")

    assert results and results[0][1]["name"] == "document-000099.txt"
    assert queries == ["document-000099"]


def test_file_search_still_widens_multiword_queries(config, db):
    db.upsert_files(
        [
            {
                "path": "/tmp/quarterly-report.txt",
                "name": "quarterly-report.txt",
                "ext": ".txt",
            }
        ]
    )
    service = FileService(config, db)

    results = service.search("quarterly rep")

    assert results and results[0][1]["name"] == "quarterly-report.txt"


def test_file_extension_filter(indexed_files):
    service, _stats, _root = indexed_files
    results = service.search("ext:png")
    assert results and results[0][1]["ext"] == ".png"


def test_file_suggestions(indexed_files):
    service, _stats, _root = indexed_files
    assert service.stats()["count"] >= 3
    assert isinstance(service.suggestions(3), list)


def test_file_index_cancellation(config, db, tmp_path):
    root = tmp_path / "big"
    root.mkdir()
    (root / "a.txt").write_text("a", encoding="utf-8")
    config.set("files.directories", [str(root)])
    token = CancelToken()
    token.cancel()
    stats = FileIndexer(config, db).index(token=token)
    assert stats["cancelled"]
    assert stats["indexed"] == 0


def test_files_provider_results(indexed_files, config, db, hooks, monkeypatch):
    service, _stats, _root = indexed_files
    provider = FilesProvider(config, db, hooks, service)
    results = provider.search("report", 5)
    assert results
    assert results[0].category == "File"
    assert results[0].copy_text.endswith("report.txt")
    assert any(action.label == "Open containing folder" for action in results[0].actions)
    monkeypatch.setattr("features.files.util.open_path_platform", lambda path: (True, f"Opened {path}"))
    provider.search("report", 5)[0].execute()
    assert any(call[0] == "notify" and call[1][1] == "info" for call in hooks.calls)
    assert db.history("file")


# ----------------------------------------------------------------- applications
def test_scan_desktop_entries(config, db, tmp_path, monkeypatch):
    menu = tmp_path / "applications"
    menu.mkdir()
    if os.name == "nt":
        # Windows scans .lnk shortcuts; the name comes from the file stem.
        (menu / "Super Editor.lnk").write_bytes(b"shortcut")
        hidden_count = 0
    else:
        (menu / "editor.desktop").write_text(
            "[Desktop Entry]\nType=Application\nName=Super Editor\nExec=/bin/echo %U\nIcon=editor\n",
            encoding="utf-8",
        )
        (menu / "hidden.desktop").write_text(
            "[Desktop Entry]\nType=Application\nName=Hidden\nExec=/bin/true\nNoDisplay=true\n",
            encoding="utf-8",
        )
        hidden_count = 1
    monkeypatch.setattr(applications_module, "start_menu_directories", lambda: [menu])
    service = AppService(config, db)
    entries = service.scan()
    names = [entry["name"] for entry in entries]
    assert "Super Editor" in names
    if os.name != "nt":
        assert "Hidden" not in names
    expected_found = 1
    stats = service.refresh()
    assert stats["found"] == expected_found
    assert db.count_apps() == expected_found
    assert service.search("editor")
    assert service.search("super ed")


def test_application_launch_records_history(config, db, tmp_path, monkeypatch):
    menu = tmp_path / "applications"
    menu.mkdir()
    if os.name == "nt":
        (menu / "Echo App.lnk").write_bytes(b"shortcut")
    else:
        (menu / "echo.desktop").write_text(
            "[Desktop Entry]\nType=Application\nName=Echo App\nExec=/bin/echo hello\n",
            encoding="utf-8",
        )
    monkeypatch.setattr(applications_module, "start_menu_directories", lambda: [menu])
    service = AppService(config, db)
    service.refresh()
    app = service.search("echo")[0]
    if os.name == "nt":
        # .lnk files have no Exec command; launch uses os.startfile which
        # needs a real shortcut. Skip the launch assertion on Windows since
        # we cannot create a valid .lnk in a test fixture.
        pytest.skip("Launching a synthetic .lnk requires a real Windows shortcut")
    ok, message = service.launch(app)
    assert ok, message
    assert db.history("app")


# -------------------------------------------------------------------- clipboard
def test_clipboard_service(config, db):
    service = ClipboardService(config, db)
    config.set("privacy.clipboard_history", True)
    assert service.capture("hello world")
    assert service.capture("hello world") is None  # duplicate suppressed
    assert service.capture("second entry")
    assert len(service.items()) == 2
    service.pin(service.items()[0]["id"], True)
    assert service.count() == 2
    service.clear(keep_pinned=True)
    assert service.count() == 1
    config.set("clipboard.enabled", False)
    assert service.capture("ignored") is None


def test_clipboard_capture_is_off_by_default(config, db):
    service = ClipboardService(config, db)
    assert not service.enabled
    assert service.capture("not opted in") is None
    assert service.count() == 0


def test_legacy_clipboard_config_disables_capture_without_deleting_history(config, db):
    old_entry = db.add_clipboard("previously stored text")
    config.path.write_text(
        '{"clipboard":{"enabled":true},"privacy":{"clipboard_history":true}}',
        encoding="utf-8",
    )
    migrated = ConfigManager(config.path)
    service = ClipboardService(migrated, db)

    assert not service.enabled
    assert service.capture("new text") is None
    assert service.count() == 1
    assert service.items()[0]["id"] == old_entry
    assert service.items()[0]["text"] == "previously stored text"


def test_clipboard_opt_in_enables_capture(config, db):
    service = ClipboardService(config, db)
    config.set("privacy.clipboard_history", True)
    assert config.get("privacy.clipboard_history_consent") is True
    assert config.get("clipboard.enabled") is True
    assert service.enabled
    assert service.capture("opted-in text")["text"] == "opted-in text"


def test_disabled_clipboard_capture_keeps_existing_search_access(config, db, hooks):
    db.add_clipboard("existing entry")
    service = ClipboardService(config, db)
    results = ClipboardProvider(config, db, hooks, service).search("", 5)
    assert [result.title for result in results] == ["existing entry"]


def test_clipboard_skips_private_keys(config, db):
    service = ClipboardService(config, db)
    pem = "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----"
    assert service.capture(pem) is None


# ------------------------------------------------------------------------ notes
def test_notes_service(config, db):
    service = NotesService(config, db)
    note_id = service.create("", "First line\nmore")
    note = service.get(note_id)
    assert note["title"] == "First line"
    service.update(note_id, body="Updated")
    assert service.get(note_id)["body"] == "Updated"
    assert service.toggle_pin(note_id)
    assert service.list("updated")
    service.delete(note_id)
    assert service.count() == 0


# ---------------------------------------------------------------- quick actions
def test_quick_actions_validation(config, db, hooks, tmp_path):
    service = QuickActionService(config, db, hooks)
    service.seed_defaults()
    assert service.actions()
    ok, _ = service.save({"title": "Bad", "kind": "open_dir", "target": str(tmp_path / "missing")})
    assert not ok
    ok, _ = service.save({"title": "Bad", "kind": "open_url", "target": "ftp://example.com"})
    assert not ok
    ok, _ = service.save({"title": "Unknown", "kind": "nonsense", "target": "x"})
    assert not ok
    ok, message = service.save({"title": "Folder", "kind": "open_dir", "target": str(tmp_path)})
    assert ok, message
    action = next(item for item in service.actions() if item["title"] == "Folder")
    ok, _ = service.execute(action)
    assert ok
    assert any(call[0] == "open_path" for call in hooks.calls)


def test_quick_action_copy_text(config, db, hooks):
    service = QuickActionService(config, db, hooks)
    ok, _ = service.save({"title": "Snippet", "kind": "copy_text", "target": "hello"})
    assert ok
    action = next(item for item in service.actions() if item["title"] == "Snippet")
    service.execute(action)
    assert ("copy_text", ("hello",)) in hooks.calls


# ----------------------------------------------------------------- quick connect
def test_ssh_validation_and_command():
    ok, message = validate_profile({"name": "x", "host": "host; rm -rf", "port": 22})
    assert not ok
    ok, _ = validate_profile({"name": "", "host": "host"})
    assert not ok
    ok, _ = validate_profile({"name": "ok", "host": "example.com", "port": 70000})
    assert not ok
    ok, message = validate_profile({"name": "ok", "host": "example.com", "port": 2222, "user": "me"})
    assert ok, message
    argv = build_ssh_argv({"host": "example.com", "port": 2222, "user": "me", "key_path": ""})
    assert argv[0] == "ssh"
    assert "-p" in argv and "2222" in argv
    assert "me@example.com" in argv


def test_windows_ssh_fallback_passes_metacharacters_as_argv(monkeypatch):
    captured = {}

    def fake_popen(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs

    monkeypatch.setattr(quick_connect.os, "name", "nt")
    monkeypatch.setattr(quick_connect.util, "which", lambda executable: {
        "ssh": "C:\\Windows\\System32\\OpenSSH\\ssh.exe",
        "wt.exe": None,
        "wt": None,
    }.get(executable))
    monkeypatch.setattr(quick_connect.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(quick_connect.subprocess, "CREATE_NEW_CONSOLE", 0x10, raising=False)

    ok, message = quick_connect.launch_profile({
        "host": "example.com",
        "extra_args": '-o "ProxyCommand=echo safe & whoami"',
    })

    assert ok, message
    assert captured["args"] == [
        "C:\\Windows\\System32\\OpenSSH\\ssh.exe",
        "-o", "ProxyCommand=echo safe & whoami", "example.com",
    ]
    assert captured["kwargs"] == {"creationflags": 0x10, "close_fds": True}


# ----------------------------------------------------------------- system info
def test_system_snapshot_is_real():
    data = system_info.snapshot()
    assert set(data) >= {"cpu", "memory", "disks", "network", "os", "gpu", "uptime"}
    assert data["os"]["system"]
    assert data["network"]["hostname"]
    assert data["memory"]["total"] is None or data["memory"]["total"] > 0
    cpu = data["cpu"]["percent"]
    assert cpu is None or (0 <= cpu <= 100)
    assert isinstance(data["disks"], list)


def test_system_provider(config, db, hooks):
    from features.system_info import SystemInfoProvider

    provider = SystemInfoProvider(config, db, hooks)
    results = provider.search("", 10)
    assert results
    assert all(result.category == "System" for result in results)
    copy_values = [result.copy_text for result in results if result.copy_text]
    assert copy_values


# ---------------------------------------------------------------------- processes
def test_process_listing():
    processes = process_manager.list_processes(limit=5)
    assert processes
    assert {"pid", "name", "cpu", "memory"} <= set(processes[0])
    details = process_manager.process_details(os.getpid())
    assert details and details["pid"] == os.getpid()


def test_process_termination():
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        time.sleep(0.2)
        ok, message = process_manager.terminate_process(child.pid)
        assert ok, message
    finally:
        if child.poll() is None:
            child.kill()


# -------------------------------------------------------------------------- misc
def test_emoji_search():
    assert any(emoji == "🔥" for emoji, _ in emoji_search.search_emojis("fire"))
    assert emoji_search.search_emojis("heart")
    assert len(emoji_search.search_emojis("")) > 0
    assert emoji_search.search_emojis("zzzzzz") == []


def test_color_formats():
    formats = color_tools.__dict__  # ensure module imports cleanly
    assert formats is not None


def test_bookmarks_graceful():
    result = bookmarks.load_bookmarks(refresh=True)
    assert isinstance(result, list)
    assert isinstance(bookmarks.search_bookmarks("github"), list)



def test_chromium_bookmark_backup_is_used_when_primary_is_invalid(tmp_path):
    profile = tmp_path / "Chrome"
    profile.mkdir()
    (profile / "Bookmarks").write_text("{broken", encoding="utf-8")
    backup = {
        "roots": {
            "bookmark_bar": {
                "type": "folder",
                "children": [{"type": "url", "name": "SeekR", "url": "https://example.com"}],
            }
        }
    }
    (profile / "Bookmarks.bak").write_text(json.dumps(backup), encoding="utf-8")
    result = bookmarks._read_chromium_bookmarks("Chrome", profile)
    assert result == [{"browser": "Chrome", "title": "SeekR", "url": "https://example.com"}]


def test_firefox_bookmarks_snapshot_includes_live_wal_data(tmp_path):
    profile = tmp_path / "firefox-profile"
    profile.mkdir()
    connection = sqlite3.connect(profile / "places.sqlite")
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.executescript(
            "CREATE TABLE moz_places (id INTEGER PRIMARY KEY, url TEXT);"
            "CREATE TABLE moz_bookmarks (id INTEGER PRIMARY KEY, type INTEGER, fk INTEGER, title TEXT);"
        )
        connection.execute("INSERT INTO moz_places(id, url) VALUES(1, 'https://example.com/live')")
        connection.execute(
            "INSERT INTO moz_bookmarks(id, type, fk, title) VALUES(1, 1, 1, 'Live bookmark')"
        )
        connection.commit()
        result = bookmarks._read_firefox_bookmarks(profile)
        assert result == [
            {"browser": "Firefox", "title": "Live bookmark", "url": "https://example.com/live"}
        ]
    finally:
        connection.close()


def test_dictionary_cache_is_available_offline(tmp_path, monkeypatch):
    cached = {
        "word": "algorithm",
        "phonetic": "",
        "meanings": [{"partOfSpeech": "noun", "definition": "A finite set of steps.", "example": "", "synonyms": []}],
    }
    cache_path = tmp_path / "dictionary-cache.json"
    monkeypatch.setattr(dictionary, "_fetch_definition", lambda word, timeout: cached)
    assert dictionary.lookup("Algorithm", cache_path=cache_path) == cached

    def offline(_word, _timeout):
        raise dictionary.DictionaryError("offline")

    monkeypatch.setattr(dictionary, "_fetch_definition", offline)
    assert dictionary.lookup("algorithm", cache_path=cache_path) == cached


def test_resolve_ssh_client_finds_standard_windows_installation(tmp_path, monkeypatch):
    monkeypatch.setattr(quick_connect.util, "which", lambda _name: None)
    monkeypatch.setattr(quick_connect.os, "name", "nt")
    monkeypatch.setenv("WINDIR", str(tmp_path))
    executable = tmp_path / "System32" / "OpenSSH" / "ssh.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"")
    assert quick_connect.resolve_ssh_client() == str(executable)


def test_windows_gpu_engine_counters_are_aggregated_by_adapter(monkeypatch):
    payload = [
        {"InstanceName": "luid_0x1_phys_0_eng_0_engtype_3D", "CookedValue": 25},
        {"InstanceName": "luid_0x1_phys_0_eng_1_engtype_Copy", "CookedValue": 35},
        {"InstanceName": "luid_0x2_phys_1_eng_0_engtype_3D", "CookedValue": 18},
    ]
    monkeypatch.setattr(system_info, "_run_quiet", lambda *args, **kwargs: json.dumps(payload))
    assert system_info._windows_gpu_engine_usage() == {0: 60.0, 1: 18.0}

def test_power_graceful():
    assert isinstance(power.supported(), bool)
    schemes = power.list_schemes()
    assert isinstance(schemes, list)
    ok, message = power.set_scheme("")
    assert not ok and message


def test_quicklook_text_and_kind(tmp_path, qapp):
    text_file = tmp_path / "sample.txt"
    text_file.write_text("hello quicklook", encoding="utf-8")
    assert quicklook.preview_kind(text_file) == "text"
    assert "hello quicklook" in quicklook.load_text_preview(text_file)
    assert quicklook.file_summary(text_file)["size"] > 0

    from PySide6.QtGui import QPixmap

    image_path = tmp_path / "image.png"
    pixmap = QPixmap(20, 10)
    pixmap.fill()
    assert pixmap.save(str(image_path), "PNG")
    assert quicklook.preview_kind(image_path) == "image"
    assert not quicklook.load_image_preview(image_path).isNull()


def test_screenshot_handles_environment(config):
    ok, path, error = screenshots.save_screenshot(config)
    assert ok or error
    if ok:
        assert Path(path).exists()



def test_save_pixmap_uses_configured_screenshot_directory(config, tmp_path, qapp):
    from PySide6.QtGui import QPixmap

    config.set("screenshots.directory", str(tmp_path))
    pixmap = QPixmap(24, 16)
    pixmap.fill()
    ok, path, error = screenshots.save_pixmap(config, pixmap)
    assert ok, error
    assert Path(path).parent == tmp_path
    assert Path(path).is_file()

def test_screenshot_provider(config, db, hooks):
    from features.screenshots import ScreenshotProvider

    provider = ScreenshotProvider(config, db, hooks)
    results = provider.search("", 5)
    assert results and results[0].category == "Screenshot"
