Warning: truncated output (original token count: 12595)
Total output lines: 1326

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


def test_launcher_can_render_results_before_first_show(qapp, controller):
    from ui.launcher_window import LauncherWindow

    launcher = LauncherWindow(controller)
    try:
        assert not launcher.isVisible()
        launcher._display_results(
            [SearchResult(title="Pre-show result", category="Test", score=1.0)],
            "pre-show",
        )
        assert launcher.current_result() is not None
        assert launcher.current_result().title == "Pre-show result"
    finally:
        launcher.close()



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
    store.icon_for(str(paths[…7595 tokens truncated… = tmp_path / "SeekR-backup.db"
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



def test_launcher_survives_repeated_hide_show_cycles(qapp, controller):
    """Repeated dropdown use must keep the surface visible, renderable and searchable."""
    launcher = controller.launcher
    config = controller.config
    old_animations = config.get("appearance.animations", False)
    old_duration = config.get("appearance.animation_duration", 150)
    config.set("appearance.animations", True)
    config.set("appearance.animation_duration", 90)

    def pump_until(predicate, timeout=2.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            qapp.processEvents()
            if predicate():
                return True
            time.sleep(0.005)
        return bool(predicate())

    try:
        for cycle in range(10):
            launcher.show_launcher()
            launcher.set_query("calc: 2 + 3")
            wait_for_search(qapp, launcher)

            assert pump_until(lambda: launcher.isVisible())
            assert launcher._results, f"cycle {cycle}: search returned no results"
            frame = launcher.grab()
            assert not frame.isNull(), f"cycle {cycle}: launcher produced an empty render"
            assert frame.width() == launcher.width()
            assert frame.height() == launcher.height()

            launcher.hide_launcher()
            assert pump_until(lambda: not launcher.isVisible()), (
                f"cycle {cycle}: launcher did not finish hiding"
            )
    finally:
        launcher._stop_window_animation()
        launcher._hiding = False
        launcher.hide()
        config.set("appearance.animations", old_animations)
        config.set("appearance.animation_duration", old_duration)

