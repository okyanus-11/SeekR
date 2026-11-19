"""Lightweight live widgets shown around the launcher results."""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from urllib.parse import urlparse
from datetime import datetime
from pathlib import Path

import psutil
from PySide6.QtCore import (
    QObject, QRunnable, QThreadPool, QTimer, Qt, Signal, Slot,
)
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtCore import QUrl
from core.version import APP_VERSION
from ui.themes import palette_for
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar,
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
            url, headers={"User-Agent": f"SeekR/{APP_VERSION} (desktop launcher)"}
        )
        with urllib.request.urlopen(request, timeout=8) as response:
            payload = response.read(1_500_001)
            if len(payload) > 1_500_000:
                raise ValueError("The widget service returned an oversized response.")
            return json.loads(payload.decode("utf-8"))

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
                    try:
                        request = urllib.request.Request(image_url, headers={"User-Agent": f"SeekR/{APP_VERSION}"})
                        with urllib.request.urlopen(request, timeout=8) as response:
                            if response.headers.get_content_type().startswith("image/"):
                                image_bytes = response.read(1_500_001)
                                if len(image_bytes) <= 1_500_000:
                                    data["_image_bytes"] = image_bytes
                    except Exception:
                        # The meme itself is still useful if its preview host
                        # is down or rejects the image request.
                        log.debug("Could not fetch daily meme preview", exc_info=True)
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
        # Keep cards fully opaque. Opacity effects on nested Qt widgets can
        # interact badly with native Windows window composition and cause
        # cards to appear to vanish after the launcher is first painted.
        del animate
        self.setGraphicsEffect(None)
        self.setWindowOpacity(1.0)


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
        try:
            psutil.cpu_percent(interval=None)
        except Exception:
            log.debug("Could not prime CPU usage sampling", exc_info=True)
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
        self.attribution = QLabel(
            '<a href="https://open-meteo.com/">Weather data by Open-Meteo.com</a>'
        )
        self.attribution.setObjectName("WidgetAttribution")
        self.attribution.setOpenExternalLinks(True)
        self.content.addWidget(self.value)
        self.content.addWidget(self.details)
        self.content.addWidget(self.attribution)
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
            f"{data.get('place_name', self._last_location)}\n"
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
        self.title.setTextFormat(Qt.TextFormat.PlainText)
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
        self.subreddit.setTextFormat(Qt.TextFormat.PlainText)
        self.subreddit.setWordWrap(True)
        self.subreddit.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.content.addWidget(self.title)
        self.content.addWidget(self.subreddit)
        self._busy = False
        self._fetch_task = None
        self._cache_path = self._get_cache_path()
        self._cached_date = ""
        self.day_timer = QTimer(self)
        self.day_timer.timeout.connect(self._check_new_day)
        self.day_timer.start(60_000)
        self.retry_timer = QTimer(self)
        self.retry_timer.setSingleShot(True)
        self.retry_timer.timeout.connect(self._retry_fetch)

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
            if (
                isinstance(cached, dict)
                and cached.get("date") == today
                and isinstance(cached.get("title"), str)
                and cached.get("title")
            ):
                self._cached_date = today
                self._show_meme(cached)
                return
        except (OSError, ValueError, TypeError):
            pass
        self.refresh()

    def _check_new_day(self):
        if self._cached_date != datetime.now().date().isoformat():
            self._load_daily()

    def _retry_fetch(self):
        self._cached_date = ""
        self.refresh()

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
            "url": self._safe_post_url(data.get("postLink", "")),
        }
        image_bytes = data.get("_image_bytes")
        if image_bytes:
            image_path = self._cache_path.with_name("daily_meme_preview.jpg")
            try:
                image_path.parent.mkdir(parents=True, exist_ok=True)
                image_path.write_bytes(image_bytes)
                item["image_file"] = str(image_path)
            except OSError:
                pass
        self._cached_date = item["date"]
        self.retry_timer.stop()
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
            # A request may finish after the user disables this card. Do not
            # restart its retry timer while it is explicitly hidden.
            if not self.isHidden():
                self.retry_timer.start(15 * 60 * 1000)
            self.title.setText("Meme unavailable")
            self.subreddit.setText("Could not load today's meme")

    @staticmethod
    def _safe_post_url(value) -> str:
        url = str(value or "")
        try:
            parsed = urlparse(url)
        except ValueError:
            return ""
        if parsed.scheme == "https" and parsed.hostname in {
            "reddit.com", "www.reddit.com", "old.reddit.com", "redd.it"
        }:
            return url
        return ""

    def _show_meme(self, item):
        image_path = None
        image_file = item.get("image_file")
        if isinstance(image_file, str) and image_file:
            try:
                candidate = Path(image_file).resolve()
                cache_dir = self._cache_path.parent.resolve()
                if candidate.parent == cache_dir:
                    image_path = candidate
            except (OSError, RuntimeError):
                image_path = None
        if image_path and image_path.is_file():
            pixmap = QPixmap(str(image_path))
            if not pixmap.isNull():
                self.preview.setPixmap(pixmap.scaled(168, 54, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                self.preview.show()
            else:
                self.preview.hide()
        else:
            self.preview.hide()
        title = item.get("title")
        subreddit = item.get("subreddit")
        self.title.setText(title[:180] if isinstance(title, str) and title else "Today's meme")
        subreddit = subreddit[:60] if isinstance(subreddit, str) and subreddit else "reddit"
        self.subreddit.setText("r/" + subreddit + "  ·  Open meme ↗")
        self._meme_url = self._safe_post_url(item.get("url", ""))
        self.setToolTip(self._meme_url)
        self.setCursor(
            Qt.CursorShape.PointingHandCursor if self._meme_url else Qt.CursorShape.ArrowCursor
        )

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and getattr(self, "_meme_url", ""):
            QDesktopServices.openUrl(QUrl(self._meme_url))
        super().mouseReleaseEvent(event)


class LauncherWidgets(QObject):
    """Owns the four optional widgets, split into two side rails."""

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._active = False
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(2)
        # Build the visual containers first and make each card a permanent
        # child of its rail. Reparenting cards on every refresh can silently
        # hide Qt widgets and leave them outside the visible layout.
        self.left_column = QWidget(parent)
        self.right_column = QWidget(parent)
        self.left_column.setObjectName("LauncherWidgetRail")
        self.right_column.setObjectName("LauncherWidgetRail")
        self.left_column.setFixedWidth(196)
        self.right_column.setFixedWidth(196)
        self._left_layout = QVBoxLayout(self.left_column)
        self._right_layout = QVBoxLayout(self.right_column)
        for layout in (self._left_layout, self._right_layout):
            layout.setContentsMargins(0, 8, 0, 8)
            layout.setSpacing(9)

        self.clock = ClockWidget(self.left_column)
        self.system = SystemWidget(self.left_column)
        self.weather = WeatherWidget(config, self.pool, self.right_column)
        self.meme = MemeWidget(self.pool, self.right_column)
        self._cards = {"clock": self.clock, "weather": self.weather, "system": self.system, "meme": self.meme}
        self._left_layout.addWidget(self.clock)
        self._left_layout.addWidget(self.system)
        self._left_layout.addStretch(1)
        self._right_layout.addWidget(self.weather)
        self._right_layout.addWidget(self.meme)
        self._right_layout.addStretch(1)
        for card in self._cards.values():
            card.setMinimumHeight(132)
            card.setMaximumHeight(168)
            card.setContentsMargins(0, 0, 0, 0)
        self._apply_card_theme()
        self._rebuild()

    def _apply_card_theme(self):
        """Apply current semantic theme tokens to every persistent widget card."""
        colors = palette_for(str(self.config.get("appearance.theme", "dark")))
        for card in self._cards.values():
            card.setStyleSheet(
                "QFrame#LauncherWidgetCard {"
                f" background: {colors['surface']};"
                f" border: 1px solid {colors['border']};"
                " border-radius: 14px;"
                " }"
                "QFrame#LauncherWidgetCard:hover {"
                f" background: {colors['surface_alt']};"
                f" border: 1px solid {colors['accent']};"
                " }"
                "QLabel#WidgetEyebrow {"
                f" color: {colors['accent']};"
                " font-size: 9pt; font-weight: 700; letter-spacing: 1px;"
                " }"
                "QLabel#WidgetClock {"
                f" color: {colors['text']};"
                " font-size: 23pt; font-weight: 700;"
                " }"
                "QLabel#WidgetValue {"
                f" color: {colors['text']};"
                " font-size: 13pt; font-weight: 650;"
                " }"
                "QLabel#WidgetSecondary {"
                f" color: {colors['muted']};"
                " font-size: 9pt; font-weight: 500;"
                " }"
                "QLabel#WidgetAttribution {"
                f" color: {colors['accent']};"
                " font-size: 8pt;"
                " }"
                "QProgressBar#WidgetProgress {"
                f" background: {colors['surface_alt']};"
                " border: 0; border-radius: 3px;"
                " }"
                "QProgressBar#WidgetProgress::chunk {"
                f" background: {colors['accent']};"
                " border-radius: 3px;"
                " }"
            )

    def _rebuild(self):
        # Cards are inserted into their layouts exactly once in __init__.
        # Settings refreshes only toggle visibility; they never remove, hide,
        # reparent, or recreate a card. This makes widget lifetime independent
        # of search refreshes, animation state, and asynchronous data replies.
        for key in ("clock", "system", "weather", "meme"):
            card = self._cards[key]
            enabled = bool(self.config.get(f"widgets.{key}_enabled", True))
            card.setVisible(enabled)
            card.reveal(False)

        self._sync_timers()
        self.left_column.setVisible(
            any(bool(self.config.get(f"widgets.{key}_enabled", True)) for key in ("clock", "system"))
        )
        self.right_column.setVisible(
            any(bool(self.config.get(f"widgets.{key}_enabled", True)) for key in ("weather", "meme"))
        )

    def _sync_timers(self):
        """Poll live data only while its rail is enabled and the launcher is visible."""
        for key, card in self._cards.items():
            enabled = bool(self.config.get(f"widgets.{key}_enabled", True))
            running = self._active and enabled
            if key == "clock":
                card.timer.start(1000) if running else card.timer.stop()
                if running:
                    card.refresh()
            elif key == "system":
                card.timer.start(2000) if running else card.timer.stop()
                if running:
                    card.refresh()
            elif key == "weather":
                card.timer.start(30 * 60 * 1000) if running else card.timer.stop()
            else:
                card.day_timer.start(60_000) if running else card.day_timer.stop()
                if not running:
                    card.retry_timer.stop()

    def set_active(self, active: bool):
        active = bool(active)
        if self._active == active:
            return
        self._active = active
        self._sync_timers()
        if active:
            if self.config.get("widgets.weather_enabled", True):
                self.weather.refresh()
            if self.config.get("widgets.meme_enabled", True):
                self.meme._load_daily()

        self.left_column.setVisible(
            any(bool(self.config.get(f"widgets.{key}_enabled", True)) for key in ("clock", "system"))
        )
        self.right_column.setVisible(
            any(bool(self.config.get(f"widgets.{key}_enabled", True)) for key in ("weather", "meme"))
        )

    def refresh_settings(self, animate=False):
        self._apply_card_theme()
        self._rebuild()
        if self._active and self.config.get("widgets.weather_enabled", True):
            self.weather._last_location = ""
            self.weather.refresh()
        if self._active and self.config.get("widgets.meme_enabled", True):
            self.meme._load_daily()
        if animate:
            for card in self._cards.values():
                if card.isVisible():
                    card.reveal(True)

