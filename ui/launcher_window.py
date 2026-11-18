"""The floating SeekR launcher window."""

from __future__ import annotations

import os
import time
from typing import Any, Optional

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QEvent,
    QPoint,
    QPropertyAnimation,
    QSize,
    Qt,
    QTimer,
    QThreadPool,
    QObject,
    QRunnable,
    Signal,
    Slot,
)
from PySide6.QtGui import QColor, QCursor, QFont, QGuiApplication, QKeyEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core.logging_setup import get_logger
from core.models import SearchResult
from core.workers import Debouncer
from ui import i18n
from ui.components import ElidedLabel, label

log = get_logger(__name__)

_MARGIN = 16
_ROW_HEIGHT = 58

#: How long a programmatically shown launcher keeps retrying activation before
#: "hide when focus is lost" is allowed to hide it again. Windows may refuse
#: ``SetForegroundWindow`` when a second instance asks the running process to
#: show its window; without this grace period the deactivation timer hides the
#: window again a moment later, so the request looks ignored.
_ACTIVATION_GRACE = 1.0
_ACTIVATION_RETRY_MS = 120


class _SearchWorkerSignals(QObject):
    finished = Signal(int, str, object, object)
    failed = Signal(int, str, str, object)


class _SearchWorker(QRunnable):
    """Run a launcher query and deliver its result through Qt's queued signals."""

    def __init__(self, engine, query: str, generation: int):
        super().__init__()
        self.engine = engine
        self.query = query
        self.generation = generation
        self.signals = _SearchWorkerSignals()
        self.setAutoDelete(False)

    def run(self) -> None:
        try:
            results = self.engine.search(self.query)
        except Exception as exc:
            log.exception("Background search failed for %r", self.query)
            self.signals.failed.emit(
                self.generation, self.query, str(exc), self
            )
        else:
            self.signals.finished.emit(
                self.generation, self.query, results, self
            )


class LauncherWindow(QWidget):
    """Frameless, keyboard-first search window."""

    closed = Signal()

    def __init__(self, controller: Any):
        super().__init__()
        self.controller = controller
        self.config = controller.config
        self.engine = controller.engine
        self.icons = controller.icons
        self._results: list[SearchResult] = []
        self._displayed_query = ""
        self._action_index: Optional[int] = None
        self._menu_open = False
        self._hiding = False
        self._hide_generation = 0
        self._activation_deadline = 0.0
        self._activation_confirmed = False
        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(lambda: self.status_label.clear())
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._hide_if_inactive)

        self.setWindowTitle("SeekR")
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)

        self._build_ui()
        self._debouncer = Debouncer(int(self.config.get("search.debounce_ms", 120) or 120), self)
        # Search providers may query large SQLite indexes or rank hundreds of
        # candidates. Keep that work off Qt's GUI thread so typing stays fluid.
        self._search_pool = QThreadPool(self)
        self._search_pool.setMaxThreadCount(2)
        self._search_generation = 0
        self._pending_execute_query: str | None = None
        # Keep Python QRunnable wrappers alive until their native pool tasks finish.
        self._search_workers = set()
        self.refresh_texts()

    # ------------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(_MARGIN, _MARGIN, _MARGIN, _MARGIN)
        outer.setSpacing(0)

        self.root = QFrame()
        self.root.setObjectName("LauncherRoot")
        shadow = QGraphicsDropShadowEffect(self.root)
        shadow.setBlurRadius(48)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 160))
        self.root.setGraphicsEffect(shadow)
        outer.addWidget(self.root)

        root_layout = QVBoxLayout(self.root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Header -----------------------------------------------------------
        header = QWidget()
        header.setObjectName("HeaderBar")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 14, 12, 12)
        header_layout.setSpacing(12)

        brand = QLabel("S")
        brand.setObjectName("BrandMark")
        brand.setFixedSize(34, 34)
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(brand)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("SearchInput")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMinimumHeight(38)
        self.search_input.textChanged.connect(self._on_text_changed)
        self.search_input.returnPressed.connect(self._execute_current)
        self.search_input.installEventFilter(self)
        header_layout.addWidget(self.search_input, 1)

        self.settings_button = QToolButton()
        self.settings_button.setText("⚙")
        self.settings_button.setToolTip("Settings (Ctrl+,)")
        self.settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_button.setFixedSize(30, 30)
        self.settings_button.setStyleSheet("font-size: 16px;")
        self.settings_button.clicked.connect(self._open_settings)
        header_layout.addWidget(self.settings_button)
        root_layout.addWidget(header)

        # Results ----------------------------------------------------------
        self.results_list = QListWidget()
        self.results_list.setObjectName("ResultList")
        self.results_list.setFrameShape(QFrame.Shape.NoFrame)
        self.results_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.results_list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.results_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.results_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.results_list.setUniformItemSizes(True)
        self.results_list.setMouseTracking(True)
        self.results_list.setSpacing(0)
        self.results_list.currentRowChanged.connect(self._on_selection_changed)
        self.results_list.itemClicked.connect(self._on_item_clicked)
        self.results_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.results_list.customContextMenuRequested.connect(self._show_context_menu)
        root_layout.addWidget(self.results_list, 1)

        # Footer -----------------------------------------------------------
        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 8, 16, 10)
        footer_layout.setSpacing(8)

        self.hint_labels: list[QLabel] = []
        self.hint_container = QHBoxLayout()
        self.hint_container.setSpacing(6)
        footer_layout.addLayout(self.hint_container)
        footer_layout.addStretch(1)

        self.action_label = label("", "Muted")
        self.action_label.setVisible(False)
        footer_layout.addWidget(self.action_label)

        self.status_label = label("", "Muted")
        footer_layout.addWidget(self.status_label)

        self.count_label = label("", "Muted")
        footer_layout.addWidget(self.count_label)
        root_layout.addWidget(footer)

    def refresh_texts(self) -> None:
        """Apply placeholder and hint strings for the configured language."""
        self.search_input.setPlaceholderText(i18n.tr(self.config, "launcher.placeholder"))
        self.settings_button.setToolTip(f"{i18n.tr(self.config, 'launcher.settings')} (Ctrl+,)")
        while self.hint_container.count():
            item = self.hint_container.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.hint_labels = []
        for key, default_key, default_label in (
            ("launcher.hint.navigate", "↑↓", "Navigate"),
            ("launcher.hint.open", "↵", "Open"),
            ("launcher.hint.actions", "Tab", "Actions"),
            ("launcher.hint.copy", "Ctrl+C", "Copy"),
            ("launcher.hint.close", "Esc", "Close"),
        ):
            text = i18n.tr(self.config, key)
            if text == key:
                text = default_label
            if " " in text:
                keycap, remainder = text.split(" ", 1)
                keycap_label = label(keycap, "Kbd")
                keycap_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.hint_container.addWidget(keycap_label)
                hint = label(remainder, "Muted")
            else:
                hint = label(text, "Muted")
            self.hint_container.addWidget(hint)
            self.hint_labels.append(hint)
            self.hint_container.addSpacing(8)

    # ------------------------------------------------------------- geometry
    def _screen(self):
        screen = QGuiApplication.screenAt(QCursor.pos())
        return screen or QGuiApplication.primaryScreen()

    def _apply_geometry(self) -> None:
        screen = self._screen()
        available = screen.availableGeometry() if screen else None
        width = int(self.config.get("appearance.window_width", 780) or 780) + _MARGIN * 2
        height = int(self.config.get("appearance.window_height", 500) or 500) + _MARGIN * 2
        if available is not None:
            width = min(width, available.width() - 24)
            height = min(height, available.height() - 80)
            x = available.x() + (available.width() - width) // 2
            y = available.y() + int(available.height() * 0.16)
        else:
            x = y = 120
        self.resize(width, height)
        self.move(x, y)
        self._target_position = QPoint(x, y)

    # ---------------------------------------------------------------- show
    def show_launcher(self) -> None:
        self._hiding = False
        # Any fade-out still in flight belongs to an earlier hide; a show that
        # arrives mid-animation must win.
        self._hide_generation += 1
        # A pending focus-loss hide must not undo the request we are serving.
        self._hide_timer.stop()
        self._activation_confirmed = self.isActiveWindow()
        self._activation_deadline = time.monotonic() + _ACTIVATION_GRACE
        self._apply_dimensions()
        self._apply_geometry()
        self._reset_action_selection()
        remember = bool(self.config.get("general.remember_last_query", False))
        if not remember:
            self.search_input.blockSignals(True)
            self.search_input.clear()
            self.search_input.blockSignals(False)
        self.refresh_texts()
        self.show()
        self.raise_()
        self.activateWindow()
        self.search_input.setFocus(Qt.FocusReason.OtherFocusReason)
        # Windows may refuse foreground activation from a background process;
        # retry once the window is mapped so the search box really has focus.
        self._force_windows_foreground()
        QTimer.singleShot(0, self._force_windows_foreground)
        self._run_search()
        self._animate_show()

    def _force_windows_foreground(self) -> None:
        if os.name != "nt" or not self.isVisible():
            return
        try:
            from features import util

            util.force_foreground(int(self.winId()))
        except Exception:  # pragma: no cover - defensive
            log.debug("Could not force the launcher to the foreground", exc_info=True)

    def refresh_appearance(self) -> None:
        """Apply font/size changes without clearing the current query."""
        self._apply_dimensions()
        if self.isVisible():
            self._apply_geometry()
        self.update()

    def _apply_dimensions(self) -> None:
        font_family = str(self.config.get("appearance.font_family", "Segoe UI") or "Segoe UI")
        font_size = int(self.config.get("appearance.font_size", 13) or 13)
        font = QFont(font_family, font_size)
        self.setFont(font)
        self.search_input.setFont(QFont(font_family, font_size + 5))
        spacing = int(self.config.get("appearance.result_spacing", 4) or 0)
        self.results_list.setSpacing(0)
        self._row_height = _ROW_HEIGHT + spacing
        opacity = float(self.config.get("appearance.opacity", 0.98))
        self.setWindowOpacity(max(0.65, min(1.0, opacity)))

    def _animate_show(self) -> None:
        duration = int(self.config.get("appearance.animation_duration", 150) or 0)
        target_opacity = float(self.config.get("appearance.opacity", 0.98))
        target_opacity = max(0.65, min(1.0, target_opacity))
        if not self.config.get("appearance.animations", True) or duration <= 0:
            self.setWindowOpacity(target_opacity)
            return
        self.setWindowOpacity(0.0)
        opacity = QPropertyAnimation(self, b"windowOpacity", self)
        opacity.setDuration(duration)
        opacity.setStartValue(0.0)
        opacity.setEndValue(target_opacity)
        opacity.setEasingCurve(QEasingCurve.Type.OutCubic)
        opacity.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

        target = getattr(self, "_target_position", self.pos())
        slide = QPropertyAnimation(self, b"pos", self)
        slide.setDuration(duration)
        slide.setStartValue(QPoint(target.x(), target.y() - 16))
        slide.setEndValue(target)
        slide.setEasingCurve(QEasingCurve.Type.OutCubic)
        slide.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

    def hide_launcher(self) -> None:
        if not self.isVisible() or self._hiding:
            return
        duration = int(self.config.get("appearance.animation_duration", 150) or 0)
        if not self.config.get("appearance.animations", True) or duration <= 0:
            self._hide_timer.stop()
            self.hide()
            self.setWindowOpacity(float(self.config.get("appearance.opacity", 0.98)))
            return
        self._hiding = True
        self._hide_generation += 1
        generation = self._hide_generation
        animation = QPropertyAnimation(self, b"windowOpacity", self)
        animation.setDuration(max(60, duration // 2))
        animation.setStartValue(self.windowOpacity())
        animation.setEndValue(0.0)
        animation.finished.connect(lambda g=generation: self._finish_hide(g))
        animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

    def _finish_hide(self, generation: Optional[int] = None) -> None:
        if generation is not None and generation != self._hide_generation:
            # A show_launcher() call superseded this fade; keep the window up.
            return
        self.hide()
        self.setWindowOpacity(float(self.config.get("appearance.opacity", 0.98)))
        self._hiding = False
        self.closed.emit()

    def toggle(self) -> None:
        if self.isVisible() and self.isActiveWindow():
            self.hide_launcher()
        else:
            self.show_launcher()

    # -------------------------------------------------------------- searching
    def _on_text_changed(self, text: str) -> None:
        self._reset_action_selection()
        if self._pending_execute_query is not None and text != self._pending_execute_query:
            self._pending_execute_query = None
        self._debouncer.call_later(self._run_search)

    def set_query(self, text: str, focus: bool = True) -> None:
        self.show_launcher()
        self.search_input.setText(text)
        self.search_input.setCursorPosition(len(text))
        self._debouncer.cancel()
        if focus:
            self.search_input.setFocus(Qt.FocusReason.OtherFocusReason)
        self._run_search()

    def _run_search(self) -> None:
        query = self.search_input.text()
        self._search_generation += 1
        generation = self._search_generation

        # Worker callbacks only emit Qt signals. The bound slots below belong
        # to this QWidget, so Qt queues delivery onto the GUI thread before
        # touching widgets. Calling a closure directly from QRunnable can run
        # it on the worker thread and cause undefined Qt GUI behaviour.
        worker = _SearchWorker(self.engine, query, generation)
        worker.signals.finished.connect(self._on_search_finished)
        worker.signals.failed.connect(self._on_search_failed)
        self._search_workers.add(worker)
        self._search_pool.start(worker)

    @Slot(int, str, object, object)
    def _on_search_finished(
        self, generation: int, query: str, results: list[SearchResult], worker
    ) -> None:
        self._search_workers.discard(worker)
        if generation != self._search_generation or query != self.search_input.text():
            return
        elapsed_ms = 0.0
        self._display_results(list(results), query)
        if self._pending_execute_query == query:
            self._pending_execute_query = None
            QTimer.singleShot(0, self._execute_current)
        if self.config.get("advanced.performance_stats", False):
            self.show_status(f"{len(results)} results")

    @Slot(int, str, str, object)
    def _on_search_failed(self, generation: int, query: str, message: str, worker) -> None:
        self._search_workers.discard(worker)
        if generation != self._search_generation or query != self.search_input.text():
            return
        log.error("Background search failed: %s", message)
        if self._pending_execute_query == query:
            self._pending_execute_query = None
        self._display_results(
            [
                SearchResult(
                    title="Search failed",
                    subtitle=message,
                    category="System",
                    score=1.0,
                    icon_glyph="!",
                )
            ],
            query,
        )

    def _display_results(self, results: list[SearchResult], query: str) -> None:
        self._displayed_query = query
        current = self.current_result()
        current_title = current.title if current else None
        self._results = results
        self.results_list.setUpdatesEnabled(False)
        self.results_list.clear()
        show_icons = bool(self.config.get("appearance.show_icons", True))
        show_categories = bool(self.config.get("appearance.show_categories", True))

        if not results:
            self._add_message_row(
                i18n.tr(self.config, "launcher.noresults.title" if query else "launcher.empty.title"),
                i18n.tr(self.config, "launcher.noresults.body" if query else "launcher.empty.body"),
            )
        else:
            for index, result in enumerate(results):
                item = QListWidgetItem()
                item.setSizeHint(QSize(0, self._row_height))
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self.results_list.addItem(item)
                widget = self._build_row(result, show_icons, show_categories)
                self.results_list.setItemWidget(item, widget)

        self.results_list.setUpdatesEnabled(True)
        self._reset_action_selection()

        if results:
            selected = 0
            if current_title:
                for index, result in enumerate(results):
                    if result.title == current_title:
                        selected = index
                        break
            self.results_list.setCurrentRow(selected)
        self._update_count()

    def _add_message_row(self, title: str, body: str) -> None:
        item = QListWidgetItem()
        item.setSizeHint(QSize(0, self._row_height + 18))
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        self.results_list.addItem(item)
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("Title")
        layout.addWidget(title_label)
        body_label = QLabel(body)
        body_label.setObjectName("Muted")
        body_label.setWordWrap(True)
        layout.addWidget(body_label)
        self.results_list.setItemWidget(item, widget)

    def _build_row(self, result: SearchResult, show_icons: bool, show_categories: bool) -> QWidget:
        widget = QWidget()
        widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(10, 6, 12, 6)
        layout.setSpacing(12)

        glyph = QLabel()
        glyph.setObjectName("ResultGlyph")
        glyph.setFixedSize(36, 36)
        glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Resolving a new Windows file icon can synchronously invoke the shell
        # and stall the GUI thread while the user types. Only use icons already
        # cached by background/secondary UI work; otherwise render the glyph.
        icon = self.icons.cached_icon_for(result.icon_path) if show_icons else None
        if icon is not None:
            glyph.setPixmap(icon.pixmap(26, 26))
        else:
            glyph.setText(result.icon_glyph or "•")
        layout.addWidget(glyph)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(1)
        title = ElidedLabel(result.title)
        title.setObjectName("Title")
        title_font = title.font()
        title_font.setWeight(QFont.Weight.DemiBold)
        title.setFont(title_font)
        text_layout.addWidget(title)
        if result.subtitle:
            subtitle = ElidedLabel(result.subtitle)
            subtitle.setObjectName("Muted")
            subtitle_font = subtitle.font()
            subtitle_font.setPointSizeF(max(7.5, subtitle_font.pointSizeF() - 1))
            subtitle.setFont(subtitle_font)
            text_layout.addWidget(subtitle)
        layout.addLayout(text_layout, 1)

        if show_categories and result.category:
            chip = QLabel(result.category)
            chip.setObjectName("CategoryChip")
            layout.addWidget(chip, 0, Qt.AlignmentFlag.AlignVCenter)

        hint = QLabel("↵")
        hint.setObjectName("Kbd")
        layout.addWidget(hint, 0, Qt.AlignmentFlag.AlignVCenter)
        return widget

    def _update_count(self) -> None:
        count = len(self._results)
        text = i18n.tr(self.config, "launcher.single_result") if count == 1 else i18n.tr(
            self.config, "launcher.results", count=count
        )
        self.count_label.setText(text if self._results else "")

    # ------------------------------------------------------------- selection
    def current_result(self) -> Optional[SearchResult]:
        row = self.results_list.currentRow()
        if 0 <= row < len(self._results):
            return self._results[row]
        return None

    def _on_selection_changed(self, _row: int) -> None:
        self._reset_action_selection()

    def _on_item_clicked(self, _item: QListWidgetItem) -> None:
        self._execute_current()

    def _move_selection(self, delta: int) -> None:
        if not self._results:
            return
        row = self.results_list.currentRow()
        if row < 0:
            row = 0
        row = max(0, min(len(self._results) - 1, row + delta))
        self.results_list.setCurrentRow(row)
        self.results_list.scrollToItem(self.results_list.item(row))

    def _reset_action_selection(self) -> None:
        self._action_index = None
        if hasattr(self, "action_label"):
            self.action_label.setVisible(False)

    def _cycle_action(self, delta: int = 1) -> None:
        result = self.current_result()
        if result is None:
            return
        actions = result.all_actions()
        if not actions:
            return
        if self._action_index is None:
            index = 0 if delta > 0 else len(actions) - 1
        else:
            index = (self._action_index + delta) % len(actions)
        self._action_index = index
        action = actions[index]
        self.action_label.setText(
            f"{i18n.tr(self.config, 'launcher.action.selected', name=action.label)}  ·  "
            f"Enter runs it  ·  Esc cancels"
        )
        self.action_label.setVisible(True)

    def _copy_current(self) -> None:
        if self._displayed_query != self.search_input.text():
            self._debouncer.cancel()
            self._run_search()
            self.show_status("Updating results…")
            return
        result = self.current_result()
        if result is None:
            return
        text = result.copy_text
        if not text:
            self.show_status("This result has nothing to copy")
            return
        self.controller.copy_text(text)
        self.show_status("Copied to clipboard")

    def _execute_current(self) -> None:
        query = self.search_input.text()
        if self._displayed_query != query:
            # Enter can arrive before the debounce timer or background search
            # completes. Never execute a result belonging to the previous query.
            self._pending_execute_query = query
            self._debouncer.cancel()
            self._run_search()
            return
        self._pending_execute_query = None
        result = self.current_result()
        if result is None:
            return
        try:
            if self.search_input.text().strip():
                self.engine.record_search(self.search_input.text())
            if self._action_index is None:
                executed = result.execute()
            else:
                executed = result.execute(action_index=self._action_index)
        except Exception as exc:  # pragma: no cover - defensive
            log.exception("Result execution failed")
            self.controller.show_error("Action failed", str(exc))
            return
        if not executed:
            self.show_status("This result has no action")
        self._reset_action_selection()

    # ------------------------------------------------------------- shortcuts
    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if watched is self.search_input and event.type() == QEvent.Type.KeyPress:
            key_event: QKeyEvent = event
            key = key_event.key()
            modifiers = key_event.modifiers()
            control = bool(modifiers & Qt.KeyboardModifier.ControlModifier)

            if key == Qt.Key.Key_Down:
                self._move_selection(1)
                return True
            if key == Qt.Key.Key_Up:
                self._move_selection(-1)
                return True
            if key == Qt.Key.Key_PageDown:
                self._move_selection(6)
                return True
            if key == Qt.Key.Key_PageUp:
                self._move_selection(-6)
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._execute_current()
                return True
            if key == Qt.Key.Key_Escape:
                self._on_escape()
                return True
            if key == Qt.Key.Key_Tab:
                self._cycle_action(1)
                return True
            if key == Qt.Key.Key_Backtab:
                self._cycle_action(-1)
                return True
            if key == Qt.Key.Key_C and control and not self.search_input.selectedText():
                self._copy_current()
                return True
            if key == Qt.Key.Key_Comma and control:
                self._open_settings()
                return True
            if key == Qt.Key.Key_R and control:
                self.controller.refresh_indexes("all")
                return True
            if key == Qt.Key.Key_T and control:
                self.controller.open_tools()
                return True
            if key in (
                Qt.Key.Key_1,
                Qt.Key.Key_2,
                Qt.Key.Key_3,
                Qt.Key.Key_4,
                Qt.Key.Key_5,
                Qt.Key.Key_6,
                Qt.Key.Key_7,
                Qt.Key.Key_8,
                Qt.Key.Key_9,
            ) and control:
                index = key - Qt.Key.Key_1
                result = self.current_result()
                if result is not None and index < len(result.all_actions()):
                    self._action_index = index
                    self._execute_current()
                return True
        return super().eventFilter(watched, event)

    def _on_escape(self) -> None:
        if self._action_index is not None:
            self._reset_action_selection()
            return
        self.hide_launcher()

    def _open_settings(self) -> None:
        self.controller.open_settings("general")

    # --------------------------------------------------------------- context
    def _show_context_menu(self, position) -> None:
        item = self.results_list.itemAt(position)
        if item is None:
            return
        row = self.results_list.row(item)
        if not (0 <= row < len(self._results)):
            return
        result = self._results[row]
        menu = QMenu(self)
        self._menu_open = True
        for index, action in enumerate(result.all_actions()):
            label_text = action.label
            if index == 0:
                label_text = f"{label_text}   (Enter)"
            menu.addAction(label_text, lambda i=index: self._execute_action_from_menu(result, i))
        if result.copy_text:
            menu.addSeparator()
            menu.addAction(
                "Copy",
                lambda: (self.controller.copy_text(result.copy_text), self.show_status("Copied")),
            )
        menu.addSeparator()
        menu.addAction("Copy result path" if result.icon_path else "Copy title", self._copy_current)
        menu.aboutToHide.connect(self._menu_closed)
        menu.exec(self.results_list.mapToGlobal(position))
        self._menu_open = False

    def _execute_action_from_menu(self, result: SearchResult, index: int) -> None:
        self._menu_open = False
        try:
            result.execute(action_index=index)
        except Exception as exc:  # pragma: no cover
            log.exception("Context action failed")
            self.controller.show_error("Action failed", str(exc))

    def _menu_closed(self) -> None:
        self._menu_open = False

    # ----------------------------------------------------------------- status
    def show_status(self, message: str, level: str = "info") -> None:
        self.status_label.setText(message)
        self._status_timer.start(5000)
        if level in {"error", "warning"}:
            log.info("Launcher status: %s", message)

    def show_progress(self, percent: int, message: str) -> None:
        self.show_status(f"{message}  ({percent}%)")

    # ------------------------------------------------------------ window hooks
    def changeEvent(self, event) -> None:  # noqa: N802
        if event.type() == QEvent.Type.WindowDeactivate:
            if self.config.get("general.hide_on_focus_loss", True):
                self._hide_timer.start(140)
        elif event.type() == QEvent.Type.WindowActivate:
            self._activation_confirmed = True
            self._hide_timer.stop()
        super().changeEvent(event)

    def _hide_if_inactive(self) -> None:
        if self._menu_open or QApplication.activePopupWidget() is not None:
            return
        # Never hide out from under a confirmation/dialog owned by the launcher.
        if QApplication.activeModalWidget() is not None:
            return
        if not self.isVisible() or self.isActiveWindow():
            return
        # The window was raised programmatically (hotkey, tray or a second
        # instance) but the desktop has not granted it the foreground yet. Keep
        # asking instead of hiding the launcher the user just requested. The
        # deadline is absolute, so this retry loop always terminates, and it is
        # skipped once activation succeeded, so clicking away still hides it.
        if not self._activation_confirmed and time.monotonic() < self._activation_deadline:
            log.debug("Launcher is visible but not active yet; retrying foreground activation")
            self._force_windows_foreground()
            self.activateWindow()
            self._hide_timer.start(_ACTIVATION_RETRY_MS)
            return
        self.hide_launcher()

    def closeEvent(self, event) -> None:  # noqa: N802
        event.ignore()
        self.hide_launcher()


__all__ = ["LauncherWindow"]
