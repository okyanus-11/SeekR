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


def test_launcher_is_anchored_to_the_top_of_the_active_screen(qapp, controller):
    launcher = controller.launcher
    launcher.show_launcher()
    qapp.processEvents()

    screen = launcher._screen()
    available = screen.availableGeometry()
    expected_x = available.x() + (available.width() - launcher.width()) // 2

    assert launcher.y() == available.y() + 8
    if available.width() >= launcher.width() > 0:
        assert abs(launcher.x() - expected_x) <= 1
    assert launcher.y() < available.y() + available.height() // 4

    launcher.hide_launcher()
    qapp.processEvents()


def test_launcher_uses_opaque_surface_without_graphics_effect(qapp, controller):
    launcher = controller.launcher
    assert not launcher.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert launcher.graphicsEffect() is None
    assert launcher.root.graphicsEffect() is None
    assert launcher.windowOpacity() == 1.0


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
        assert launcher.windowOpacity() == 1.0
    finally:
        config.set("appearance.animations", old_animations)
        config.set("appearance.animation_duration", old_duration)
        launcher._stop_window_animation()
        launcher._hiding = False


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
            for key in ("clock", "weather", "system", "cat", "tasks", "media"):
                controller.config.set(f"widgets.{key}_enabled", False)
            widgets.refresh_settings()
            qapp.processEvents()
            assert not widgets.left_column.isVisible()
            assert not widgets.right_column.isVisible()

            for key in ("clock", "weather", "system", "cat", "tasks", "media"):
                controller.config.set(f"widgets.{key}_enabled", True)
            widgets.refresh_settings()
            qapp.processEvents()
            assert widgets.left_column.isVisible()
            assert widgets.right_column.isVisible()
            assert all(card.isVisible() for card in widgets._cards.values())
            assert all(card.parentWidget() in (widgets.left_column, widgets.right_column)
                       for card in widgets._cards.values())

            launcher.resize(980 + cycle * 80, 560 + cycle * 40)
            qapp.processEvents()
            launcher.hide_launcher()
            qapp.processEvents()
            launcher.show_launcher()
            qapp.processEvents()
            launcher.set_query(f"calc: {cycle + 2}*3")
            wait_for_search(qapp, launcher)
            assert all(card.isVisible() for card in widgets._cards.values())

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
        for key in ("clock", "weather", "system", "cat", "tasks"):
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
    assert widgets.tasks.timer.isActive()

    launcher.hide_launcher()
    qapp.processEvents()
    assert not widgets._active
    assert not widgets.clock.timer.isActive()
    assert not widgets.system.timer.isActive()
    assert not widgets.weather.timer.isActive()
    assert not widgets.cat.day_timer.isActive()
    assert not widgets.tasks.timer.isActive()

    launcher.show_launcher()
    qapp.processEvents()
    assert widgets._active
    assert widgets.clock.timer.isActive()
    assert widgets.system.timer.isActive()


def test_widget_refresh_intervals_are_configurable_and_bounded(qapp, controller):
    widgets = controller.launcher.launcher_widgets
    # Keep this test hermetic: interval changes must not trigger live network calls.
    controller.config.set("widgets.clock_refresh_ms", 1500)
    controller.config.set("widgets.system_refresh_ms", 5000)
    controller.config.set("widgets.weather_refresh_minutes", 45)
    controller.config.set("widgets.tasks_refresh_minutes", 10)
    widgets.weather.refresh = lambda: None
    widgets.cat._load_daily = lambda: None
    widgets.set_active(True)
    widgets.refresh_settings()
    qapp.processEvents()

    assert widgets.clock.timer.interval() == 1500
    assert widgets.system.timer.interval() == 5000
    assert widgets.weather.timer.interval() == 45 * 60 * 1000
    assert widgets.cat.day_timer.interval() == 60_000
    assert widgets.tasks.timer.interval() == 10 * 60 * 1000

    controller.config.set("widgets.clock_refresh_ms", 1)
    controller.config.set("widgets.system_refresh_ms", 999999)
    controller.config.set("widgets.weather_refresh_minutes", 1)
    controller.config.set("widgets.tasks_refresh_minutes", 9999)
    assert controller.config.get("widgets.clock_refresh_ms") == 250
    assert controller.config.get("widgets.system_refresh_ms") == 30000
    assert controller.config.get("widgets.weather_refresh_minutes") == 5
    assert controller.config.get("widgets.tasks_refresh_minutes") == 60
    widgets.set_active(False)


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
    assert len(window.pages) == len(window.PAGES)
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
    assert len(window.pages) == len(window.PAGES)
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


def test_launcher_remains_opaque_when_legacy_opacity_is_configured(qapp, controller):
    launcher = controller.launcher
    controller.config.set("appearance.animations", False)
    controller.config.set("appearance.opacity", 0.73)
    launcher.show_launcher()
    qapp.processEvents()
    # Legacy opacity values must not turn the launcher into a layered window.
    assert launcher.windowOpacity() == 1.0
    assert not launcher.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    controller.config.set("appearance.opacity", 0.91)
    qapp.processEvents()
    assert launcher.windowOpacity() == 1.0
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


def test_hotkey_reopens_launcher_during_hide_animation(qapp, controller):
    """A second hotkey press must reverse an in-progress dropdown dismissal."""
    launcher = controller.launcher
    controller.config.set("appearance.animations", True)
    controller.config.set("appearance.animation_duration", 400)
    try:
        launcher.show_launcher()
        qapp.processEvents()
        assert launcher.isVisible()

        launcher.hide_launcher()
        assert launcher._hiding
        launcher.toggle()  # same path used by the global hotkey
        _pump(qapp, 0.6)

        assert launcher.isVisible(), "the second hotkey press was swallowed by the hide animation"
        assert not launcher._hiding
    finally:
        controller.config.set("appearance.animations", False)


def test_stale_window_deactivate_does_not_hide_reopened_launcher(qapp, controller):
    """A delayed deactivate event from the prior hide must not close a fresh show."""
    from PySide6.QtCore import QEvent

    launcher = controller.launcher
    previous_hide_setting = controller.config.get("general.hide_on_focus_loss", True)
    controller.config.set("general.hide_on_focus_loss", True)
    launcher.show_launcher()
    qapp.processEvents()
    try:
        # Model Qt delivering an old WindowDeactivate after the new show has
        # already been activated. This is the race that the grace guard covers.
        launcher._activation_confirmed = True
        launcher._activation_deadline = time.monotonic() + 2.0
        event = QEvent(QEvent.Type.WindowDeactivate)
        qapp.sendEvent(launcher, event)
        assert not launcher._hide_timer.isActive()
        _pump(qapp, 0.2)
        assert launcher.isVisible()
    finally:
        launcher._activation_deadline = 0.0
        launcher.hide_launcher()
        controller.config.set("general.hide_on_focus_loss", previous_hide_setting)


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


def test_cat_json_endpoint_requires_a_list_response(monkeypatch):
    import json
    import urllib.request

    from ui.launcher_widgets import _FetchTask

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _limit):
            return self.payload

    monkeypatch.setattr(
        urllib.request, "urlopen",
        lambda request, timeout: Response(json.dumps([{"url": "https://cdn2.thecatapi.com/images/cat.jpg"}]).encode()),
    )
    assert _FetchTask._get_json_list("https://api.thecatapi.com/v1/images/search") == [
        {"url": "https://cdn2.thecatapi.com/images/cat.jpg"}
    ]

    monkeypatch.setattr(
        urllib.request, "urlopen",
        lambda request, timeout: Response(json.dumps({"url": "https://cdn2.thecatapi.com/images/cat.jpg"}).encode()),
    )
    with pytest.raises(ValueError, match="invalid response"):
        _FetchTask._get_json_list("https://api.thecatapi.com/v1/images/search")

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
    assert widgets.cat.parentWidget() is widgets.right_column

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
    controller.config.set("widgets.cat_enabled", True)
    controller.config.set("widgets.media_enabled", True)
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


def test_daily_cat_widget_displays_an_image_without_external_link_metadata(qapp, monkeypatch, tmp_path):
    import base64
    import json
    from PySide6.QtCore import QThreadPool
    from ui.launcher_widgets import CatWidget

    cache = tmp_path / "daily_cat.json"
    monkeypatch.setattr(CatWidget, "_get_cache_path", staticmethod(lambda: cache))
    widget = CatWidget(QThreadPool())
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
    )
    widget.set_cat("cat", {"_image_bytes": png})
    assert widget.preview.pixmap() is not None
    assert not widget.preview.pixmap().isNull()
    assert "tomorrow" in widget.status.text().lower()
    saved = json.loads(cache.read_text(encoding="utf-8"))
    assert saved["image_file"] == "daily_cat.png"
    assert "url" not in saved
    assert (tmp_path / "daily_cat.png").is_file()

    restored = CatWidget(QThreadPool())
    restored._load_daily()
    assert not restored._last_good_pixmap.isNull()
    assert "saved on this device" in restored.status.text().lower()

    widget.retry_timer.stop()
    widget.day_timer.stop()
    restored.retry_timer.stop()
    restored.day_timer.stop()
    widget.deleteLater()
    restored.deleteLater()
    qapp.processEvents()


def test_disabled_daily_cat_does_not_restart_retry_timer(qapp):
    from PySide6.QtCore import QThreadPool
    from ui.launcher_widgets import CatWidget

    widget = CatWidget(QThreadPool())
    widget.setVisible(False)
    widget.set_error("cat", "network unavailable")
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
        ("> system", "command_center"),
        ("update: ", "updates"),
        ("task: ", "tasks"),
    ):
        resolved = controller.engine.resolve(query)
        assert resolved is not None
        assert resolved[0].id == expected


def test_workflow_and_snippet_tools_pages_are_constructible(qapp, controller, tmp_path):
    from ui.tools_window import ToolsWindow

    window = ToolsWindow(controller)
    assert "workflows" in window.pages
    assert "snippets" in window.pages
    assert "tasks" in window.pages
    assert "database" in window.pages
    assert "diagnostics" in window.pages

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
    tasks_tab = window.pages["tasks"]
    database_tab = window.pages["database"]
    workflow_tab.reload()
    snippet_tab.reload()
    tasks_tab.reload()
    assert hasattr(database_tab, "_backup") and hasattr(database_tab, "_restore")
    assert workflow_tab.table.rowCount() >= 1
    assert snippet_tab.table.rowCount() >= 1
    window.close()


def test_system_widget_includes_storage_battery_and_network(qapp, controller):
    system = controller.launcher.launcher_widgets.system
    system.refresh()
    deadline = time.monotonic() + 3.0
    while system._busy and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.005)
    assert not system._busy, "system metrics worker did not finish"
    assert system.disk_label.text().startswith("Storage")
    assert system.battery_label.text().startswith("Battery")
    assert system.network_label.text().startswith("Network")
    assert system.disk_bar.value() >= 0


def test_system_widget_collects_metrics_off_the_gui_thread(qapp, controller, monkeypatch):
    import psutil

    system = controller.launcher.launcher_widgets.system
    deadline = time.monotonic() + 3.0
    while system._busy and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.005)
    assert not system._busy

    main_thread = threading.get_ident()
    worker_thread = []
    started = threading.Event()
    release = threading.Event()
    original = psutil.cpu_percent

    def slow_cpu_probe(interval=None):
        worker_thread.append(threading.get_ident())
        started.set()
        release.wait(2.0)
        return original(interval=interval)

    monkeypatch.setattr(psutil, "cpu_percent", slow_cpu_probe)
    try:
        system.refresh()
        assert started.wait(1.0), "system metrics probe did not start"
        # A deliberately stalled OS metrics call must not stall Qt's event loop.
        qapp.processEvents()
        assert system._busy
        assert worker_thread and worker_thread[0] != main_thread
    finally:
        release.set()

    deadline = time.monotonic() + 3.0
    while system._busy and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.005)
    assert not system._busy, "system metrics worker did not recover after the probe returned"

def test_clock_widget_focus_timer_starts_pauses_and_resets(controller):
    clock = controller.launcher.launcher_widgets.clock
    original = controller.config.get("widgets.focus_duration_minutes", 25)
    try:
        controller.config.set("widgets.focus_duration_minutes", 5)
        clock._reset_focus()
        assert clock.focus_remaining == 300
        clock._toggle_focus()
        assert clock.focus_deadline is not None
        clock._toggle_focus()
        assert clock.focus_deadline is None
        assert 0 <= clock.focus_remaining <= 300
        clock._reset_focus()
        assert clock.focus_remaining == 300
    finally:
        controller.config.set("widgets.focus_duration_minutes", original)
        clock._reset_focus()


def test_database_tools_page_backup_and_restore(qapp, controller, tmp_path, monkeypatch):
    from ui.tools import data as data_tools

    page = data_tools.DatabaseTab(controller, None)
    original_id = controller.notes_service.create("Backup note", "restored content")
    backup_path = tmp_path / "SeekR-backup.db"
    monkeypatch.setattr(
        data_tools.QFileDialog, "getSaveFileName",
        lambda *_args, **_kwargs: (str(backup_path), "SQLite database (*.db)"),
    )
    page._backup()
    assert backup_path.is_file()
    assert "Verified backup" in page.status.text()

    controller.notes_service.create("Later note", "must be removed by restore")
    monkeypatch.setattr(
        data_tools.QFileDialog, "getOpenFileName",
        lambda *_args, **_kwargs: (str(backup_path), "SQLite database (*.db)"),
    )
    monkeypatch.setattr(data_tools.dialogs, "ask_confirm", lambda *_args, **_kwargs: True)
    page._restore()
    assert controller.notes_service.get(original_id)["body"] == "restored content"
    assert controller.notes_service.list("Later note") == []
    assert "Database restored" in page.status.text()


def test_widget_size_settings_apply_without_reparenting(qapp, controller):
    widgets = controller.launcher.launcher_widgets
    parents = {name: card.parentWidget() for name, card in widgets._cards.items()}
    controller.config.set("widgets.rail_width", 232)
    controller.config.set("widgets.card_height", 176)
    widgets.refresh_settings()
    assert widgets.left_column.width() == 232
    assert widgets.right_column.width() == 232
    for name, card in widgets._cards.items():
        assert card.minimumHeight() == 176
        assert card.parentWidget() is parents[name]
    controller.config.set("widgets.rail_width", 196)
    controller.config.set("widgets.card_height", 140)
    widgets.refresh_settings()


def test_widget_order_settings_reorder_without_reparenting(qapp, controller):
    widgets = controller.launcher.launcher_widgets
    parents = {name: card.parentWidget() for name, card in widgets._cards.items()}
    controller.config.set("widgets.left_order", ["tasks", "clock", "system"])
    controller.config.set("widgets.right_order", ["cat", "weather"])
    widgets.refresh_settings()
    left = [widgets._left_layout.itemAt(i).widget() for i in range(widgets._left_layout.count())]
    right = [widgets._right_layout.itemAt(i).widget() for i in range(widgets._right_layout.count())]
    assert left[:3] == [widgets.tasks, widgets.clock, widgets.system]
    assert right[:2] == [widgets.cat, widgets.weather]
    for name, card in widgets._cards.items():
        assert card.parentWidget() is parents[name]
    controller.config.set("widgets.left_order", ["clock", "system", "tasks"])
    controller.config.set("widgets.right_order", ["weather", "cat"])
    widgets.refresh_settings()

 
def test_weather_keeps_last_good_data_when_refresh_fails(qapp, controller):
    from PySide6.QtCore import QThreadPool
    from ui.launcher_widgets import WeatherWidget

    controller.config.set("widgets.weather_location", "Izmir")
    widget = WeatherWidget(controller.config, QThreadPool())
    widget._last_location = "Izmir"
    widget.set_weather("weather", {
        "place_name": "Izmir, Türkiye",
        "current": {
            "weather_code": 0,
            "temperature_2m": 22,
            "apparent_temperature": 21,
            "relative_humidity_2m": 45,
        },
    })
    previous_value = widget.value.text()
    widget.set_error("weather", "network unavailable")
    assert widget.value.text() == previous_value
    assert "last successful update" in widget.details.text().lower()
    widget.timer.stop()
    widget.deleteLater()

 
def test_cat_keeps_last_good_image_when_refresh_fails(qapp, monkeypatch, tmp_path):
    import base64
    from PySide6.QtCore import QThreadPool
    from ui.launcher_widgets import CatWidget

    cache = tmp_path / "daily_cat.json"
    monkeypatch.setattr(CatWidget, "_get_cache_path", staticmethod(lambda: cache))
    widget = CatWidget(QThreadPool())
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
    )
    widget.set_cat("cat", {"_image_bytes": png})
    widget.set_error("cat", "network unavailable")
    assert widget.preview.pixmap() is not None
    assert not widget.preview.pixmap().isNull()
    assert "saved cat" in widget.status.text().lower()
    widget.retry_timer.stop()
    widget.day_timer.stop()
    widget.deleteLater()
    qapp.processEvents()


def test_weather_cache_restores_last_good_data_across_instances(qapp, monkeypatch, controller, tmp_path):
    from PySide6.QtCore import QThreadPool
    from ui.launcher_widgets import WeatherWidget

    cache = tmp_path / "weather_cache.json"
    monkeypatch.setattr(WeatherWidget, "_get_cache_path", staticmethod(lambda: cache))
    controller.config.set("widgets.weather_location", "Izmir")
    first = WeatherWidget(controller.config, QThreadPool())
    first._last_location = "Izmir"
    first.set_weather("weather", {
        "place_name": "Izmir, Türkiye",
        "current": {
            "weather_code": 0,
            "temperature_2m": 22,
            "apparent_temperature": 21,
            "relative_humidity_2m": 45,
        },
    })
    first_value = first.value.text()
    second = WeatherWidget(controller.config, QThreadPool())
    assert second.value.text() == first_value
    assert "Izmir" in second.details.text()
    first.timer.stop()
    second.timer.stop()
    first.deleteLater()
    second.deleteLater()

 
def test_widget_json_rejects_non_object_provider_response(monkeypatch):
    import urllib.request
    from ui.launcher_widgets import _FetchTask

    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
        def read(self, _limit):
            return b"[]"

    monkeypatch.setattr(urllib.request, "urlopen", lambda *_args, **_kwargs: Response())
    import pytest
    with pytest.raises(ValueError, match="invalid response"):
        _FetchTask._get_json("https://example.test/widget")



def test_widget_json_reports_network_errors_without_swallowing_them(monkeypatch):
    import urllib.error
    import urllib.request
    import pytest
    from ui.launcher_widgets import _FetchTask

    for error in (urllib.error.URLError("DNS lookup failed"), TimeoutError("request timed out")):
        monkeypatch.setattr(
            urllib.request, "urlopen",
            lambda *_args, _error=error, **_kwargs: (_ for _ in ()).throw(_error),
        )
        with pytest.raises(type(error)):
            _FetchTask._get_json("https://example.test/data")


def test_widget_json_rejects_malformed_payload(monkeypatch):
    import urllib.request
    import pytest
    from ui.launcher_widgets import _FetchTask

    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
        def read(self, _limit):
            return b'{"weather":'

    monkeypatch.setattr(urllib.request, "urlopen", lambda *_args, **_kwargs: Response())
    with pytest.raises(ValueError):
        _FetchTask._get_json("https://example.test/data")


def test_widget_json_rejects_oversized_payload(monkeypatch):
    import urllib.request
    import pytest
    from ui.launcher_widgets import _FetchTask

    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
        def read(self, limit):
            return b"x" * limit

    monkeypatch.setattr(urllib.request, "urlopen", lambda *_args, **_kwargs: Response())
    with pytest.raises(ValueError, match="oversized"):
        _FetchTask._get_json("https://example.test/data")


def test_widget_fetch_task_emits_failure_for_network_errors(monkeypatch):
    from ui.launcher_widgets import _FetchTask

    def fail(_url):
        raise OSError("simulated offline network")

    monkeypatch.setattr(_FetchTask, "_get_json", staticmethod(fail))
    task = _FetchTask("weather", "Izmir")
    failures = []
    task.signals.failed.connect(lambda kind, message: failures.append((kind, message)))
    task.run()

    assert failures == [("weather", "simulated offline network")]
