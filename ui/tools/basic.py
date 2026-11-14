"""Calculator, developer utilities, date/time, color and dictionary pages."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any, Callable, Optional

from PySide6.QtCore import QDateTime, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QComboBox,
    QDateTimeEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.logging_setup import get_logger
from core.workers import run_async
from features import date_time, developer_tools, dictionary
from features.developer_tools import ToolError
from ui.components import ScrollPage, SectionCard, danger_button, label, primary_button, secondary_button

log = get_logger(__name__)


def _copy(text: str) -> None:
    clipboard = QGuiApplication.clipboard()
    if clipboard is not None:
        clipboard.setText(text or "")


class ToolCard(QFrame):
    """A small input → output utility card."""

    def __init__(
        self,
        title: str,
        description: str = "",
        input_placeholder: str = "",
        with_input: bool = True,
        input_height: int = 70,
    ):
        super().__init__()
        self.setObjectName("Card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)
        heading = label(title, "Title")
        layout.addWidget(heading)
        if description:
            layout.addWidget(label(description, "Muted", wrap=True))

        self.input: Optional[QPlainTextEdit] = None
        self.buttons = QHBoxLayout()
        self.buttons.setSpacing(6)
        self.body = QVBoxLayout()
        if with_input:
            self.input = QPlainTextEdit()
            self.input.setPlaceholderText(input_placeholder)
            self.input.setFixedHeight(input_height)
            layout.addWidget(self.input)
        layout.addLayout(self.body)
        layout.addLayout(self.buttons)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setFixedHeight(input_height)
        self.output.setPlaceholderText("Result appears here")
        layout.addWidget(self.output)

        self._extra = QHBoxLayout()
        self._extra.addStretch(1)
        self._extra.addWidget(secondary_button("Copy result", self.copy_output))
        layout.addLayout(self._extra)

    def add_button(self, text: str, handler: Callable[[str], str], primary: bool = False) -> QPushButton:
        button = primary_button(text) if primary else secondary_button(text)
        button.clicked.connect(lambda: self.run(handler))
        self.buttons.addWidget(button)
        return button

    def add_widget(self, widget: QWidget) -> QWidget:
        self.body.addWidget(widget)
        return widget

    def run(self, handler: Callable[[str], str]) -> None:
        text = self.input.toPlainText() if self.input is not None else ""
        try:
            result = handler(text)
        except ToolError as exc:
            self.set_output(f"Error: {exc}")
        except Exception as exc:  # pragma: no cover - defensive
            log.exception("Developer tool failed")
            self.set_output(f"Unexpected error: {exc}")
        else:
            self.set_output(result if isinstance(result, str) else str(result))

    def set_output(self, text: str) -> None:
        self.output.setPlainText(text)

    def copy_output(self) -> None:
        _copy(self.output.toPlainText())


class CalculatorTab(QWidget):
    """Interactive calculator with live results and history."""

    def __init__(self, controller, window):
        super().__init__()
        self.controller = controller
        self.service = controller.calculator_service
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(16)

        left = QVBoxLayout()
        left.setSpacing(10)
        heading = label("Calculator", "Heading")
        left.addWidget(heading)
        left.addWidget(
            label("Enter an expression. Supported: + − × ÷, powers, roots, trigonometry, logarithms, percentages and unit conversions.", "Muted", wrap=True)
        )
        self.expression = QLineEdit()
        self.expression.setPlaceholderText("sqrt(144) + 25 * 4")
        self.expression.setMinimumHeight(42)
        self.expression.textChanged.connect(self._evaluate)
        self.expression.returnPressed.connect(self._copy_result)
        left.addWidget(self.expression)

        self.result = QLabel("—")
        self.result.setObjectName("Heading")
        self.result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        left.addWidget(self.result)

        self.detail = label("Enter copies the result", "Muted", wrap=True)
        left.addWidget(self.detail)

        buttons = QHBoxLayout()
        buttons.addWidget(primary_button("Copy result", self._copy_result))
        buttons.addWidget(secondary_button("Copy expression and result", self._copy_full))
        buttons.addStretch(1)
        left.addLayout(buttons)
        left.addStretch(1)
        layout.addLayout(left, 3)

        right = QVBoxLayout()
        right.setSpacing(8)
        right.addWidget(label("History", "Title"))
        self.history = QListWidget()
        self.history.setObjectName("PlainList")
        self.history.itemClicked.connect(self._use_history)
        right.addWidget(self.history, 1)
        right.addWidget(danger_button("Clear history", self._clear_history))
        layout.addLayout(right, 2)
        self._current: Optional[Any] = None
        self.refresh_history()

    def _evaluate(self) -> None:
        text = self.expression.text()
        if not text.strip():
            self.result.setText("—")
            self.detail.setText("Enter copies the result")
            self._current = None
            return
        outcome = self.service.evaluate_text(text)
        if outcome.ok:
            self.result.setText(outcome.result)
            self.detail.setText(f"{outcome.expression}   ·   Enter copies the result")
            self._current = outcome
        else:
            self.result.setText("—")
            self.detail.setText(outcome.error)
            self._current = None

    def _copy_result(self) -> None:
        if self._current is None:
            return
        _copy(self._current.result)
        self.service.record(self._current)
        self.detail.setText(f"Copied {self._current.result}")
        self.refresh_history()

    def _copy_full(self) -> None:
        if self._current is None:
            return
        _copy(f"{self._current.expression} = {self._current.result}")
        self.service.record(self._current)
        self.refresh_history()

    def _use_history(self, item) -> None:
        text = item.data(Qt.ItemDataRole.UserRole)
        if text:
            self.expression.setText(str(text))

    def _clear_history(self) -> None:
        self.service.clear_history()
        self.refresh_history()

    def refresh_history(self) -> None:
        self.history.clear()
        entries = self.service.history(100)
        if not entries:
            self.history.addItem("No calculations yet")
            return
        for entry in entries:
            item = QListWidgetItem(entry)
            expression = entry.split(" = ")[0]
            item.setData(Qt.ItemDataRole.UserRole, expression)
            self.history.addItem(item)

    def on_show(self) -> None:
        self.refresh_history()
        self.expression.setFocus(Qt.FocusReason.OtherFocusReason)


class DeveloperTab(ScrollPage):
    """Fifteen developer utilities in one place."""

    def __init__(self, controller, window):
        super().__init__()
        self.controller = controller
        heading = label("Developer tools", "Heading")
        self.layout.addWidget(heading)
        self.layout.addWidget(label("All conversions run locally and never leave your computer.", "Muted", wrap=True))

        uuid_card = ToolCard("UUID generator", "Generate version 1 or version 4 identifiers.", with_input=False, input_height=54)
        uuid_card.add_button("Generate v4", lambda _text: developer_tools.generate_uuid(4), primary=True)
        uuid_card.add_button("Generate v1", lambda _text: developer_tools.generate_uuid(1))
        self.layout.addWidget(uuid_card)

        base64_card = ToolCard("Base64", "Encode text to Base64 or decode Base64 back to text.", "Hello, SeekR")
        base64_card.add_button("Encode", developer_tools.base64_encode, primary=True)
        base64_card.add_button("Decode", developer_tools.base64_decode)
        self.layout.addWidget(base64_card)

        json_card = ToolCard("JSON", "Format, minify or validate a JSON document.", '{"name":"SeekR","version":"1.0.0"}')
        json_card.add_button("Format", lambda text: developer_tools.json_format(text, indent=2), primary=True)
        json_card.add_button("Minify", developer_tools.json_minify)
        json_card.add_button("Validate", lambda text: developer_tools.json_validate(text)[1])
        self.layout.addWidget(json_card)

        url_card = ToolCard("URL encoding", "Percent-encode or decode text for use in URLs.", "https://example.com/?q=hello world")
        url_card.add_button("Encode", developer_tools.url_encode, primary=True)
        url_card.add_button("Decode", developer_tools.url_decode)
        self.layout.addWidget(url_card)

        hash_card = ToolCard("Hash generator", "MD5, SHA-1, SHA-2 and BLAKE2 digests.", "SeekR")
        algorithm = QComboBox()
        for name in developer_tools.HASH_ALGORITHMS:
            algorithm.addItem(name.upper(), name)
        hash_card.add_widget(algorithm)
        hash_card.add_button(
            "Generate hash",
            lambda text: developer_tools.hash_text(text, algorithm.currentData()),
            primary=True,
        )
        self.layout.addWidget(hash_card)

        regex_card = QFrame()
        regex_card.setObjectName("Card")
        regex_layout = QVBoxLayout(regex_card)
        regex_layout.setContentsMargins(16, 14, 16, 14)
        regex_layout.addWidget(label("Regex tester", "Title"))
        regex_layout.addWidget(label("Python regular expressions with optional i, m, s and x flags.", "Muted"))
        pattern_row = QHBoxLayout()
        self.regex_pattern = QLineEdit()
        self.regex_pattern.setPlaceholderText(r"\b[A-Z]\w+\b")
        self.regex_flags = QLineEdit()
        self.regex_flags.setPlaceholderText("i")
        self.regex_flags.setFixedWidth(70)
        pattern_row.addWidget(self.regex_pattern, 1)
        pattern_row.addWidget(self.regex_flags)
        regex_layout.addLayout(pattern_row)
        self.regex_text = QPlainTextEdit()
        self.regex_text.setPlaceholderText("Text to test")
        self.regex_text.setFixedHeight(70)
        regex_layout.addWidget(self.regex_text)
        self.regex_output = QPlainTextEdit()
        self.regex_output.setReadOnly(True)
        self.regex_output.setFixedHeight(90)
        regex_layout.addWidget(self.regex_output)
        regex_buttons = QHBoxLayout()
        regex_buttons.addWidget(primary_button("Test", self._run_regex))
        regex_buttons.addStretch(1)
        regex_buttons.addWidget(secondary_button("Copy result", lambda: _copy(self.regex_output.toPlainText())))
        regex_layout.addLayout(regex_buttons)
        self.layout.addWidget(regex_card)

        timestamp_card = ToolCard("Timestamp converter", "Convert epoch timestamps and human-readable dates.", "2026-01-31 14:30")
        timestamp_card.add_button("Date → epoch", lambda text: f"{developer_tools.datetime_to_timestamp(text):.0f}", primary=True)
        timestamp_card.add_button("Epoch → date", lambda text: developer_tools.timestamp_to_datetime(float(text.strip() or "0")))
        timestamp_card.add_button("Now", lambda _text: "\n".join(f"{key}: {value}" for key, value in developer_tools.now_info().items()))
        self.layout.addWidget(timestamp_card)

        case_card = ToolCard("Text case", "Convert text between common naming conventions.", "hello world example")
        for mode, text in (
            ("UPPER", "upper"),
            ("lower", "lower"),
            ("Title", "title"),
            ("snake_case", "snake"),
            ("kebab-case", "kebab"),
            ("camelCase", "camel"),
            ("PascalCase", "pascal"),
            ("CONSTANT", "constant"),
        ):
            case_card.add_button(text, lambda value, m=mode: developer_tools.change_case(value, m))
        self.layout.addWidget(case_card)

        hex_card = ToolCard("Hexadecimal", "Convert text to hexadecimal bytes and back.", "SeekR")
        hex_card.add_button("Text → hex", developer_tools.text_to_hex, primary=True)
        hex_card.add_button("Hex → text", developer_tools.hex_to_text)
        hex_card.add_button("Text → binary", developer_tools.text_to_binary)
        hex_card.add_button("Binary → text", developer_tools.binary_to_text)
        self.layout.addWidget(hex_card)

        self.counter_card = ToolCard("Character and word counter", "Counts update while you type.", "Count these words and characters")
        self.counter_label = label("", "Muted", wrap=True)
        self.counter_card.body.addWidget(self.counter_label)
        self.counter_card.input.textChanged.connect(self._count)
        self.layout.addWidget(self.counter_card)
        self._count()

        color_card = ToolCard("Color converter", "Hex, RGB, HSL and HSV conversion lives in the Color tab.", with_input=False, input_height=0)
        color_card.output.hide()
        color_card.add_button("Open color tools", lambda _text: window.open_page("color"), primary=True)
        self.layout.addWidget(color_card)
        self.layout.addStretch(1)

    def _run_regex(self) -> None:
        try:
            result = developer_tools.test_regex(
                self.regex_pattern.text(), self.regex_text.toPlainText(), self.regex_flags.text()
            )
        except ToolError as exc:
            self.regex_output.setPlainText(f"Error: {exc}")
            return
        lines = [f"{result['count']} match(es)"]
        for index, match in enumerate(result["matches"][:80], start=1):
            lines.append(f"{index:>3}. '{match['match']}'  [{match['start']}–{match['end']}]  groups={match['groups']}")
            if match["named"]:
                lines.append(f"     named={match['named']}")
        if result["truncated"]:
            lines.append("… output truncated")
        self.regex_output.setPlainText("\n".join(lines))

    def _count(self) -> None:
        counts = developer_tools.count_text(self.counter_card.input.toPlainText())
        self.counter_label.setText(
            f"{counts['characters']} characters  ·  {counts['characters_no_spaces']} without spaces  ·  "
            f"{counts['words']} words  ·  {counts['lines']} lines  ·  {counts['sentences']} sentences  ·  "
            f"{counts['paragraphs']} paragraphs"
        )


class DateTimeTab(ScrollPage):
    """Current time, zone conversion, differences and countdown."""

    def __init__(self, controller, window):
        super().__init__()
        self.controller = controller
        self.config = controller.config
        self.layout.addWidget(label("Date and time", "Heading"))
        self.layout.addWidget(label("Live clock, time zone conversion, date differences and a countdown timer.", "Muted", wrap=True))

        clock = self.section("Clock")
        self.clock_label = label("", "Heading")
        clock.add_widget(self.clock_label)
        self.clock_detail = label("", "Muted", wrap=True)
        clock.add_widget(self.clock_detail)
        self.epoch_label = label("", "Muted")
        clock.add_widget(self.epoch_label)
        format_row = QHBoxLayout()
        self.format_edit = QLineEdit(str(self.config.get("date_time.format", "%Y-%m-%d %H:%M:%S")))
        self.format_edit.setMaximumWidth(260)
        self.format_edit.editingFinished.connect(self._save_format)
        format_row.addWidget(label("Format", "Muted"))
        format_row.addWidget(self.format_edit)
        format_row.addStretch(1)
        format_holder = QWidget()
        format_holder.setLayout(format_row)
        clock.add_widget(format_holder)

        converter = self.section("Time zone conversion")
        zone_row = QGridLayout()
        self.source_zone = QComboBox()
        self.target_zone = QComboBox()
        zones = sorted(date_time.zone_names())
        for zone in zones:
            self.source_zone.addItem(zone, zone)
            self.target_zone.addItem(zone, zone)
        for combo, preferred in ((self.source_zone, "local"), (self.target_zone, "Europe/Istanbul")):
            index = combo.findData(preferred)
            if index >= 0:
                combo.setCurrentIndex(index)
        self.time_input = QLineEdit()
        self.time_input.setPlaceholderText("Now, or e.g. 14:30 / 2026-01-31 14:30")
        zone_row.addWidget(label("From", "Muted"), 0, 0)
        zone_row.addWidget(self.source_zone, 0, 1, 1, 2)
        zone_row.addWidget(label("To", "Muted"), 1, 0)
        zone_row.addWidget(self.target_zone, 1, 1, 1, 2)
        zone_row.addWidget(self.time_input, 2, 0, 1, 2)
        convert_button = primary_button("Convert", self._convert)
        zone_row.addWidget(convert_button, 2, 2)
        zone_row.setColumnStretch(1, 1)
        zones_holder = QWidget()
        zones_holder.setLayout(zone_row)
        converter.add_widget(zones_holder)
        self.convert_result = label("", "Title")
        converter.add_widget(self.convert_result)
        self.convert_detail = label("", "Muted", wrap=True)
        converter.add_widget(self.convert_detail)

        difference = self.section("Date difference")
        diff_row = QHBoxLayout()
        self.date_a = QDateTimeEdit(QDateTime.currentDateTime())
        self.date_a.setCalendarPopup(True)
        self.date_a.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.date_b = QDateTimeEdit(QDateTime.currentDateTime().addDays(7))
        self.date_b.setCalendarPopup(True)
        self.date_b.setDisplayFormat("yyyy-MM-dd HH:mm")
        diff_row.addWidget(self.date_a, 1)
        diff_row.addWidget(label("→", "Muted"))
        diff_row.addWidget(self.date_b, 1)
        diff_row.addWidget(primary_button("Calculate", self._difference))
        diff_holder = QWidget()
        diff_holder.setLayout(diff_row)
        difference.add_widget(diff_holder)
        self.diff_result = label("", "Muted", wrap=True)
        difference.add_widget(self.diff_result)

        countdown = self.section("Countdown timer")
        countdown_row = QHBoxLayout()
        self.countdown_minutes = QSpinBox()
        self.countdown_minutes.setRange(1, 600)
        self.countdown_minutes.setValue(5)
        self.countdown_minutes.setSuffix(" min")
        self.countdown_start = primary_button("Start", self._start_countdown)
        self.countdown_stop = secondary_button("Stop", self._stop_countdown)
        self.countdown_label = label("", "Title")
        countdown_row.addWidget(self.countdown_minutes)
        countdown_row.addWidget(self.countdown_start)
        countdown_row.addWidget(self.countdown_stop)
        countdown_row.addStretch(1)
        countdown_holder = QWidget()
        countdown_holder.setLayout(countdown_row)
        countdown.add_widget(countdown_holder)
        countdown.add_widget(self.countdown_label)

        self._remaining = 0
        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._tick_countdown)

        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(1000)
        self._clock_timer.timeout.connect(self._update_clock)
        self._started = False
        self.layout.addStretch(1)

    def section(self, title: str) -> SectionCard:
        card = SectionCard(title)
        self.layout.addWidget(card)
        return card

    def showEvent(self, event) -> None:  # noqa: N802
        self._clock_timer.start()
        self._update_clock()
        super().showEvent(event)

    def hideEvent(self, event) -> None:  # noqa: N802
        self._clock_timer.stop()
        super().hideEvent(event)

    def _update_clock(self) -> None:
        fmt = str(self.config.get("date_time.format", "%Y-%m-%d %H:%M:%S"))
        moment = date_time.now()
        self.clock_label.setText(moment.strftime(fmt))
        self.clock_detail.setText(
            f"{moment.strftime('%A, %d %B %Y')}  ·  {date_time.utc_offset(moment)}  ·  "
            f"{moment.tzname() or 'local time'}"
        )
        info = developer_tools.now_info()
        self.epoch_label.setText(f"ISO {info['iso']}   ·   epoch {info['epoch']}   ·   UTC {info['utc']}")

    def _save_format(self) -> None:
        self.config.set("date_time.format", self.format_edit.text().strip() or "%Y-%m-%d %H:%M:%S")
        self._update_clock()

    def _convert(self) -> None:
        source = self.source_zone.currentData()
        target = self.target_zone.currentData()
        text = self.time_input.text().strip()
        try:
            if not text or text.lower() == "now":
                moment = date_time.now(None if source == "local" else source)
            else:
                moment = date_time.parse_datetime(text, default_zone=None if source == "local" else source)
            converted = date_time.convert(moment, target)
        except (date_time.TimeZoneError, ValueError) as exc:
            self.convert_result.setText("Cannot convert")
            self.convert_detail.setText(str(exc))
            return
        fmt = str(self.config.get("date_time.format", "%Y-%m-%d %H:%M:%S"))
        self.convert_result.setText(converted.strftime(fmt))
        self.convert_detail.setText(
            f"{target}  ·  {converted.strftime('%A')}  ·  {date_time.utc_offset(converted)}"
        )

    def _difference(self) -> None:
        first = self.date_a.dateTime().toPython()
        second = self.date_b.dateTime().toPython()
        if first.tzinfo is None:
            first = first.astimezone()
        if second.tzinfo is None:
            second = second.astimezone()
        delta = date_time.date_difference(first, second)
        days = delta.days
        seconds = delta.seconds
        hours, remainder = divmod(seconds, 3600)
        minutes = remainder // 60
        self.diff_result.setText(
            f"{abs(days)} days, {hours} hours and {minutes} minutes  "
            f"({date_time.describe_delta(delta)})"
        )

    def _start_countdown(self) -> None:
        self._remaining = self.countdown_minutes.value() * 60
        self._countdown_timer.start()
        self._update_countdown_label()

    def _stop_countdown(self) -> None:
        self._countdown_timer.stop()
        self._remaining = 0
        self.countdown_label.setText("Countdown stopped")

    def _tick_countdown(self) -> None:
        self._remaining = max(0, self._remaining - 1)
        self._update_countdown_label()
        if self._remaining == 0:
            self._countdown_timer.stop()
            QApplication.beep()
            self.countdown_label.setText("Time is up!")
            self.controller.notify("Countdown finished")

    def _update_countdown_label(self) -> None:
        minutes, seconds = divmod(self._remaining, 60)
        self.countdown_label.setText(f"{minutes:02d}:{seconds:02d} remaining")


class ColorTab(QWidget):
    """Color picker with every common representation."""

    def __init__(self, controller, window):
        super().__init__()
        self.controller = controller
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(24)

        left = QVBoxLayout()
        left.setSpacing(10)
        left.addWidget(label("Color picker", "Heading"))
        left.addWidget(label("Pick a color or type a value such as #ff8800 or rgb(255, 136, 0).", "Muted", wrap=True))
        self.swatch = QLabel()
        self.swatch.setFixedSize(180, 180)
        self.swatch.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left.addWidget(self.swatch)
        self.input = QLineEdit("#7c5cff")
        self.input.editingFinished.connect(self._parse_input)
        left.addWidget(self.input)
        buttons = QHBoxLayout()
        buttons.addWidget(primary_button("Choose color…", self._choose))
        buttons.addWidget(secondary_button("Copy HEX", lambda: _copy(self.values.get("hex", ""))))
        left.addLayout(buttons)
        left.addStretch(1)
        layout.addLayout(left, 1)

        right = QVBoxLayout()
        right.setSpacing(8)
        right.addWidget(label("Values", "Title"))
        self.value_labels: dict[str, QLabel] = {}
        for key, title in (
            ("hex", "HEX"),
            ("rgb", "RGB"),
            ("hsl", "HSL"),
            ("hsv", "HSV"),
            ("decimal", "Decimal"),
        ):
            row = QHBoxLayout()
            row.addWidget(label(title, "Muted"))
            value = label("", "Title")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            row.addWidget(value, 1)
            copy_button = secondary_button("Copy")
            copy_button.clicked.connect(lambda _checked=False, k=key: _copy(self.values.get(k, "")))
            row.addWidget(copy_button)
            right.addLayout(row)
            self.value_labels[key] = value
            right.addWidget(_row_divider())
        right.addStretch(1)
        layout.addLayout(right, 2)

        self.values: dict[str, str] = {}
        self._set_color(QColor("#7c5cff"))

    def _set_color(self, color: QColor) -> None:
        if not color.isValid():
            return
        self.values = developer_tools.color_formats(color.name())
        self.input.setText(self.values["hex"])
        for key, widget in self.value_labels.items():
            widget.setText(self.values.get(key, ""))
        text_color = "#101116" if color.lightness() > 150 else "#ffffff"
        self.swatch.setStyleSheet(
            f"background: {color.name()}; color: {text_color}; border-radius: 14px; font-weight: 600;"
        )
        self.swatch.setText(color.name().upper())

    def _choose(self) -> None:
        color = QColorDialog.getColor(QColor(self.values.get("hex", "#7c5cff")), self, "Choose color")
        if color.isValid():
            self._set_color(color)

    def _parse_input(self) -> None:
        try:
            color = QColor(developer_tools.to_hex(self.input.text().strip()))
        except ToolError as exc:
            self.input.setText(self.values.get("hex", ""))
            self.controller.show_error("Color", str(exc))
            return
        if color.isValid():
            self._set_color(color)


def _row_divider() -> QWidget:
    widget = QWidget()
    widget.setFixedHeight(1)
    widget.setStyleSheet("background: rgba(128,128,128,0.25);")
    return widget


class DictionaryTab(QWidget):
    """Dictionary lookups with offline-friendly errors."""

    def __init__(self, controller, window):
        super().__init__()
        self.controller = controller
        self._busy = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        layout.addWidget(label("Dictionary", "Heading"))
        layout.addWidget(
            label(
                "Definitions are fetched from dictionaryapi.dev. An internet connection is required; "
                "nothing is sent except the word you look up.",
                "Muted",
                wrap=True,
            )
        )
        row = QHBoxLayout()
        self.word_edit = QLineEdit()
        self.word_edit.setPlaceholderText("algorithm")
        self.word_edit.returnPressed.connect(self.lookup_current)
        row.addWidget(self.word_edit, 1)
        row.addWidget(primary_button("Look up", self.lookup_current))
        self.web_button = secondary_button("Open Merriam-Webster", self._open_web)
        row.addWidget(self.web_button)
        layout.addLayout(row)
        self.status = label("", "Muted", wrap=True)
        layout.addWidget(self.status)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("Definitions appear here")
        layout.addWidget(self.output, 1)
        copy_row = QHBoxLayout()
        copy_row.addWidget(secondary_button("Copy definition", lambda: _copy(self.output.toPlainText())))
        copy_row.addStretch(1)
        layout.addLayout(copy_row)

    def lookup_current(self) -> None:
        self.lookup(self.word_edit.text().strip())

    def lookup(self, word: str) -> None:
        word = (word or "").strip()
        if not word:
            self.status.setText("Enter a word to look up")
            return
        if self._busy:
            return
        self._busy = True
        self.word_edit.setText(word)
        self.status.setText(f"Looking up “{word}”…")
        self.output.clear()
        run_async(
            dictionary.lookup,
            word,
            on_finished=self._done,
            on_failed=self._failed,
        )

    def _done(self, result: dict) -> None:
        self._busy = False
        self.output.setPlainText(dictionary.format_definition(result))
        self.status.setText(f"{len(result.get('meanings', []))} definitions found")

    def _failed(self, message: str, _traceback: str) -> None:
        self._busy = False
        self.status.setText(message)
        self.output.setPlainText(
            "The dictionary service could not be reached.\n"
            "Check your connection, or open the word on Merriam-Webster instead."
        )

    def _open_web(self) -> None:
        word = self.word_edit.text().strip()
        if not word:
            return
        self.controller.open_url(f"https://www.merriam-webster.com/dictionary/{word}")


__all__ = ["CalculatorTab", "DeveloperTab", "DateTimeTab", "ColorTab", "DictionaryTab", "ToolCard"]
