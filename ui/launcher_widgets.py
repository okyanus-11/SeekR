"""Lightweight live widgets shown around the launcher results."""

from __future__ import annotations

import json
import os
import time
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
    QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton,
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
            parsed = json.loads(payload.decode("utf-8"))
            if not isinstance(parsed, dict):
                raise ValueError("The widget service returned an invalid response.")
            return parsed

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
    def __init__(self, config, parent=None):
        super().__init__("Local time", parent)
        self.config = config
        self.time_label = QLabel()
        self.time_label.setObjectName("WidgetClock")
        self.date_label = QLabel()
        self.date_label.setObjectName("WidgetSecondary")
        self.content.addWidget(self.time_label)
        self.content.addWidget(self.date_label)

        self.focus_remaining = self._duration_seconds()
        self.focus_deadline: float | None = None
        self.focus_label = QLabel()
        self.focus_label.setObjectName("WidgetSecondary")
        self.content.addWidget(self.focus_label)
        controls = QHBoxLayout()
        self.focus_button = QPushButton("Start focus")
        self.focus_button.setFixedHeight(24)
        self.focus_button.clicked.connect(self._toggle_focus)
        self.focus_reset = QPushButton("Reset")
        self.focus_reset.setFixedHeight(24)
        self.focus_reset.clicked.connect(self._reset_focus)
        controls.addWidget(self.focus_button)
        controls.addWidget(self.focus_reset)
        self.content.addLayout(controls)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1000)
        self.refresh()

    def _duration_seconds(self) -> int:
        minutes = int(self.config.get("widgets.focus_duration_minutes", 25) or 25)
        return max(5, min(180, minutes)) * 60

    def _toggle_focus(self) -> None:
        if self.focus_deadline is not None:
            self.focus_remaining = max(0, int(self.focus_deadline - time.monotonic() + 0.999))
            self.focus_deadline = None
        else:
            if self.focus_remaining <= 0:
                self.focus_remaining = self._duration_seconds()
            self.focus_deadline = time.monotonic() + self.focus_remaining
        self._refresh_focus()

    def _reset_focus(self) -> None:
        self.focus_deadline = None
        self.focus_remaining = self._duration_seconds()
        self._refresh_focus()

    def _refresh_focus(self) -> None:
        if self.focus_deadline is not None:
            self.focus_remaining = max(0, int(self.focus_deadline - time.monotonic() + 0.999))
            if self.focus_remaining <= 0:
                self.focus_deadline = None
                self.focus_label.setText("Focus session complete")
                self.focus_button.setText("Start again")
                return
            self.focus_label.setText(f"Focus · {self.focus_remaining // 60:02d}:{self.focus_remaining % 60:02d} remaining")
            self.focus_button.setText("Pause")
        elif self.focus_remaining == self._duration_seconds():
            self.focus_label.setText(f"Focus · {self.focus_remaining // 60:02d}:00 session")
            self.focus_button.setText("Start focus")
        else:
            self.focus_label.setText(f"Paused · {self.focus_remaining // 60:02d}:{self.focus_remaining % 60:02d}")
            self.focus_button.setText("Resume")

    def refresh(self):
        now = datetime.now()
        self.time_label.setText(now.strftime("%H:%M:%S"))
        self.date_label.setText(now.strftime("%A, %d %B"))
        self._refresh_focus()


class SystemWidget(WidgetCard):
    def __init__(self, parent=None):
        super().__init__("System", parent)
        self.cpu_label = QLabel("CPU  ·  —")
        self.ram_label = QLabel("Memory  ·  —")
        self.disk_label = QLabel("Storage  ·  —")
        self.battery_label = QLabel("Battery  ·  —")
        self.network_label = QLabel("Network  ·  —")
        self.cpu_bar = self._add_meter(self.cpu_label)
        self.ram_bar = self._add_meter(self.ram_label)
        self.disk_bar = self._add_meter(self.disk_label)
        self.content.addWidget(self.battery_label)
        self.content.addWidget(self.network_label)
        self.battery_label.setObjectName("WidgetSecondary")
        self.network_label.setObjectName("WidgetSecondary")
        try:
            psutil.cpu_percent(interval=None)
            self._network_previous = psutil.net_io_counters()
        except Exception:
            self._network_previous = None
        self._network_time = time.monotonic()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(2000)
        self.refresh()

    def _add_meter(self, label_widget: QLabel) -> QProgressBar:
        label_widget.setObjectName("WidgetSecondary")
        self.content.addWidget(label_widget)
        bar = QProgressBar()
        bar.setObjectName("WidgetProgress")
        bar.setRange(0, 100)
        bar.setTextVisible(False)
        bar.setFixedHeight(5)
        self.content.addWidget(bar)
        return bar

    @staticmethod
    def _rate(value: float) -> str:
        units = ("B/s", "KB/s", "MB/s", "GB/s")
        amount = max(0.0, float(value))
        unit = 0
        while amount >= 1024 and unit < len(units) - 1:
            amount /= 1024
            unit += 1
        return f"{amount:.0f} {units[unit]}"

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
            log.debug("System CPU/memory refresh failed", exc_info=True)

        try:
            root = Path.home().anchor or os.path.abspath(os.sep)
            disk = psutil.disk_usage(root)
            disk_percent = int(disk.percent)
            self.disk_label.setText(f"Storage  ·  {disk_percent}% used")
            self.disk_bar.setValue(disk_percent)
        except Exception:
            self.disk_label.setText("Storage  ·  unavailable")
            log.debug("System storage refresh failed", exc_info=True)

        try:
            battery = psutil.sensors_battery()
            if battery is None:
                self.battery_label.setText("Battery  ·  unavailable")
            else:
                state = "plugged in" if battery.power_plugged else "on battery"
                self.battery_label.setText(f"Battery  ·  {int(battery.percent)}% · {state}")
        except Exception:
            self.battery_label.setText("Battery  ·  unavailable")
            log.debug("System battery refresh failed", exc_info=True)

        try:
            current = psutil.net_io_counters()
            now = time.monotonic()
            elapsed = max(0.1, now - self._network_time)
            if self._network_previous is None:
                sent_rate = received_rate = 0.0
            else:
                sent_rate = max(0, current.bytes_sent - self._network_previous.bytes_sent) / elapsed
                received_rate = max(0, current.bytes_recv - self._network_previous.bytes_recv) / elapsed
            self._network_previous = current
            self._network_time = now
            self.network_label.setText(
                f"Network  ·  ↑ {self._rate(sent_rate)}  ↓ {self._rate(received_rate)}"
            )
        except Exception:
            self.network_label.setText("Network  ·  unavailable")
            log.debug("System network refresh failed", exc_info=True)


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
        self._last_good_details = ""
        self._has_data = False
        self._busy = False
        self._fetch_task = None
        self._cache_path = self._get_cache_path()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_periodic)
        self.timer.start(30 * 60 * 1000)
        self._restore_cache()

    @staticmethod
    def _get_cache_path() -> Path:
        try:
            from core.paths import app_data_dir
            return Path(app_data_dir()) / "weather_cache.json"
        except Exception:
            return Path.home() / ".seekr_weather_cache.json"

    def _restore_cache(self) -> None:
        location = str(self.config.get("widgets.weather_location", "") or "").strip()
        if not location:
            return
        try:
            if self._cache_path.stat().st_size > 64_000:
                return
            if self._cache_path.stat().st_size > 64_000:
                return
            cached = json.loads(self._cache_path.read_text(encoding="utf-8"))
            if not isinstance(cached, dict) or cached.get("location") != location:
                return
            data = cached.get("data")
            if not isinstance(data, dict) or not isinstance(data.get("current"), dict):
                return
            self._last_location = location
            self.set_weather("weather", data)
            self.details.setText(self._last_good_details + "\nCached · last successful update")
            # Keep the cache visible but allow the first active refresh to
            # request newer conditions immediately.
            self._last_location = ""
        except (OSError, ValueError, TypeError):
            log.debug("Could not restore cached weather", exc_info=True)

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
        if self._has_data:
            self.details.setText(self._last_good_details + "\nRefreshing…")
        else:
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
        if not isinstance(data, dict) or not isinstance(data.get("current"), dict):
            self.set_error("weather", "The weather service returned malformed data.")
            return
        current = data["current"]
        code = current.get("weather_code")
        if not isinstance(code, int):
            code = None
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
        self._last_good_details = (
            f"{data.get('place_name', self._last_location)}\n"
            f"Feels like {current.get('apparent_temperature', '—')}°  ·  "
            f"Humidity {current.get('relative_humidity_2m', '—')}%"
        )
        self._has_data = True
        self.details.setText(self._last_good_details + "\nUpdated just now")
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(json.dumps({
                "location": self._last_location,
                "data": data,
            }), encoding="utf-8")
        except OSError:
            log.debug("Could not cache weather data", exc_info=True)

    @Slot(str, str)
    def set_error(self, kind, message):
        if kind == "weather":
            self._busy = False
            self._fetch_task = None
            if str(self.config.get("widgets.weather_location", "") or "").strip() != self._last_location:
                self._last_location = ""
                self.refresh()
                return
            if self._has_data:
                self.details.setText(self._last_good_details + "\nOffline · showing last successful update")
            else:
                self.value.setText("Weather unavailable")
                self.details.setText(("Offline · " + message)[:110])


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
        self._last_good_item = None
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
                self._last_good_item = cached
                self._show_meme(cached)
                return
            if isinstance(cached, dict) and isinstance(cached.get("title"), str) and cached.get("title"):
                self._last_good_item = cached
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
        self._last_good_item = item
        self.retry_timer.stop()
        self._show_meme(item)
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(json.dumps(item), encoding="utf-8")
        except OSError:
            log.debug("Could not cache daily meme", exc_info=True)

    @Slot(str, str)
    def set_error(self, kind, message):
        if kind != "meme":
            return
        self._busy = False
        self._fetch_task = None
        self._cached_date = datetime.now().date().isoformat()
        # A request may finish after the user disables this card. Do not
        # restart its retry timer while it is explicitly hidden.
        if not self.isHidden():
            self.retry_timer.start(15 * 60 * 1000)
        if self._last_good_item:
            self._show_meme(self._last_good_item)
            subreddit = self._last_good_item.get("subreddit", "reddit")
            self.subreddit.setText("r/" + str(subreddit) + "  ·  cached offline copy")
        else:
            self.title.setText("Meme unavailable")
            self.subreddit.setText("Offline · no cached meme available")

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


class TasksWidget(WidgetCard):
    """Small local task summary; refreshes only while the launcher is visible."""

    def __init__(self, service, hooks, parent=None):
        super().__init__("Tasks", parent)
        self.service = service
        self.hooks = hooks
        self.summary = QLabel("Loading tasks…")
        self.summary.setObjectName("WidgetValue")
        self.content.addWidget(self.summary)
        self.task_labels = []
        for _ in range(2):
            item = QLabel()
            item.setObjectName("WidgetSecondary")
            item.setWordWrap(True)
            self.content.addWidget(item)
            self.task_labels.append(item)
        self.open_button = QPushButton("Open tasks")
        self.open_button.setFixedHeight(24)
        self.open_button.clicked.connect(self._open_tasks)
        self.content.addWidget(self.open_button)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.refresh()

    def _open_tasks(self):
        if self.hooks is not None:
            self.hooks.open_tools("tasks")
            self.hooks.hide_launcher()

    def refresh(self):
        try:
            rows = self.service.tasks(include_completed=False) if self.service is not None else []
            today = datetime.now().date().isoformat()
            rows = [row for row in rows if not row.get("completed")]
            rows.sort(key=lambda row: (
                not bool(row.get("due_date")),
                str(row.get("due_date") or "9999-12-31"),
                str(row.get("title", "")).casefold(),
            ))
            overdue = sum(1 for row in rows if row.get("due_date") and row["due_date"] < today)
            self.summary.setText(f"{len(rows)} open  ·  {overdue} overdue")
            for index, label_widget in enumerate(self.task_labels):
                if index < len(rows):
                    row = rows[index]
                    due = row.get("due_date") or "No due date"
                    label_widget.setText(f"• {str(row.get('title', 'Task'))[:26]}  ·  {due}")
                    label_widget.setVisible(True)
                else:
                    label_widget.clear()
                    label_widget.setVisible(False)
        except Exception:
            log.debug("Task widget refresh failed", exc_info=True)
            self.summary.setText("Tasks unavailable")
            for label_widget in self.task_labels:
                label_widget.clear()


class _MediaSignals(QObject):
    finished = Signal(str, object)
    failed = Signal(str, str)


class _MediaTask(QRunnable):
    def __init__(self, action: str):
        super().__init__()
        self.setAutoDelete(False)
        self.action = action
        self.signals = _MediaSignals()

    def run(self) -> None:
        try:
            if self.action == "refresh":
                from features.media import get_current_media
                result = get_current_media()
            else:
                from features.media import control_current_media
                result = control_current_media(self.action)
            self.signals.finished.emit(self.action, result)
        except Exception as exc:
            self.signals.failed.emit(self.action, str(exc))


class MediaWidget(WidgetCard):
    """Optional Windows system-media widget; WinRT work stays off the GUI thread."""

    def __init__(self, pool: QThreadPool, parent=None):
        super().__init__("Now playing", parent)
        self.pool = pool
        self._task = None
        self._busy = False
        self.title = QLabel("No active media session")
        self.title.setObjectName("WidgetValue")
        self.title.setWordWrap(True)
        self.artist = QLabel("Play media in a supported Windows app")
        self.artist.setObjectName("WidgetSecondary")
        self.status = QLabel("Media controls are optional")
        self.status.setObjectName("WidgetSecondary")
        self.content.addWidget(self.title)
        self.content.addWidget(self.artist)
        self.content.addWidget(self.status)
        controls = QHBoxLayout()
        self.previous_button = QPushButton("Previous")
        self.play_pause_button = QPushButton("Play")
        self.next_button = QPushButton("Next")
        for button in (self.previous_button, self.play_pause_button, self.next_button):
            button.setFixedHeight(25)
            controls.addWidget(button)
        self.previous_button.clicked.connect(lambda: self._run("previous"))
        self.play_pause_button.clicked.connect(self._toggle_play_pause)
        self.next_button.clicked.connect(lambda: self._run("next"))
        self.content.addLayout(controls)
        self._set_controls(False, False, False)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.setInterval(10_000)

    def _set_controls(self, previous: bool, toggle: bool, next_track: bool) -> None:
        self.previous_button.setEnabled(previous)
        self.play_pause_button.setEnabled(toggle)
        self.next_button.setEnabled(next_track)

    def _toggle_play_pause(self) -> None:
        self._run("toggle")

    def _run(self, action: str) -> None:
        if self._busy:
            return
        self._busy = True
        task = _MediaTask(action)
        self._task = task
        task.signals.finished.connect(self._finished)
        task.signals.failed.connect(self._failed)
        self.pool.start(task)

    def refresh(self) -> None:
        self._run("refresh")

    @Slot(str, object)
    def _finished(self, action: str, result) -> None:
        self._busy = False
        self._task = None
        if action == "refresh":
            self.set_media(result)
        else:
            self.status.setText("Playback command sent" if result else "No active media session")
            QTimer.singleShot(350, self.refresh)

    @Slot(str, str)
    def _failed(self, action: str, message: str) -> None:
        self._busy = False
        self._task = None
        if action == "refresh":
            self.title.setText("Media unavailable")
            self.artist.setText("Windows media-session API is not available")
            self.status.setText(message[:90])
            self._set_controls(False, False, False)
        else:
            self.status.setText(("Media command failed: " + message)[:100])

    def set_media(self, data) -> None:
        if not isinstance(data, dict):
            self.title.setText("No active media session")
            self.artist.setText("Play media in a supported Windows app")
            self.status.setText("No current session")
            self._set_controls(False, False, False)
            return
        self.title.setText(data.get("title") or "Unknown track")
        details = " · ".join(part for part in (data.get("artist", ""), data.get("album", "")) if part)
        self.artist.setText(details or data.get("source") or "Unknown artist")
        state = str(data.get("status", "unknown")).replace("_", " ").title()
        self.status.setText(state + ((" · " + data["source"]) if data.get("source") else ""))
        toggle = bool(data.get("can_toggle") or data.get("can_play") or data.get("can_pause"))
        self.play_pause_button.setText("Pause" if data.get("status") == "playing" else "Play")
        self._set_controls(bool(data.get("can_previous")), toggle, bool(data.get("can_next")))


class LauncherWidgets(QObject):
    """Owns the four optional widgets, split into two side rails."""

    def __init__(self, config, parent=None, task_service=None, hooks=None):
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
        self.left_column.setFixedWidth(int(self.config.get("widgets.rail_width", 196)))
        self.right_column.setFixedWidth(int(self.config.get("widgets.rail_width", 196)))
        self._left_layout = QVBoxLayout(self.left_column)
        self._right_layout = QVBoxLayout(self.right_column)
        for layout in (self._left_layout, self._right_layout):
            layout.setContentsMargins(0, 8, 0, 8)
            layout.setSpacing(9)

        self.clock = ClockWidget(config, self.left_column)
        self.system = SystemWidget(self.left_column)
        self.tasks = TasksWidget(task_service, hooks, self.left_column)
        self.weather = WeatherWidget(config, self.pool, self.right_column)
        self.meme = MemeWidget(self.pool, self.right_column)
        self.media = MediaWidget(self.pool, self.right_column)
        self._cards = {"clock": self.clock, "weather": self.weather, "system": self.system, "meme": self.meme, "tasks": self.tasks, "media": self.media}
        self._apply_order()
        for key, card in self._cards.items():
            card.setMinimumHeight(int(self.config.get("widgets.card_height", 140)))
            card.setMaximumHeight(int(self.config.get("widgets.card_height", 140)) + (72 if key == "system" else 56 if key == "clock" else 20 if key == "tasks" else 28))
            card.setContentsMargins(0, 0, 0, 0)
        self._apply_card_theme()
        self._rebuild()

    def _apply_order(self):
        """Reorder persistent cards inside their existing rails without reparenting."""
        for layout, keys, stretch in (
            (self._left_layout, self.config.get("widgets.left_order", ["clock", "system", "tasks"]), ("clock", "system", "tasks")),
            (self._right_layout, self.config.get("widgets.right_order", ["weather", "meme", "media"]), ("weather", "meme", "media")),
        ):
            while layout.count():
                item = layout.takeAt(0)
                if item.widget() is not None:
                    layout.removeWidget(item.widget())
            order = [key for key in keys if key in stretch]
            order.extend(key for key in stretch if key not in order)
            for key in order:
                layout.addWidget(self._cards[key])
            layout.addStretch(1)

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
        self._apply_order()
        width = int(self.config.get("widgets.rail_width", 196))
        self.left_column.setFixedWidth(width)
        self.right_column.setFixedWidth(width)
        card_height = int(self.config.get("widgets.card_height", 140))
        for key, card in self._cards.items():
            card.setMinimumHeight(card_height)
            card.setMaximumHeight(card_height + (72 if key == "system" else 56 if key == "clock" else 20 if key == "tasks" else 28))
        # Cards may move between layout positions, but remain permanent children
        # of their original rail. No refresh recreates or reparents a live widget.
        for key in ("clock", "system", "tasks", "weather", "meme", "media"):
            card = self._cards[key]
            enabled = bool(self.config.get(f"widgets.{key}_enabled", True))
            card.setVisible(enabled)
            card.reveal(False)

        self._sync_timers()
        self.left_column.setVisible(
            any(bool(self.config.get(f"widgets.{key}_enabled", True)) for key in ("clock", "system", "tasks"))
        )
        self.right_column.setVisible(
            any(bool(self.config.get(f"widgets.{key}_enabled", True)) for key in ("weather", "meme", "media"))
        )

    def _sync_timers(self):
        """Poll live data only while its rail is enabled and the launcher is visible."""
        for key, card in self._cards.items():
            enabled = bool(self.config.get(f"widgets.{key}_enabled", True))
            running = self._active and enabled
            if key == "clock":
                card.timer.start(int(self.config.get("widgets.clock_refresh_ms", 1000))) if running else card.timer.stop()
                if running:
                    card.refresh()
            elif key == "system":
                card.timer.start(int(self.config.get("widgets.system_refresh_ms", 2000))) if running else card.timer.stop()
                if running:
                    card.refresh()
            elif key == "tasks":
                interval = int(self.config.get("widgets.tasks_refresh_minutes", 5)) * 60 * 1000
                card.timer.start(interval) if running else card.timer.stop()
                if running:
                    card.refresh()
            elif key == "weather":
                interval = int(self.config.get("widgets.weather_refresh_minutes", 30)) * 60 * 1000
                card.timer.start(interval) if running else card.timer.stop()
            elif key == "meme":
                interval = int(self.config.get("widgets.meme_refresh_minutes", 60)) * 60 * 1000
                card.day_timer.start(interval) if running else card.day_timer.stop()
                if not running:
                    card.retry_timer.stop()
            elif key == "media":
                interval = int(self.config.get("widgets.media_refresh_seconds", 10)) * 1000
                card.timer.start(interval) if running else card.timer.stop()

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
            if self.config.get("widgets.media_enabled", False):
                self.media.refresh()

        self.left_column.setVisible(
            any(bool(self.config.get(f"widgets.{key}_enabled", True)) for key in ("clock", "system", "tasks"))
        )
        self.right_column.setVisible(
            any(bool(self.config.get(f"widgets.{key}_enabled", True)) for key in ("weather", "meme", "media"))
        )

    def refresh_settings(self, animate=False):
        self._apply_card_theme()
        self._rebuild()
        if self._active and self.config.get("widgets.weather_enabled", True):
            self.weather._last_location = ""
            self.weather.refresh()
        if self._active and self.config.get("widgets.meme_enabled", True):
            self.meme._load_daily()
        if self._active and self.config.get("widgets.media_enabled", False):
            self.media.refresh()
        if animate:
            for card in self._cards.values():
                if card.isVisible():
                    card.reveal(True)

