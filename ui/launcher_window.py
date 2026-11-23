Warning: truncated output (original token count: 9649)
Total output lines: 912

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
    QParallelAnimationGroup,
    QSize,
    Qt,
    QTimer,
    QThreadPool,
    QObject,
    QRunnable,
    Signal,
    Slot,
)
from PySide6.QtGui import QCursor, QFont, QGuiApplication, QKeyEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
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
from ui.launcher_widgets import LauncherWidgets

log = get_logger(__name__)

_MARGIN = 16
_ROW_HEIGHT = 58
_DROPDOWN_TOP_GAP = 8
_DROPDOWN_REVEAL = 18

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
        self._window_animation = None
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
        # Keep the top-level surface opaque. Layered translucent Qt tool windows
        # can stop receiving visible backing-store repaints on Windows while
        # still processing input, which presents as a frozen screenshot.
        self.setObjectName("LauncherWindow")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)

        # Search results can arrive before the first show (for example when a
        # background query finishes during hidden startup). Keep row rendering
        # valid before the first call to _apply_dimensions().
        self._row_height = _ROW_HEIGHT
        self._build_ui()
        self._debouncer = Debouncer(int(self.config.get("search.debounce_ms", 65) or 65), self)
        # Search providers may query large SQLite indexes or rank hundreds of
        # candidates. Keep that work off Qt's GUI thread so typing stays fluid.
        self._search_pool = QThreadPool(self)
        # Search is latency-sensitive and only the newest query matters.
        # A single worker plus one replaceable pending request prevents rapid
        # typing from launching intermediate searches that are already stale.
        # Results are generation-checked before touching the UI, so stale work
        # can never replace the current query.
        self._search_pool.setMaxThreadCount(1)
        self._active_searches = 0
        self._queued_search: tuple[int, str] | None = None
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
        # Avoid graphics effects on the translucent top-level surface. The
        # themed frame border supplies separation without a native layered effect.
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

        # Main content: two compact widget rails frame the search results.
        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(12, 2, 12, 2)
        body_layout.setSpacing(12)

        self.launcher_widgets = LauncherWidgets(self.config, self, self.controller.task_service, self.controller)
        body_layout.addWidget(self.launcher_widgets.left_column, 0)

        results_panel = QWidget()
        results_layout = QVBoxLayout(results_panel)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.setSpacing(0)
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
        results_layout.addWidget(self.results_list, 1)
        body_layout.addWidget(results_panel, 1)
        body_layout.addWidget(self.launcher_widgets.right_column, 0)
        root_layout.addWidget(body, 1)

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
        footer_layout.add…4649 tokens truncated…lta))
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
            # Windows/Qt can deliver a delayed deactivation from the previous
            # hide/show transition after the launcher has already been raised
            # again. Treat every deactivation inside the activation grace
            # period as stale; otherwise its 140 ms timer can hide the freshly
            # reopened launcher and make the second hotkey press appear broken.
            if time.monotonic() < self._activation_deadline:
                self._hide_timer.stop()
            elif self.config.get("general.hide_on_focus_loss", True):
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

