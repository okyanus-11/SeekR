"""Regression tests for launcher widget visibility and live updates."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from ui.launcher_widgets import LauncherWidgets


class _WidgetConfig:
    def get(self, key: str, default=None):
        values = {
            "appearance.theme": "dark",
            "widgets.clock_enabled": True,
            "widgets.system_enabled": True,
            "widgets.weather_enabled": True,
            "widgets.meme_enabled": True,
            "widgets.weather_location": "",
        }
        return values.get(key, default)


def test_widgets_remain_visible_and_live_after_refresh(qapp, monkeypatch):
    # Keep this UI regression test deterministic and independent of network APIs.
    monkeypatch.setattr("ui.launcher_widgets.WeatherWidget.refresh", lambda self: None)
    monkeypatch.setattr("ui.launcher_widgets.MemeWidget._load_daily", lambda self: None)

    host = QWidget()
    host.resize(1000, 700)
    widgets = LauncherWidgets(_WidgetConfig(), host)
    host.show()
    widgets.left_column.show()
    widgets.right_column.show()
    qapp.processEvents()

    initial_time = widgets.clock.time_label.text()
    widgets.refresh_settings(animate=True)
    qapp.processEvents()

    assert all(card.isVisible() for card in widgets._cards.values())
    assert widgets.left_column.isVisible()
    assert widgets.right_column.isVisible()
    assert all(card.graphicsEffect() is None for card in widgets._cards.values())
    assert widgets.clock.timer.isActive()
    assert widgets.system.timer.isActive()
    assert widgets.weather.timer.isActive()
    assert widgets.meme.day_timer.isActive()

    # The old failure was delayed: cards looked correct initially, then vanished.
    from PySide6.QtTest import QTest

    QTest.qWait(1200)
    qapp.processEvents()
    assert all(card.isVisible() for card in widgets._cards.values())
    assert widgets.clock.time_label.text() != initial_time

    widgets.refresh_settings(animate=False)
    qapp.processEvents()
    assert all(card.isVisible() for card in widgets._cards.values())
    host.close()
