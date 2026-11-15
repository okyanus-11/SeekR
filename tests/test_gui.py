"""Headless GUI smoke tests (offscreen Qt platform)."""

from __future__ import annotations

import pytest

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QGuiApplication, QKeyEvent
from PySide6.QtWidgets import QLabel

from core.application import SeekRApplication
from core.config_manager import ConfigManager
from core.database import Database
from core.models import ResultAction
from core.search_engine import SearchProvider


class DummyProvider(SearchProvider):
    id = "gui_test"
    title = "GUI test"
    keyword = "gui"
    weight = 2.0
    auto = True

    def search(self, query, limit):
        if not query.strip():
            return []
        return [
            self.make_result(
                title=f"GUI result {index}",
                score=0.9,
                subtitle=f"row {index}",
                primary=lambda index=index: None,
                copy_text=f"copy {index}",
                actions=[ResultAction(label="Secondary", callback=lambda index=index: None)],
            )
            for index in range(3)
        ]


@pytest.fixture(scope="module")
def controller(qapp, tmp_path_factory):
    directory = tmp_path_factory.mktemp("gui")
    config = ConfigManager(directory / "config.json")
    config.set("files.auto_index", False)
    config.set("applications.refresh_on_start", False)
    config.set("appearance.animations", False)
    config.set("general.show_tray_icon", False)
    db = Database(directory / "gui.db")
    app = SeekRApplication(qapp, config, db)
    app._create_tray = lambda: None  # no tray in headless environments
    app._start_clipboard_monitor = lambda: None
    app._auto_index = lambda: None
    app.start(show_window=False, register_hotkey=False)
    yield app
    app.shutdown()


def test_launcher_opens_and_searches(qapp, controller):
    controller.show_launcher()
    qapp.processEvents()
    launcher = controller.launcher
    assert launcher is not None
    assert launcher.isVisible()

    launcher.set_query("calc: 6*7")
    qapp.processEvents()
    result = launcher.current_result()
    assert result is not None
    assert result.title == "42"

    controller.engine.register(DummyProvider(controller.config, controller.db, controller))
    launcher.set_query("gui test")
    qapp.processEvents()
    assert len(launcher._results) >= 3
    assert launcher.current_result().title.startswith("GUI result")

    # Keyboard handling: arrow keys move the selection.
    event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier)
    assert launcher.eventFilter(launcher.search_input, event) is True
    first = launcher.current_result().title
    launcher._move_selection(1)
    assert launcher.current_result().title != first

    # Tab cycles actions and Escape clears the action selection.
    tab_event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.KeyboardModifier.NoModifier)
    assert launcher.eventFilter(launcher.search_input, tab_event) is True
    assert launcher._action_index == 0
    assert launcher.action_label.isVisible()
    escape = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    assert launcher.eventFilter(launcher.search_input, escape) is True
    assert launcher._action_index is None


def test_icon_store_evicts_least_recently_used_paths(qapp, tmp_path):
    from PySide6.QtGui import QIcon

    from ui.icons import IconStore

    class CountingIconProvider:
        def __init__(self):
            self.calls = {}

        def icon(self, file_info):
            path = file_info.fileName()
            self.calls[path] = self.calls.get(path, 0) + 1
            return QIcon()

    store = IconStore()
    provider = CountingIconProvider()
    store._provider = provider
    paths = [tmp_path / f"icon-{index}.exe" for index in range(513)]
    for path in paths[:512]:
        path.touch()
        store.icon_for(str(path))
    paths[512].touch()

    store.icon_for(str(paths[0]))
    store.icon_for(str(paths[512]))
    store.icon_for(str(paths[0]))
    store.icon_for(str(paths[1]))

    assert len(store._cache) == 512
    assert provider.calls[paths[0].name] == 1
    assert provider.calls[paths[1].name] == 2


def test_launcher_execution_copies_and_hides(qapp, controller):
    launcher = controller.launcher
    launcher.show_launcher()
    launcher.set_query("calc: 2+3")
    qapp.processEvents()
    assert launcher.current_result().title == "5"
    launcher._execute_current()
    qapp.processEvents()
    clipboard = QGuiApplication.clipboard()
    assert clipboard is not None
    assert clipboard.text() == "5"


def test_launcher_hides_on_escape(qapp, controller):
    launcher = controller.launcher
    launcher.show_launcher()
    qapp.processEvents()
    escape = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    launcher.eventFilter(launcher.search_input, escape)
    qapp.processEvents()
    assert not launcher.isVisible()


def test_ctrl_copy_action(qapp, controller):
    launcher = controller.launcher
    launcher.show_launcher()
    launcher.set_query("gui test")
    qapp.processEvents()
    launcher._copy_current()
    assert QGuiApplication.clipboard().text().startswith("copy")


def test_settings_window_pages(qapp, controller):
    controller.open_settings("general")
    qapp.processEvents()
    window = controller._settings_window
    assert window is not None
    assert len(window.pages) == 13
    for key in ("general", "appearance", "search", "applications", "files", "web", "calculator", "commands", "clipboard", "privacy", "advanced", "plugins", "about"):
        assert key in window.pages

    window.open_page("plugins")
    assert window.stack.currentWidget() is window.pages["plugins"]
    from ui.components import InfoBanner

    banner = window.pages["plugins"].findChild(InfoBanner)
    assert banner is not None
    texts = [item.text() for item in banner.findChildren(QLabel)]
    assert any("PLUGIN MARKETPLACE" in text for text in texts)
    assert any("COMING SOON" in text for text in texts)
    assert any("Extend SeekR" in text for text in texts)
    window.open_page("clipboard")
    clipboard_text = " ".join(
        item.text() for item in window.pages["clipboard"].findChildren(QLabel)
    )
    assert "unencrypted" in clipboard_text
    assert "SQLite" in clipboard_text

    window.open_page("appearance")
    controller.config.set("appearance.theme", "catppuccin_mocha")
    qapp.processEvents()
    assert "#1e1e2e" in qapp.styleSheet()

    reloaded = ConfigManager(controller.config.path)
    assert reloaded.get("appearance.theme") == "catppuccin_mocha"


def test_tools_window_pages(qapp, controller):
    controller.open_tools("calculator")
    qapp.processEvents()
    window = controller._tools_window
    assert window is not None
    assert len(window.pages) == 14
    window.open_page("notes")
    assert window.stack.currentWidget() is window.pages["notes"]
    window.open_page("developer")
    assert window.stack.currentWidget() is window.pages["developer"]
    window.open_page("dictionary")
    assert window.stack.currentWidget() is window.pages["dictionary"]


def test_tools_clipboard_and_notes(qapp, controller):
    service = controller.clipboard_service
    controller.config.set("privacy.clipboard_history", True)
    service.capture("settings smoke test")
    controller.open_tools("clipboard")
    qapp.processEvents()
    window = controller._tools_window
    clipboard_page = window.pages["clipboard"]
    clipboard_page.reload()
    assert clipboard_page.list.count() >= 1

    notes_service = controller.notes_service
    note_id = notes_service.create("Smoke note", "Body text")
    controller.open_notes(note_id)
    qapp.processEvents()
    notes_page = window.pages["notes"]
    notes_page.select_note(note_id)
    qapp.processEvents()
    assert notes_page.title_edit.text() == "Smoke note"


def test_theme_stylesheet_contains_widgets(controller):
    stylesheet = controller.app.styleSheet()
    assert "QLineEdit" in stylesheet
    assert "QListWidget#ResultList" in stylesheet


def test_notifications_and_hooks(qapp, controller):
    controller.notify("hello from tests")
    assert controller.launcher.status_label.text() == "hello from tests"
    assert controller.copy_text("clipboard value")
    assert QGuiApplication.clipboard().text() == "clipboard value"


def test_settings_persist_switch_toggle(qapp, controller):
    config = controller.config
    config.set("search.typo_tolerance", False)
    reloaded = ConfigManager(config.path)
    assert reloaded.get("search.typo_tolerance") is False
    config.set("search.typo_tolerance", True)
