"""Headless GUI smoke tests (offscreen Qt platform)."""

from __future__ import annotations

import gc
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QGuiApplication, QKeyEvent
from PySide6.QtWidgets import QLabel

from core.application import SeekRApplication
from core.config_manager import ConfigManager
from core.database import Database
from core.models import ResultAction, SearchResult
from core.search_engine import SearchProvider
from ui.themes import palette_for


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


def wait_for_search(qapp, launcher, timeout: float = 3.0):
    """Process queued Qt signals until the latest background search completes."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if launcher._displayed_query == launcher.search_input.text():
            return
        time.sleep(0.005)
    pytest.fail("Launcher search did not complete before the timeout")


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



def test_run_async_retains_worker_until_callback_delivery(qapp):
    from PySide6.QtCore import QThreadPool

    from core.workers import _ACTIVE_WORKERS, run_async

    pool = QThreadPool()
    completed = []
    worker = run_async(lambda: "finished", on_finished=completed.append, pool=pool)
    worker_id = id(worker)
    del worker
    gc.collect()

    assert pool.waitForDone(3000)
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline and not completed:
        qapp.processEvents()
        time.sleep(0.005)

    # Process the queued reaper signal as well as the user callback.
    qapp.processEvents()
    assert completed == ["finished"]
    assert all(id(item) != worker_id for item in _ACTIVE_WORKERS)



def test_run_async_cleanup_precedes_completion_callback(qapp):
    from PySide6.QtCore import QThreadPool

    from core.workers import run_async

    pool = QThreadPool()
    events = []
    worker = run_async(
        lambda: "done",
        on_cleanup=lambda: events.append("cleanup"),
        on_finished=lambda _result: events.append("finished"),
        pool=pool,
    )
    assert pool.waitForDone(3000)
    qapp.processEvents()
    assert events == ["cleanup", "finished"]


def test_launcher_opens_and_searches(qapp, controller):
    controller.show_launcher()
    qapp.processEvents()
    launcher = controller.launcher
    assert launcher is not None
    assert launcher.isVisible()

    launcher.set_query("calc: 6*7")
    wait_for_search(qapp, launcher)
    result = launcher.current_result()
    assert result is not None
    assert result.title == "42"

    controller.engine.register(DummyProvider(controller.config, controller.db, controller))
    launcher.set_query("gui test")
    wait_for_search(qapp, launcher)
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



def test_launcher_show_interrupts_an_in_progress_hide(qapp, controller):
    """A fast re-open must cancel the old fade instead of fading back out."""
    launcher = controller.launcher
    config = controller.config
    old_animations = config.get("appearance.animations", False)
    old_duration = config.get("appearance.animation_duration", 150)
    config.set("appearance.animations", True)
    config.set("appearance.animation_duration", 120)
    try:
        launcher.show_launcher()
        qapp.processEvents()
        launcher.hide_launcher()
        qapp.processEvents()
        launcher.show_launcher()

        deadline = time.monotonic() + 0.3
        while time.monotonic() < deadline:
            qapp.processEvents()
            time.sleep(0.005)

        assert launcher.isVisible()
        assert not launcher._hiding
        assert launcher.windowOpacity() > 0.8
    finally:
        config.set("appearance.animations", old_animations)
        config.set("appearance.animation_duration", old_duration)
        launcher._stop_window_animation()
        launcher._hiding = False
        launcher.setWindowOpacity(float(config.get("appearance.opacity", 0.98)))


def test_launcher_coalesces_rapid_searches_to_latest_query(qapp, controller):
    """Typing during a slow query must not queue every intermediate query."""
    launcher = controller.launcher
    original_engine = launcher.engine
    started = threading.Event()
    release = threading.Event()
    calls = []

    class SlowEngine:
        def search(self, query):
            calls.append(query)
            if query == "first":
                started.set()
                release.wait(3)
            return [SearchResult(title=query, category="Test", score=1.0)]

    launcher.engine = SlowEngine()
    try:
        launcher.search_input.setText("first")
        launcher._debouncer.cancel()
        launcher._run_search()
        assert started.wait(2), "first search worker did not start"

        for query in ("middle", "latest"):
            launcher.search_input.setText(query)
            launcher._debouncer.cancel()
            launcher._run_search()

        release.set()
        wait_for_search(qapp, launcher)
        assert calls == ["first", "latest"]
        assert launcher.current_result() is not None
        assert launcher.current_result().title == "latest"
    finally:
        release.set()
        launcher.engine = original_engine


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



def test_launcher_widgets_survive_settings_and_theme_refresh(qapp, controller):
    launcher = controller.launcher
    widgets = launcher.launcher_widgets
    launcher.show_launcher()
    qapp.processEvents()

    original_theme = controller.config.get("appearance.theme", "dark")
    try:
        for cycle in range(3):
            for key in ("clock", "weather", "system", "meme"):
                controller.config.set(f"widgets.{key}_enabled", False)
            widgets.refresh_settings()
            qapp.processEvents()
            assert not widgets.left_column.isVisible()
            assert not widgets.right_column.isVisible()

            for key in ("clock", "weather", "system", "meme"):
                controller.config.set(f"widgets.{key}_enabled", True)
            widgets.refresh_settings()
            qapp.processEvents()
            assert widgets.left_column.isVisible()
            assert widgets.right_column.isVisible()
            assert all(card.isVisible() for card in widgets._cards.values())
            assert all(card.parentWidget() in (widgets.left_column, widgets.right_column)
                       for card in widgets._cards.values())

            theme = "light" if cycle % 2 == 0 else "dark"
            controller.config.set("appearance.theme", theme)
            widgets.refresh_settings()
            qapp.processEvents()
            expected = palette_for(theme)["surface"]
            assert expected in widgets.clock.styleSheet()
            assert all(card.isVisible() for card in widgets._cards.values())
    finally:
        controller.config.set("appearance.theme", original_theme)
        widgets.refresh_settings()
        for key in ("clock", "weather", "system", "meme"):
            controller.config.set(f"widgets.{key}_enabled", True)
        widgets.refresh_settings()



def test_widget_polling_pauses_when_launcher_is_hidden(qapp, controller):
    launcher = controller.launcher
    widgets = launcher.launcher_widgets
    launcher.show_launcher()
    qapp.processEvents()
    assert widgets._active
    assert widgets.clock.timer.isActive()
    assert widgets.system.timer.isActive()

    launcher.hide_launcher()
    qapp.processEvents()
    assert not widgets._active
    assert not widgets.clock.timer.isActive()
    assert not widgets.system.timer.isActive()
    assert not widgets.weather.timer.isActive()
    assert not widgets.meme.day_timer.isActive()

    launcher.show_launcher()
    qapp.processEvents()
    assert widgets._active
    assert widgets.clock.timer.isActive()
    assert widgets.system.timer.isActive()

def test_launcher_execution_copies_and_hides(qapp, controller):
    launcher = controller.launcher
    launcher.show_launcher()
    launcher.set_query("calc: 2+3")
    wait_for_search(qapp, launcher)
    assert launcher.current_result().title == "5"
    launcher._execute_current()
    qapp.processEvents()
    clipboard = QGuiApplication.clipboard()
    assert clipboard is not None
    assert clipboard.text() == "5"



def test_enter_waits_for_results_for_the_current_query(qapp, controller):
    launcher = controller.launcher
    launcher.show_launcher()
    launcher.set_query("calc: 2+3")
    wait_for_search(qapp, launcher)
    assert launcher.current_result().title == "5"

    # Change the query and press Enter before the debounced/background search
    # has delivered its result. The old "5" result must never be executed.
    launcher.search_input.setText("calc: 7*8")
    launcher._execute_current()

    deadline = time.monotonic() + 3.0
    clipboard = QGuiApplication.clipboard()
    while time.monotonic() < deadline and clipboard.text() != "56":
        qapp.processEvents()
        time.sleep(0.005)

    assert launcher._displayed_query == "calc: 7*8"
    assert clipboard.text() == "56"


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
    wait_for_search(qapp, launcher)
    launcher._copy_current()
    assert QGuiApplication.clipboard().text().startswith("copy")


def test_settings_window_pages(qapp, controller):
    controller.open_settings("general")
    qapp.processEvents()
    window = controller._settings_window
    assert window is not None
    assert len(window.pages) == 14
    for key in ("general", "appearance", "search", "applications", "files", "web", "calculator", "commands", "clipboard", "privacy", "advanced", "widgets", "plugins", "about"):
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


def test_launcher_respects_configured_opacity(qapp, controller):
    launcher = controller.launcher
    controller.config.set("appearance.animations", False)
    controller.config.set("appearance.opacity", 0.73)
    launcher.show_launcher()
    qapp.processEvents()
    # Qt exposes top-level opacity as an 8-bit alpha value on supported
    # platforms, so compare against the representable value rather than the
    # unquantized float supplied to setWindowOpacity().
    assert launcher.windowOpacity() == pytest.approx(round(0.73 * 255) / 255)
    controller.config.set("appearance.opacity", 0.91)
    qapp.processEvents()
    assert launcher.windowOpacity() == pytest.approx(round(0.91 * 255) / 255)
    controller.config.set("appearance.opacity", 0.98)


def test_theme_uses_point_sized_typography(controller):
    from ui.themes import build_stylesheet

    controller.config.set("appearance.font_size", 16)
    stylesheet = build_stylesheet(controller.config)
    assert "font-size: 16pt;" in stylesheet
    assert "font-size: 16px;" not in stylesheet
    controller.config.set("appearance.font_size", 13)


def test_theme_stylesheet_contains_widgets(controller):
    stylesheet = controller.app.styleSheet()
    assert "QLineEdit" in stylesheet
    assert "QListWidget#ResultList" in stylesheet


def test_weather_widget_displays_required_open_meteo_attribution(controller):
    attribution = controller.launcher.launcher_widgets.weather.attribution
    assert attribution.openExternalLinks()
    assert "Weather data by Open-Meteo.com" in attribution.text()
    assert 'href="https://open-meteo.com/"' in attribution.text()


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


# ------------------------------------- repeated packaged activation (v1.0.0)
def _pump(qapp, seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.01)


def test_show_survives_a_refused_foreground_activation(qapp, controller, monkeypatch):
    """[SIMULATED Windows] A show request must not be undone by focus-loss hiding.

    Windows refuses ``SetForegroundWindow`` from a background process, so a
    launcher raised by a second instance's socket message can end up visible
    but *not* active. The deactivation timer that hides the launcher when the
    user clicks away must not swallow that programmatic show; otherwise a
    repeated launch logs "request forwarded" while nothing appears.
    """
    launcher = controller.launcher
    launcher.show_launcher()
    qapp.processEvents()
    assert launcher.isVisible()

    # The desktop just took the focus away, and Windows then refuses to hand it
    # back when the second instance asks for the window.
    monkeypatch.setattr(launcher, "isActiveWindow", lambda: False)
    launcher.changeEvent(QEvent(QEvent.Type.WindowDeactivate))
    launcher.show_launcher()
    qapp.processEvents()

    _pump(qapp, 0.5)
    assert launcher.isVisible(), "a forwarded show request was hidden by focus loss"


def test_hide_on_focus_loss_still_hides_after_the_activation_grace(qapp, controller, monkeypatch):
    """[REAL] The activation grace period must not disable hide-on-focus-loss."""
    launcher = controller.launcher
    launcher.show_launcher()
    qapp.processEvents()
    monkeypatch.setattr(launcher, "isActiveWindow", lambda: False)
    # The grace window has already elapsed, so a genuine focus loss hides it.
    launcher._activation_deadline = time.monotonic() - 1.0
    launcher.changeEvent(QEvent(QEvent.Type.WindowDeactivate))

    _pump(qapp, 0.5)
    assert not launcher.isVisible(), "hide-on-focus-loss stopped working"


def test_a_superseded_hide_animation_cannot_hide_a_reshown_launcher(qapp, controller):
    """[REAL Qt animation] A show during the hide fade must win."""
    launcher = controller.launcher
    controller.config.set("appearance.animations", True)
    controller.config.set("appearance.animation_duration", 400)
    try:
        launcher.show_launcher()
        qapp.processEvents()
        assert launcher.isVisible()

        launcher.hide_launcher()          # starts a ~200 ms fade out
        launcher.show_launcher()          # a second instance arrives mid-fade
        _pump(qapp, 0.6)                  # let the stale animation finish

        assert launcher.isVisible(), "a stale hide animation hid the re-shown launcher"
    finally:
        controller.config.set("appearance.animations", False)


def test_controller_quit_stops_the_event_loop(tmp_path):
    """[REAL Qt event loop, subprocess] Quit must actually end the application.

    ``QCoreApplication.quit()`` is a no-op once the controller is running, which
    made the tray's Quit action do nothing; ``SeekRApplication.quit()`` therefore
    calls ``exit(0)`` directly. The script has its own watchdog timer so a
    regression fails instead of hanging the suite.
    """
    script = """
import os, sys, time
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from core.application import SeekRApplication
from core.config_manager import ConfigManager
from core.database import Database
from core.paths import ensure_app_dirs

ensure_app_dirs()
app = QApplication(["seekr-quit-test"])
cfg = ConfigManager(); db = Database()
cfg.set("general.show_tray_icon", False)
cfg.set("files.auto_index", False)
cfg.set("files.enabled", False)
controller = SeekRApplication(app, cfg, db)
controller._create_tray = lambda: None
controller.start(show_window=True, register_hotkey=False)
QTimer.singleShot(1200, controller.quit)
QTimer.singleShot(6000, lambda: os._exit(3))
started = time.monotonic()
code = app.exec()
print(f"QUIT_OK {code} {time.monotonic() - started:.2f}", flush=True)
"""
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["SEEKR_HOME"] = str(tmp_path / "home")
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=40,
        env=env,
    )
    assert result.returncode == 0, (
        f"quit() did not stop the event loop: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "QUIT_OK 0" in result.stdout, result.stdout


def test_single_instance_show_request_reveals_the_launcher(qapp, controller):
    """[REAL socket] A forwarded show request makes a hidden launcher visible."""
    from core.single_instance import SingleInstance

    key = f"SeekR.GuiTest.{os.getpid()}.{time.time_ns()}"
    primary = SingleInstance(key)
    secondary = SingleInstance(key)
    primary.show_requested.connect(controller.show_launcher)
    try:
        assert primary.listen() is True
        controller.launcher.hide_launcher()
        qapp.processEvents()
        assert not controller.launcher.isVisible()

        assert secondary.notify_existing() is True
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and not controller.launcher.isVisible():
            qapp.processEvents()
            time.sleep(0.01)
        assert controller.launcher.isVisible(), "the forwarded show request was ignored"
    finally:
        secondary.close()
        primary.close()


def test_widget_http_user_agent_tracks_application_version(monkeypatch):
    import json
    import urllib.request

    from core.version import APP_VERSION
    from ui.launcher_widgets import _FetchTask

    seen = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _limit):
            return json.dumps({"ok": True}).encode("utf-8")

    def fake_urlopen(request, timeout):
        seen["user_agent"] = request.get_header("User-agent")
        seen["timeout"] = timeout
        return Response()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert _FetchTask._get_json("https://example.test/data") == {"ok": True}
    assert seen == {
        "user_agent": f"SeekR/{APP_VERSION} (desktop launcher)",
        "timeout": 8,
    }


def test_launcher_widget_coordinator_does_not_create_an_overlay(qapp, controller):
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QWidget

    launcher = controller.launcher
    widgets = launcher.launcher_widgets

    assert isinstance(widgets, QObject)
    assert not isinstance(widgets, QWidget)
    assert widgets.left_column.parentWidget() is not widgets
    assert widgets.right_column.parentWidget() is not widgets
    assert widgets.clock.parentWidget() is widgets.left_column
    assert widgets.system.parentWidget() is widgets.left_column
    assert widgets.weather.parentWidget() is widgets.right_column
    assert widgets.meme.parentWidget() is widgets.right_column

    controller.config.set("widgets.clock_enabled", False)
    widgets.refresh_settings()
    assert widgets.clock.isHidden()
    assert widgets.clock.parentWidget() is widgets.left_column

    controller.config.set("widgets.clock_enabled", True)
    widgets.refresh_settings()
    assert widgets.clock.parentWidget() is widgets.left_column
    assert not widgets.clock.isHidden()


def test_launcher_shows_all_enabled_widget_cards_in_visible_rails(qapp, controller):
    launcher = controller.launcher
    widgets = launcher.launcher_widgets
    controller.config.set("widgets.clock_enabled", True)
    controller.config.set("widgets.system_enabled", True)
    controller.config.set("widgets.weather_enabled", True)
    controller.config.set("widgets.meme_enabled", True)
    widgets.refresh_settings()
    launcher.show_launcher()
    qapp.processEvents()

    assert launcher.isVisible()
    assert widgets.left_column.isVisible()
    assert widgets.right_column.isVisible()
    for name, card in widgets._cards.items():
        assert card.isVisible(), f"{name} widget is not visible"
        assert card.width() > 0 and card.height() > 0, f"{name} widget has empty geometry"
        snapshot = card.grab()
        assert not snapshot.isNull(), f"{name} widget failed to render a snapshot"
        assert card.parentWidget() in (widgets.left_column, widgets.right_column)
    assert widgets.left_column.geometry().width() >= 190
    assert widgets.right_column.geometry().width() >= 190
    launcher.hide_launcher()
    qapp.processEvents()


def test_daily_meme_only_opens_safe_reddit_links():
    from ui.launcher_widgets import MemeWidget

    assert MemeWidget._safe_post_url("https://www.reddit.com/r/test/comments/123/") == "https://www.reddit.com/r/test/comments/123/"
    assert MemeWidget._safe_post_url("https://redd.it/123") == "https://redd.it/123"
    assert MemeWidget._safe_post_url("javascript:alert(1)") == ""
    assert MemeWidget._safe_post_url("https://example.com/") == ""
    assert MemeWidget._safe_post_url("https://[:::]/") == ""


def test_disabled_daily_meme_does_not_restart_retry_timer(qapp):
    from PySide6.QtCore import QThreadPool
    from ui.launcher_widgets import MemeWidget

    widget = MemeWidget(QThreadPool())
    widget.setVisible(False)
    widget.set_error("meme", "network unavailable")
    assert not widget.retry_timer.isActive()
    widget.deleteLater()
    qapp.processEvents()

def test_20_new_search_providers_are_registered(controller, tmp_path):
    for query, expected in (
        ("flow: ", "workflows"),
        ("snip: ", "snippets"),
        ("content: ", "file_content"),
        ("chain: ", "command_chains"),
        ("wm: ", "window_manager"),
    ):
        resolved = controller.engine.resolve(query)
        assert resolved is not None
        assert resolved[0].id == expected


def test_workflow_and_snippet_tools_pages_are_constructible(qapp, controller, tmp_path):
    from ui.tools_window import ToolsWindow

    window = ToolsWindow(controller)
    assert "workflows" in window.pages
    assert "snippets" in window.pages

    folder = tmp_path / "workspace"
    folder.mkdir()
    ok, message = controller.workflow_service.save({
        "title": "Open workspace",
        "description": "Test workflow",
        "steps": [{"type": "open_folder", "path": str(folder)}],
    })
    assert ok, message
    ok, message = controller.snippet_service.save({
        "title": "Greeting", "category": "General", "shortcut": "hi", "content": "Hello",
    })
    assert ok, message

    workflow_tab = window.pages["workflows"]
    snippet_tab = window.pages["snippets"]
    workflow_tab.reload()
    snippet_tab.reload()
    assert workflow_tab.table.rowCount() >= 1
    assert snippet_tab.table.rowCount() >= 1
    window.close()

