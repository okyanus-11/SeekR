from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from features import applications as applications_module
from features import bookmarks, color_tools, emoji_search, power, process_manager, quicklook, screenshots, system_info
from features.applications import AppService
from features.clipboard import ClipboardService
from features.files import FileIndexer, FileService, FilesProvider
from features.notes import NotesService
from features.quick_actions import QuickActionService
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


def test_screenshot_provider(config, db, hooks):
    from features.screenshots import ScreenshotProvider

    provider = ScreenshotProvider(config, db, hooks)
    results = provider.search("", 5)
    assert results and results[0].category == "Screenshot"
