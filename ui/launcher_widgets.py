"""Lightweight live widgets shown around the launcher results."""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

import psutil
from PySide6.QtCore import (
    QEasingCurve, QObject, QPropertyAnimation, QRunnable, QThreadPool,
    QTimer, Qt, Signal, Slot,
)
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QProgressBar,
    QVBoxLayout, QWidget,
)

log = logging.getLogger(__name__)


class _FetchSignals(QObject):
    finished = Signal(str, object)
    failed = Signal(str, str)


class _FetchTask(QRunnable):
    def __init__(self, kind: str, location: str = ""):
        super().__init__()
        self.setAutoDelete(False)
        self.kind = kind
        self.location = location
        self.signals = _FetchSignals()

    @staticmethod
    def _get_json(url: str) -> dict:
        request = urllib.request.Request(
            url, headers={"User-Agent": "SeekR/1.1.0 (desktop launcher)"}
        )
        with urllib.request.urlopen(request, timeout=8) as response:
            return json.loads(response.read(1_500_000).decode("utf-8"))

    def run(self) -> None:
        try:
            if self.kind == "weather":
                query = urllib.parse.urlencode({"name": self.location, "count": 1, "language": "en", "format": "json"})
                geo = self._get_json("https://geocoding-api.open-meteo.com/v1/search?" + query)
                places = geo.get("results") or []
                if not places:
                    raise ValueError("Location not found. Check the name in Settings.")
                place = places[0]
                params = urllib.parse.urlencode({
                    "latitude": place["latitude"], "longitude": place["longitude"],
                    "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
                    "timezone": "auto",
                })
                data = self._get_json("https://api.open-meteo.com/v1/forecast?" + params)
                data["place_name"] = ", ".join(filter(None, [place.get("name"), place.get("country")]))
                self.signals.finished.emit(self.kind, data)
            elif self.kind == "meme":
                data = self._get_json("https://meme-api.com/gimme/wholesomememes")
                image_url = str(data.get("url", ""))
                if image_url.startswith("https://"):
                    request = urllib.request.Request(image_url, headers={"User-Agent": "SeekR/1.1.0"})
                    with urllib.request.urlopen(request, timeout=8) as response:
                        data["_image_bytes"] = response.read(1_500_000)
                self.signals.finished.emit(self.kind, data)
        except Exception as exc:
            self.signals.failed.emit(self.kind, str(exc))


class WidgetCard(QFrame):
    """A compact, themed launcher card with a soft entrance transition."""

    def __init__(self, eyebrow: str, parent=None):
        super().__init__(parent)
        self.setObjectName("LauncherWidgetCard")
        self.setMinimumHeight(124)
        self.setMaximumHeight(160)
        self.setSizePolicy(self.sizePolicy().horizontalPolicy(), self.sizePolicy().verticalPolicy())
        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)
        self._fade = QPropertyAnimation(self._opacity, b"opacity", self)
        self._fade.setDuration(260)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(13, 11, 13, 12)
        layout.setSpacing(5)
        top = QHBoxLayout()
        self.eyebrow = QLabel(eyebrow.upper())
        self.eyebrow.setObjectName("WidgetEyebrow")
        top.addWidget(self.eyebrow)
        top.addStretch(1)
        layout.addLayout(top)
        self.content = QVBoxLayout()
        self.content.setSpacing(3)
        layout.addLayout(self.content, 1)

    def reveal(self, animate: bool = True) -> None:
        self._fade.stop()
        if animate:
            self._fade.setStartValue(0.0)
            self._fade.setEndValue(1.0)
            self._fade.start()
        else:
            self._opacity.setOpacity(1.0)


class ClockWidget(WidgetCard):
    def __init__(self, parent=None):
        super().__init__("Local time", parent)
        self.time_label = QLabel()
        self.time_label.setObjectName("WidgetClock")
        self.date_label = QLabel()
        self.date_label.setObjectName("WidgetSecondary")
        self.content.addWidget(self.time_label)
        self.content.addWidget(self.date_label)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1000)
        self.refresh()

    def refresh(self):
        now = datetime.now()
        self.time_label.setText(now.strftime("%H:%M:%S"))
        self.date_label.setText(now.strftime("%A, %d %B"))


class SystemWidget(WidgetCard):
    def __init__(self, parent=None):
        super().__init__("System", parent)
        self.cpu_label = QLabel("CPU  ·  —")
        self.ram_label = QLabel("Memory  ·  —")
        for title, obj in (("CPU", self.cpu_label), ("Memory", self.ram_label)):
            obj.setObjectName("WidgetSecondary")
            self.content.addWidget(obj)
            bar = QProgressBar()
            bar.setObjectName("WidgetProgress")
            bar.setRange(0, 100)
            bar.setTextVisible(False)
            bar.setFixedHeight(5)
            self.content.addWidget(bar)
            if title == "CPU":
                self.cpu_bar = bar
            else:
                self.ram_bar = bar
        psutil.cpu_percent(interval=None)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(2000)
        self.refresh()

    def refresh(self):
        try:
            cpu = int(psutil.cpu_percent(interval=None))
            memory = psutil.virtual_memory()
            ram = int(memory.percent)
            self.cpu_label.setText(f"CPU  ·  {cpu}%")
            self.ram_label.setText(f"Memory  ·  {ram}%")
            self.cpu_bar.setValue(cpu)
            self.ram_bar.setValue(ram)
        except Exception:
            log.debug("System widget refresh failed", exc_info=True)


class WeatherWidget(WidgetCard):
    def __init__(self, config, pool: QThreadPool, parent=None):
        super().__init__("Weather", parent)
        self.config = config
        self.pool = pool
        self.value = QLabel("Set a location in Settings")
        self.value.setObjectName("WidgetValue")
        self.details = QLabel("Weather at a glance")
        self.details.setObjectName("WidgetSecondary")
        self.details.setWordWrap(True)
        self.content.addWidget(self.value)
        self.content.addWidget(self.details)
        self._last_location = ""
        self._busy = False
        self._fetch_task = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_periodic)
        self.timer.start(30 * 60 * 1000)

    def _refresh_periodic(self):
        self._last_location = ""
        self.refresh()

    def refresh(self):
        location = str(self.config.get("widgets.weather_location", "") or "").strip()
        if not location:
            self.value.setText("Add your location")
            self.details.setText("Settings  →  Widgets")
            return
        if self._busy or location == self._last_location and self.value.text() != "Loading…":
            return
        self._busy = True
        self._last_location = location
        self.value.setText("Loading…")
        task = _FetchTask("weather", location)
        self._fetch_task = task
        task.signals.finished.connect(self.set_weather)
        task.signals.failed.connect(self.set_error)
        self.pool.start(task)

    @Slot(str, object)
    def set_weather(self, kind, data):
        if kind != "weather":
            return
        self._busy = False
        self._fetch_task = None
        if str(self.config.get("widgets.weather_location", "") or "").strip() != self._last_location:
            self._last_location = ""
            self.refresh()
            return
        current = data.get("current", {})
        code = current.get("weather_code")
        conditions = {
            0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
            45: "Fog", 48: "Depositing rime fog", 51: "Light drizzle",
            53: "Drizzle", 55: "Heavy drizzle", 61: "Light rain", 63: "Rain",
            65: "Heavy rain", 71: "Light snow", 73: "Snow", 75: "Heavy snow",
            80: "Rain showers", 81: "Showers", 82: "Heavy showers",
            95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Heavy thunderstorm",
        }
        condition = conditions.get(code, "Current conditions")
        self.value.setText(f"{current.get('temperature_2m', '—')}°  ·  {condition}")
        self.details.setText(
            f"{data.get('place_name', self._last_location)}\\n"
            f"Feels like {current.get('apparent_temperature', '—')}°  ·  "
            f"Humidity {current.get('relative_humidity_2m', '—')}%"
        )

    @Slot(str, str)
    def set_error(self, kind, message):
        if kind == "weather":
            self._busy = False
            self._fetch_task = None
            if str(self.config.get("widgets.weather_location", "") or "").strip() != self._last_location:
                self._last_location = ""
                self.refresh()
                return
            self.value.setText("Weather unavailable")
            self.details.setText(message[:90])


class MemeWidget(WidgetCard):
    def __init__(self, pool: QThreadPool, parent=None):
        super().__init__("Daily meme", parent)
        self.pool = pool
        self.title = QLabel("Today's internet moment")
        self.title.setObjectName("WidgetValue")
        self.title.setWordWrap(True)
        self.title.setMaximumHeight(34)
        self.title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setFixedHeight(54)
        self.preview.setMinimumWidth(150)
        self.preview.setScaledContents(False)
        self.preview.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.content.addWidget(self.preview)
        self.subreddit = QLabel("A fresh meme, once per day")
        self.subreddit.setObjectName("WidgetSecondary")
        self.subreddit.setWordWrap(True)
        self.content.addWidget(self.title)
        self.content.addWidget(self.subreddit)
        self._busy = False
        self._fetch_task = None
        self._cache_path = self._get_cache_path()
        self._cached_date = ""
        self._load_daily()
        self.day_timer = QTimer(self)
        self.day_timer.timeout.connect(self._check_new_day)
        self.day_timer.start(60_000)

    @staticmethod
    def _get_cache_path() -> Path:
        try:
            from core.paths import app_data_dir
            return Path(app_data_dir()) / "daily_meme.json"
        except Exception:
            return Path.home() / ".seekr_daily_meme.json"

    def _load_daily(self):
        today = datetime.now().date().isoformat()
        try:
            cached = json.loads(self._cache_path.read_text(encoding="utf-8"))
            if cached.get("date") == today and cached.get("title"):
                self._cached_date = today
                self._show_meme(cached)
                return
        except (OSError, ValueError, TypeError):
            pass
        self.refresh()

    def _check_new_day(self):
        if self._cached_date != datetime.now().date().isoformat():
            self._load_daily()

    def refresh(self):
        if self._busy:
            return
        self._busy = True
        self.title.setText("Finding today's meme…")
        task = _FetchTask("meme")
        self._fetch_task = task
        task.signals.finished.connect(self.set_meme)
        task.signals.failed.connect(self.set_error)
        self.pool.start(task)

    @Slot(str, object)
    def set_meme(self, kind, data):
        if kind != "meme":
            return
        self._busy = False
        self._fetch_task = None
        item = {
            "date": datetime.now().date().isoformat(),
            "title": str(data.get("title", "Today's meme"))[:180],
            "subreddit": str(data.get("subreddit", "reddit"))[:60],
            "url": str(data.get("postLink", "")),
        }
        image_bytes = data.get("_image_bytes")
        if image_bytes:
            image_path = self._cache_path.with_name("daily_meme_preview.jpg")
            try:
                image_path.write_bytes(image_bytes)
                item["image_file"] = str(image_path)
            except OSError:
                pass
        self._cached_date = item["date"]
        self._show_meme(item)
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(json.dumps(item), encoding="utf-8")
        except OSError:
            log.debug("Could not cache daily meme", exc_info=True)

    @Slot(str, str)
    def set_error(self, kind, message):
        if kind == "meme":
            self._busy = False
            self._fetch_task = None
            self._cached_date = datetime.now().date().isoformat()
            self.title.setText("Meme unavailable")
            self.subreddit.setText("Could not load today's meme")

    def _show_meme(self, item):
        image_path = Path(item.get("image_file", "")) if item.get("image_file") else None
        if image_path and image_path.is_file():
            pixmap = QPixmap(str(image_path))
            if not pixmap.isNull():
                self.preview.setPixmap(pixmap.scaled(168, 54, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                self.preview.show()
            else:
                self.preview.hide()
        else:
            self.preview.hide()
        self.title.setText(item.get("title", "Today's meme"))
        self.subreddit.setText("r/" + item.get("subreddit", "reddit") + "  ·  Open meme ↗")
        self.setToolTip(item.get("url", ""))
        self.setCursor(Qt.CursorShape.PointingHandCursor if item.get("url") else Qt.CursorShape.ArrowCursor)
        self._meme_url = item.get("url", "")

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and getattr(self, "_meme_url", ""):
            QDesktopServices.openUrl(QUrl(self._meme_url))
        super().mouseReleaseEvent(event)


class LauncherWidgets(QWidget):
    """Owns the four optional widgets, split into two side rails."""

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(2)
        self.clock = ClockWidget(self)
        self.system = SystemWidget(self)
        self.weather = WeatherWidget(config, self.pool, self)
        self.meme = MemeWidget(self.pool, self)
        self._cards = {"clock": self.clock, "weather": self.weather, "system": self.system, "meme": self.meme}
        for card in self._cards.values():
            card.setMinimumHeight(126)
            card.setMaximumHeight(164)
            card.setStyleSheet(
                "QFrame#LauncherWidgetCard { background: palette(window); border: 1px solid palette(mid); border-radius: 13px; } "
                "QFrame#LauncherWidgetCard:hover { border: 1px solid palette(highlight); } "
                "QLabel#WidgetEyebrow { color: palette(mid); font-size: 9px; font-weight: 700; letter-spacing: 1px; } "
                "QLabel#WidgetClock { font-size: 25px; font-weight: 650; color: palette(windowText); } "
                "QLabel#WidgetValue { font-size: 19px; font-weight: 650; color: palette(windowText); } "
                "QLabel#WidgetSecondary { color: palette(mid); font-size: 10px; } "
                "QProgressBar#WidgetProgress { background: palette(base); border: 0; border-radius: 2px; } "
                "QProgressBar#WidgetProgress::chunk { background: palette(highlight); border-radius: 2px; }"
            )
        self.left_column = QWidget(self)
        self.right_column = QWidget(self)
        self.left_column.setFixedWidth(196)
        self.right_column.setFixedWidth(196)
        self._left_layout = QVBoxLayout(self.left_column)
        self._right_layout = QVBoxLayout(self.right_column)
        for layout in (self._left_layout, self._right_layout):
            layout.setContentsMargins(0, 8, 0, 8)
            layout.setSpacing(9)
        self._rebuild()
        if self.config.get("widgets.weather_enabled", True):
            self.weather.refresh()
        if self.config.get("widgets.meme_enabled", True):
            self.meme._load_daily()

    def _rebuild(self):
        for layout in (self._left_layout, self._right_layout):
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().setParent(None)
        for key in ("clock", "system"):
            card = self._cards[key]
            enabled = bool(self.config.get(f"widgets.{key}_enabled", True))
            card.setVisible(enabled)
            if enabled:
                self._left_layout.addWidget(card)
                card.reveal(False)
        self._left_layout.addStretch(1)
        for key in ("weather", "meme"):
            card = self._cards[key]
            enabled = bool(self.config.get(f"widgets.{key}_enabled", True))
            card.setVisible(enabled)
            if enabled:
                self._right_layout.addWidget(card)
                card.reveal(False)
        self._right_layout.addStretch(1)

    def refresh_settings(self, animate=False):
        self._rebuild()
        if self.config.get("widgets.weather_enabled", True):
            self.weather._last_location = ""
            self.weather.refresh()
        if self.config.get("widgets.meme_enabled", True):
            self.meme._load_daily()
        if animate:
            for card in self._cards.values():
                if card.isVisible():
                    card.reveal(True)

