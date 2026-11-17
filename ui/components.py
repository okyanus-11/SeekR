"""Reusable widgets shared by the launcher, settings and tools windows."""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QEasingCurve, QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFontMetrics, QKeySequence, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QColorDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.hotkeys import HotkeyError, normalize_hotkey
from ui import i18n


class Switch(QAbstractButton):
    """An animated on/off switch that follows the active theme."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(46, 26)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._position = 0.0
        self._animation = QVariantAnimation(self)
        self._animation.setDuration(140)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.valueChanged.connect(self._on_animation)
        self.toggled.connect(self._animate)
        self._position = 1.0 if self.isChecked() else 0.0

    def _on_animation(self, value) -> None:
        self._position = float(value)
        self.update()

    def _animate(self, checked: bool) -> None:
        self._animation.stop()
        self._animation.setStartValue(self._position)
        self._animation.setEndValue(1.0 if checked else 0.0)
        self._animation.start()

    def setChecked(self, checked: bool) -> None:  # noqa: N802 (Qt API)
        super().setChecked(checked)
        if not self._animation.state():
            self._position = 1.0 if checked else 0.0
            self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width, height = self.width(), self.height()
        track = QRectF(1.0, 1.0, width - 2.0, height - 2.0)
        radius = track.height() / 2

        palette = self.palette()
        track_color = palette.highlight().color() if self.isChecked() else palette.mid().color()
        if not self.isChecked():
            track_color.setAlpha(90)
        if not self.isEnabled():
            track_color.setAlpha(50)
        painter.setPen(QPen(track_color.darker(115), 1))
        painter.setBrush(track_color)
        painter.drawRoundedRect(track, radius, radius)

        knob_size = height - 8
        left = 4 + (width - knob_size - 8) * self._position
        knob = QRectF(left, 4, knob_size, knob_size)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(knob)
        painter.end()


class SettingRow(QFrame):
    """A labelled setting row with a control on the right."""

    def __init__(self, title: str, description: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Row")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 10, 4, 10)
        layout.setSpacing(14)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        self.title_label = QLabel(i18n.translate_text(title))
        self.title_label.setWordWrap(True)
        text_layout.addWidget(self.title_label)
        if description:
            self.description_label = QLabel(i18n.translate_text(description))
            self.description_label.setObjectName("Muted")
            self.description_label.setWordWrap(True)
            text_layout.addWidget(self.description_label)
        else:
            self.description_label = None
        layout.addLayout(text_layout, 1)

        self.control_container = QWidget()
        self.control_layout = QHBoxLayout(self.control_container)
        self.control_layout.setContentsMargins(0, 0, 0, 0)
        self.control_layout.setSpacing(8)
        layout.addWidget(self.control_container, 0)

    def add_control(self, widget: QWidget) -> QWidget:
        self.control_layout.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
        return widget

    def set_enabled_state(self, enabled: bool) -> None:
        self.setEnabled(enabled)


class SectionCard(QFrame):
    """A card with a title, optional subtitle and stacked content."""

    def __init__(self, title: str = "", subtitle: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(8)
        if title:
            heading = QLabel(i18n.translate_text(title))
            heading.setObjectName("Title")
            outer.addWidget(heading)
        if subtitle:
            description = QLabel(i18n.translate_text(subtitle))
            description.setObjectName("Muted")
            description.setWordWrap(True)
            outer.addWidget(description)
        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(2)
        outer.addLayout(self.body)

    def add_row(self, row: SettingRow) -> SettingRow:
        self.body.addWidget(row)
        return row

    def add_widget(self, widget: QWidget) -> QWidget:
        self.body.addWidget(widget)
        return widget


class ScrollPage(QScrollArea):
    """A scrollable settings page with a vertical content layout."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.container = QWidget()
        self.container.setObjectName("PageRoot")
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(22, 20, 22, 26)
        self.layout.setSpacing(14)
        self.setWidget(self.container)

    def add(self, widget: QWidget) -> QWidget:
        self.layout.addWidget(widget)
        return widget

    def add_stretch(self) -> None:
        self.layout.addStretch(1)


class ColorButton(QPushButton):
    """A button showing a color swatch; opens the color dialog."""

    colorChanged = Signal(str)

    def __init__(self, color: str = "#7c5cff", parent: QWidget | None = None):
        super().__init__(parent)
        self._color = QColor(color)
        if not self._color.isValid():
            self._color = QColor("#7c5cff")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumWidth(120)
        self.clicked.connect(self._choose)
        self._update_label()

    @property
    def color(self) -> str:
        return self._color.name()

    def set_color(self, color: str) -> None:
        candidate = QColor(color)
        if candidate.isValid():
            self._color = candidate
            self._update_label()

    def _update_label(self) -> None:
        self.setText(f"  {self._color.name().upper()}")
        self.setStyleSheet(
            f"QPushButton {{ border-left: 18px solid {self._color.name()}; text-align: left; padding-left: 10px; }}"
        )

    def _choose(self) -> None:
        chosen = QColorDialog.getColor(self._color, self, i18n.translate_text("Choose accent color"))
        if chosen.isValid():
            self._color = chosen
            self._update_label()
            self.colorChanged.emit(chosen.name())


class HotkeyEdit(QLineEdit):
    """Captures a key combination instead of typing text."""

    hotkeyChanged = Signal(str)

    def __init__(self, hotkey: str = "Alt+Space", parent: QWidget | None = None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setPlaceholderText(i18n.translate_text("Press a key combination"))
        self.setToolTip(i18n.translate_text("Click and press a combination such as Ctrl+Shift+Space"))
        self.set_hotkey(hotkey)

    def set_hotkey(self, hotkey: str) -> None:
        text = (hotkey or "").strip()
        self.setText(text)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            return
        if event.key() == Qt.Key.Key_Escape:
            self.clearFocus()
            return
        parts: list[str] = []
        modifiers = event.modifiers()
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            parts.append("Ctrl")
        if modifiers & Qt.KeyboardModifier.AltModifier:
            parts.append("Alt")
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            parts.append("Shift")
        if modifiers & Qt.KeyboardModifier.MetaModifier:
            parts.append("Win")
        key_text = QKeySequence(event.key()).toString()
        if not key_text or key_text in {"Ctrl", "Alt", "Shift", "Meta"}:
            return
        parts.append(key_text)
        candidate = "+".join(parts)
        try:
            normalized = normalize_hotkey(candidate)
        except HotkeyError:
            self.setText(candidate)
            self.setToolTip(i18n.translate_text("Add at least one modifier (Ctrl, Alt, Shift or Win)"))
            return
        self.setText(normalized)
        self.setToolTip(i18n.translate_text("Click and press a combination such as Ctrl+Shift+Space"))
        self.hotkeyChanged.emit(normalized)


class ClickableLabel(QLabel):
    """A label that emits a signal when clicked (used for links)."""

    clicked = Signal()

    def __init__(self, text: str = "", parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class ElidedLabel(QLabel):
    """A single-line label that elides its text when space runs out."""

    def __init__(self, text: str = "", parent: QWidget | None = None):
        super().__init__(text, parent)
        self._full_text = text
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def setText(self, text: str) -> None:  # noqa: N802
        self._full_text = text or ""
        super().setText(self._full_text)

    def paintEvent(self, event) -> None:  # noqa: N802
        metrics = QFontMetrics(self.font())
        elided = metrics.elidedText(self._full_text, Qt.TextElideMode.ElideRight, max(10, self.width()))
        painter = QPainter(self)
        painter.setPen(self.palette().windowText().color())
        painter.drawText(self.rect(), int(self.alignment() | Qt.AlignmentFlag.AlignVCenter), elided)
        painter.end()


def hline() -> QFrame:
    line = QFrame()
    line.setObjectName("Divider")
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFixedHeight(1)
    return line


def label(text: str, object_name: str = "", wrap: bool = False) -> QLabel:
    widget = QLabel(i18n.translate_text(text))
    if object_name:
        widget.setObjectName(object_name)
    widget.setWordWrap(wrap)
    return widget


def badge(text: str) -> QLabel:
    widget = QLabel(i18n.translate_text(text))
    widget.setObjectName("Badge")
    widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return widget


def primary_button(text: str, callback: Optional[Callable[[], None]] = None) -> QPushButton:
    button = QPushButton(i18n.translate_text(text))
    button.setObjectName("Primary")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    if callback is not None:
        button.clicked.connect(callback)
    return button


def secondary_button(text: str, callback: Optional[Callable[[], None]] = None) -> QPushButton:
    button = QPushButton(i18n.translate_text(text))
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    if callback is not None:
        button.clicked.connect(callback)
    return button


def danger_button(text: str, callback: Optional[Callable[[], None]] = None) -> QPushButton:
    button = QPushButton(i18n.translate_text(text))
    button.setObjectName("Danger")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    if callback is not None:
        button.clicked.connect(callback)
    return button


class InfoBanner(QFrame):
    """A highlighted informational block (e.g. the plugin marketplace notice)."""

    def __init__(self, title: str, body: str, badge_text: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 22)
        layout.setSpacing(10)
        header = QHBoxLayout()
        heading = QLabel(i18n.translate_text(title))
        heading.setObjectName("Heading")
        header.addWidget(heading)
        header.addStretch(1)
        if badge_text:
            header.addWidget(badge(badge_text))
        layout.addLayout(header)
        description = QLabel(i18n.translate_text(body))
        description.setWordWrap(True)
        description.setObjectName("Muted")
        layout.addWidget(description)


__all__ = [
    "Switch",
    "SettingRow",
    "SectionCard",
    "ScrollPage",
    "ColorButton",
    "HotkeyEdit",
    "ClickableLabel",
    "ElidedLabel",
    "hline",
    "label",
    "badge",
    "primary_button",
    "secondary_button",
    "danger_button",
    "InfoBanner",
]
