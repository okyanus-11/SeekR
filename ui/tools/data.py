"""Clipboard, notes, bookmarks, connections and quick actions pages."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QProgressDialog
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QFileDialog,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.logging_setup import get_logger
from core.workers import CancelToken
from features import bookmarks as bookmarks_module
from features import util
from ui import dialogs
from ui.components import (
    Switch,
    danger_button,
    label,
    primary_button,
    secondary_button,
)

log = get_logger(__name__)


class ClipboardTab(QWidget):
    """Clipboard history with search, pin and delete."""

    def __init__(self, controller, window):
        super().__init__()
        self.controller = controller
        self.service = controller.clipboard_service
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        layout.addWidget(label("Clipboard history", "Heading"))
        layout.addWidget(
            label(
                "Clipboard text is stored unencrypted in SeekR’s local SQLite database. "
                "Images are saved as local PNG files only when image capture is separately enabled. "
                "Capture is off until you opt in. Pin entries to keep them when the limit is reached.",
                "Muted", wrap=True,
            )
        )
        controls = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search clipboard history…")
        self.search.textChanged.connect(self.reload)
        controls.addWidget(self.search, 1)
        self.category_filter = QComboBox()
        self.category_filter.addItem("All categories", "")
        self.category_filter.currentIndexChanged.connect(self.reload)
        controls.addWidget(self.category_filter)
        self.monitor_switch = Switch()
        self.monitor_switch.setChecked(controller.clipboard_service.enabled)
        self.monitor_switch.toggled.connect(self._toggle_monitor)
        controls.addWidget(label("Monitor clipboard", "Muted"))
        controls.addWidget(self.monitor_switch)
        controls.addWidget(secondary_button("Refresh", self.reload))
        layout.addLayout(controls)

        self.list = QListWidget()
        self.list.setObjectName("PlainList")
        self.list.setWordWrap(True)
        self.list.setIconSize(QSize(64, 64))
        self.list.itemDoubleClicked.connect(lambda _item: self._copy())
        self.list.currentItemChanged.connect(self._selection_changed)
        layout.addWidget(self.list, 1)

        category_controls = QHBoxLayout()
        self.category_edit = QComboBox()
        self.category_edit.setEditable(True)
        self.category_edit.addItems(["Uncategorized", "Work", "School", "Personal", "Code", "Other"])
        category_controls.addWidget(label("Category", "Muted"))
        category_controls.addWidget(self.category_edit, 1)
        category_controls.addWidget(secondary_button("Set category", self._set_category))
        layout.addLayout(category_controls)

        buttons = QHBoxLayout()
        buttons.addWidget(primary_button("Copy", self._copy))
        buttons.addWidget(secondary_button("Pin / Unpin", self._toggle_pin))
        buttons.addWidget(danger_button("Delete entry", self._delete))
        buttons.addWidget(danger_button("Clear unpinned", self._clear))
        buttons.addStretch(1)
        self.status = label("", "Muted")
        buttons.addWidget(self.status)
        layout.addLayout(buttons)
        self.reload()

    def _toggle_monitor(self, checked: bool) -> None:
        self.controller.config.set("clipboard.enabled", checked)
        self.status.setText("Clipboard monitoring enabled" if checked else "Clipboard monitoring disabled")

    def reload(self) -> None:
        items = self.service.items(self.search.text().strip(), 300)
        selected_category = self.category_filter.currentData()
        categories = sorted({str(entry.get("category", "")).strip()
                             for entry in items if str(entry.get("category", "")).strip()})
        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItem("All categories", "")
        self.category_filter.addItem("Uncategorized", "__uncategorized__")
        for category in categories:
            self.category_filter.addItem(category, category)
        index = self.category_filter.findData(selected_category)
        self.category_filter.setCurrentIndex(max(0, index))
        self.category_filter.blockSignals(False)
        if selected_category == "__uncategorized__":
            items = [entry for entry in items if not entry.get("category")]
        elif selected_category:
            items = [entry for entry in items if entry.get("category") == selected_category]
        self.list.clear()
        for entry in items:
            text = entry.get("text", "")
            is_image = entry.get("kind") == "image"
            preview = " ".join(text.split())
            title = (f"Image · {int(entry.get('width') or 0)}×{int(entry.get('height') or 0)}"
                     if is_image else preview[:140] + ("…" if len(preview) > 140 else ""))
            stamp = dt.datetime.fromtimestamp(entry.get("created", 0)).strftime("%Y-%m-%d %H:%M")
            prefix = "📌 " if entry.get("pinned") else ""
            item = QListWidgetItem(f"{prefix}{title}\n{stamp}")
            if is_image:
                pixmap = QPixmap(str(entry.get("image_path") or ""))
                if not pixmap.isNull():
                    item.setIcon(QIcon(pixmap.scaled(
                        64, 64, Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )))
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self.list.addItem(item)
        self.status.setText(f"{len(items)} entries")
        self.monitor_switch.blockSignals(True)
        self.monitor_switch.setChecked(self.service.enabled)
        self.monitor_switch.blockSignals(False)

    def _selection_changed(self, current, _previous) -> None:
        entry = current.data(Qt.ItemDataRole.UserRole) if current is not None else None
        category = (entry or {}).get("category", "") or "Uncategorized"
        self.category_edit.setCurrentText(category)

    def _set_category(self) -> None:
        entry = self._selected()
        if entry is None:
            self.status.setText("Select an entry first")
            return
        category = self.category_edit.currentText().strip()
        if category.lower() == "uncategorized":
            category = ""
        self.service.set_category(entry["id"], category)
        self.reload()

    def _selected(self) -> Optional[dict]:
        item = self.list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def _copy(self) -> None:
        entry = self._selected()
        if entry is None:
            self.status.setText("Select an entry first")
            return
        if self.service.copy(entry):
            self.status.setText("Copied image to clipboard" if entry.get("kind") == "image" else "Copied to clipboard")
        else:
            self.status.setText("Could not copy this entry")

    def _toggle_pin(self) -> None:
        entry = self._selected()
        if entry is None:
            return
        self.service.pin(entry["id"], not bool(entry.get("pinned")))
        self.reload()

    def _delete(self) -> None:
        entry = self._selected()
        if entry is None:
            return
        self.service.delete(entry["id"])
        self.reload()

    def _clear(self) -> None:
        if not dialogs.ask_confirm(self, "Clear clipboard history", "Delete all unpinned clipboard entries?"):
            return
        self.service.clear(keep_pinned=True)
        self.reload()

    def on_show(self) -> None:
        self.reload()

    def showEvent(self, event) -> None:  # noqa: N802
        self.reload()
        super().showEvent(event)


class NotesTab(QWidget):
    """Quick notes with autosave."""

    def __init__(self, controller, window):
        super().__init__()
        self.controller = controller
        self.service = controller.notes_service
        self.config = controller.config
        self._current_id: Optional[int] = None
        self._loading = False
        self._dirty = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        header = QHBoxLayout()
        header.addWidget(label("Quick notes", "Heading"))
        header.addStretch(1)
        header.addWidget(primary_button("New note", self._new_note))
        layout.addLayout(header)
        layout.addWidget(label("Notes save automatically on this computer.", "Muted"))

        splitter = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search notes…")
        self.search.textChanged.connect(lambda _text: self._refresh_list())
        left_layout.addWidget(self.search)
        self.note_list = QListWidget()
        self.note_list.setObjectName("PlainList")
        self.note_list.currentRowChanged.connect(self._on_note_selected)
        left_layout.addWidget(self.note_list, 1)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Note title")
        self.title_edit.textChanged.connect(self._schedule_save)
        right_layout.addWidget(self.title_edit)
        self.body_edit = QPlainTextEdit()
        self.body_edit.setPlaceholderText("Write something…")
        self.body_edit.textChanged.connect(self._schedule_save)
        right_layout.addWidget(self.body_edit, 1)
        footer = QHBoxLayout()
        self.meta_label = label("", "Muted")
        footer.addWidget(self.meta_label, 1)
        footer.addWidget(secondary_button("Pin", self._toggle_pin))
        footer.addWidget(danger_button("Delete", self._delete))
        right_layout.addLayout(footer)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(int(self.config.get("notes.auto_save_ms", 700) or 700))
        self.save_timer.timeout.connect(self._save_now)
        self._refresh_list()

    # -------------------------------------------------------------- list model
    def _refresh_list(self, select_id: Optional[int] = None) -> None:
        target = select_id if select_id is not None else self._current_id
        self._loading = True
        self.note_list.clear()
        notes = self.service.list(self.search.text().strip(), 300)
        selected_row = -1
        for index, note in enumerate(notes):
            prefix = "📌 " if note.get("pinned") else ""
            title = note.get("title") or "Untitled note"
            item = QListWidgetItem(f"{prefix}{title}")
            item.setData(Qt.ItemDataRole.UserRole, note["id"])
            self.note_list.addItem(item)
            if note["id"] == target:
                selected_row = index
        self._loading = False
        if selected_row >= 0:
            self.note_list.setCurrentRow(selected_row)
        elif notes:
            self.note_list.setCurrentRow(0)
        else:
            self._current_id = None
            self._loading = True
            self.title_edit.clear()
            self.body_edit.clear()
            self._loading = False
            self.meta_label.setText("No notes yet")

    def _on_note_selected(self, row: int) -> None:
        if self._loading:
            return
        item = self.note_list.item(row)
        if item is None:
            return
        self._save_now()
        note_id = item.data(Qt.ItemDataRole.UserRole)
        note = self.service.get(int(note_id))
        if note is None:
            return
        self._current_id = note["id"]
        self._loading = True
        self.title_edit.setText(note.get("title", ""))
        self.body_edit.setPlainText(note.get("body", ""))
        self._loading = False
        updated = dt.datetime.fromtimestamp(note.get("updated", 0)).strftime("%Y-%m-%d %H:%M")
        self.meta_label.setText(f"Last saved {updated}" + ("  ·  pinned" if note.get("pinned") else ""))

    # ----------------------------------------------------------------- actions
    def _schedule_save(self) -> None:
        if self._loading or self._current_id is None:
            return
        self._dirty = True
        self.meta_label.setText("Saving…")
        self.save_timer.start()

    def _save_now(self) -> None:
        self.save_timer.stop()
        if self._current_id is None or self._loading or not self._dirty:
            return
        title = self.title_edit.text().strip() or "Untitled note"
        self.service.update(self._current_id, title=title, body=self.body_edit.toPlainText())
        self._dirty = False
        self.meta_label.setText(f"Saved at {dt.datetime.now():%H:%M:%S}")
        current = self._current_id
        self._refresh_list(select_id=current)

    def _new_note(self) -> None:
        self._save_now()
        note_id = self.service.create("New note", "")
        self._current_id = note_id
        self._refresh_list(select_id=note_id)
        self.title_edit.setFocus(Qt.FocusReason.OtherFocusReason)
        self.title_edit.selectAll()

    def _toggle_pin(self) -> None:
        if self._current_id is None:
            return
        self._save_now()
        self.service.toggle_pin(self._current_id)
        self._refresh_list(select_id=self._current_id)
        note = self.service.get(self._current_id)
        if note:
            self.meta_label.setText(
                "Pinned" if note.get("pinned") else "Unpinned"
            )

    def _delete(self) -> None:
        if self._current_id is None:
            return
        if not dialogs.ask_confirm(self, "Delete note", "Delete this note permanently?"):
            return
        self.service.delete(self._current_id)
        self._current_id = None
        self._dirty = False
        self._refresh_list(select_id=None)

    def select_note(self, note_id: int) -> None:
        self._save_now()
        self._refresh_list(select_id=note_id)

    def on_show(self) -> None:
        self._refresh_list()

    def hideEvent(self, event) -> None:  # noqa: N802
        self._save_now()
        super().hideEvent(event)


class BookmarksTab(QWidget):
    """Bookmarks discovered from installed browsers."""

    def __init__(self, controller, window):
        super().__init__()
        self.controller = controller
        self._bookmarks: list[dict] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        layout.addWidget(label("Bookmarks", "Heading"))
        layout.addWidget(
            label(
                "SeekR reads bookmark files from Chrome, Edge, Brave, Vivaldi and Firefox. "
                "No browser data is uploaded anywhere.",
                "Muted",
                wrap=True,
            )
        )
        controls = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search bookmarks…")
        self.search.textChanged.connect(self._filter)
        controls.addWidget(self.search, 1)
        controls.addWidget(primary_button("Open", self._open))
        controls.addWidget(secondary_button("Reload", self.reload))
        layout.addLayout(controls)
        self.list = QListWidget()
        self.list.setObjectName("PlainList")
        self.list.itemDoubleClicked.connect(lambda _item: self._open())
        layout.addWidget(self.list, 1)
        self.status = label("", "Muted", wrap=True)
        layout.addWidget(self.status)
        self.reload()

    def reload(self) -> None:
        try:
            self._bookmarks = bookmarks_module.load_bookmarks(refresh=True)
        except Exception as exc:  # pragma: no cover - defensive
            log.exception("Bookmark loading failed")
            self.status.setText(f"Could not read bookmarks: {exc}")
            self._bookmarks = []
        self._filter()

    def _filter(self) -> None:
        query = self.search.text().strip().lower()
        self.list.clear()
        matches = [
            bookmark
            for bookmark in self._bookmarks
            if not query or query in bookmark["title"].lower() or query in bookmark["url"].lower()
        ]
        for bookmark in matches[:500]:
            item = QListWidgetItem(f"{bookmark['title']}\n{bookmark['browser']}  ·  {bookmark['url']}")
            item.setData(Qt.ItemDataRole.UserRole, bookmark)
            self.list.addItem(item)
        if not self._bookmarks:
            self.status.setText("No bookmarks found. Open your browser once so its bookmark file exists.")
        else:
            self.status.setText(f"{len(self._bookmarks)} bookmarks  ·  showing {len(matches)}")

    def _open(self) -> None:
        item = self.list.currentItem()
        if item is None:
            return
        bookmark = item.data(Qt.ItemDataRole.UserRole)
        if not self.controller.open_url(bookmark.get("url", "")):
            self.status.setText("Could not open the bookmark")

    def on_show(self) -> None:
        if not self._bookmarks:
            self.reload()


class ConnectionsTab(QWidget):
    """SSH profiles management."""

    def __init__(self, controller, window):
        super().__init__()
        self.controller = controller
        self.service = controller.quick_connect_service
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        layout.addWidget(label("Quick Connect", "Heading"))
        layout.addWidget(
            label(
                "Launch SSH sessions from the launcher. Profiles use key-based authentication; "
                "SeekR never stores passwords.",
                "Muted",
                wrap=True,
            )
        )
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Name", "Host", "User", "Port"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(lambda _index: self._connect())
        layout.addWidget(self.table, 1)
        buttons = QHBoxLayout()
        buttons.addWidget(primary_button("Connect", self._connect))
        buttons.addWidget(secondary_button("New profile…", self._new))
        buttons.addWidget(secondary_button("Edit…", self._edit))
        buttons.addWidget(danger_button("Delete", self._delete))
        buttons.addStretch(1)
        self.status = label("", "Muted")
        buttons.addWidget(self.status)
        layout.addLayout(buttons)
        self.reload()

    def reload(self) -> None:
        profiles = self.service.profiles()
        self.table.setRowCount(0)
        for profile in profiles:
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = [
                profile.get("name", ""),
                profile.get("host", ""),
                profile.get("user", "") or "—",
                str(profile.get("port", 22)),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, profile)
                self.table.setItem(row, column, item)
        self.status.setText(f"{len(profiles)} profiles")

    def _selected(self) -> Optional[dict]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _connect(self) -> None:
        profile = self._selected()
        if profile is None:
            self.status.setText("Select a profile first")
            return
        ok, message = self.service.connect(profile)
        self.status.setText(message)
        if not ok:
            self.controller.show_error("SSH", message)

    def _new(self) -> None:
        dialog = dialogs.SSHProfileDialog(self.service, parent=self)
        if dialog.exec():
            self.reload()

    def _edit(self) -> None:
        profile = self._selected()
        if profile is None:
            return
        dialog = dialogs.SSHProfileDialog(self.service, profile, parent=self)
        if dialog.exec():
            self.reload()

    def _delete(self) -> None:
        profile = self._selected()
        if profile is None:
            return
        if not dialogs.ask_confirm(self, "Delete profile", f"Delete “{profile['name']}”?"):
            return
        self.service.delete(profile["id"])
        self.reload()

    def on_show(self) -> None:
        self.reload()


class ActionsTab(QWidget):
    """Manage quick actions."""

    def __init__(self, controller, window):
        super().__init__()
        self.controller = controller
        self.service = controller.quick_action_service
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        layout.addWidget(label("Quick actions", "Heading"))
        layout.addWidget(
            label(
                "Folders, websites, applications and text snippets that appear in the launcher.",
                "Muted",
                wrap=True,
            )
        )
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Title", "Type", "Target", "Description"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(lambda _index: self._run())
        layout.addWidget(self.table, 1)
        buttons = QHBoxLayout()
        buttons.addWidget(primary_button("Run", self._run))
        buttons.addWidget(secondary_button("New…", self._new))
        buttons.addWidget(secondary_button("Edit…", self._edit))
        buttons.addWidget(danger_button("Delete", self._delete))
        buttons.addStretch(1)
        self.status = label("", "Muted")
        buttons.addWidget(self.status)
        layout.addLayout(buttons)
        self.reload()

    def reload(self) -> None:
        from features.quick_actions import KINDS

        actions = self.service.actions()
        self.table.setRowCount(0)
        for action in actions:
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = [
                action.get("title", ""),
                KINDS.get(action.get("kind", ""), action.get("kind", "")),
                action.get("target", ""),
                action.get("description", ""),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, action)
                self.table.setItem(row, column, item)
        self.status.setText(f"{len(actions)} actions")

    def _selected(self) -> Optional[dict]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _run(self) -> None:
        action = self._selected()
        if action is None:
            self.status.setText("Select an action first")
            return
        ok, message = self.service.execute(action)
        self.status.setText(message)
        if not ok:
            self.controller.show_error("Quick action", message)

    def _new(self) -> None:
        dialog = dialogs.QuickActionDialog(self.service, parent=self)
        if dialog.exec():
            self.reload()

    def _edit(self) -> None:
        action = self._selected()
        if action is None:
            return
        dialog = dialogs.QuickActionDialog(self.service, action, parent=self)
        if dialog.exec():
            self.reload()

    def _delete(self) -> None:
        action = self._selected()
        if action is None:
            return
        if not dialogs.ask_confirm(self, "Delete action", f"Delete “{action['title']}”?"):
            return
        self.service.delete(action["id"])
        self.reload()

    def on_show(self) -> None:
        self.reload()



class WorkflowsTab(QWidget):
    """Create, edit, import, export and run local structured workflows."""

    def __init__(self, controller, window):
        super().__init__()
        self.controller = controller
        self.service = controller.workflow_service
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        layout.addWidget(label("Workflows", "Heading"))
        layout.addWidget(label(
            "Chain safe built-in actions into repeatable routines. Workflows are stored locally; "
            "they cannot run shell scripts or load third-party code.",
            "Muted", wrap=True,
        ))
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Title", "Steps", "Description"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(lambda _index: self._run())
        layout.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        buttons.addWidget(primary_button("Run", self._run))
        buttons.addWidget(secondary_button("New…", self._new))
        buttons.addWidget(secondary_button("Edit…", self._edit))
        buttons.addWidget(danger_button("Delete", self._delete))
        buttons.addWidget(secondary_button("Import…", self._import))
        buttons.addWidget(secondary_button("Export…", self._export))
        buttons.addStretch(1)
        self.status = label("", "Muted")
        buttons.addWidget(self.status)
        layout.addLayout(buttons)
        self.reload()

    def reload(self) -> None:
        rows = self.service.workflows()
        self.table.setRowCount(0)
        for workflow in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = [workflow["title"], str(len(workflow["steps"])), workflow.get("description", "")]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, workflow)
                self.table.setItem(row, column, item)
        self.status.setText(f"{len(rows)} workflows")

    def _selected(self) -> Optional[dict]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _run(self) -> None:
        workflow = self._selected()
        if workflow is None:
            self.status.setText("Select a workflow first")
            return
        valid, message, lines = self.service.preview(workflow)
        if not valid:
            dialogs.show_error(self, "Workflow preview failed", message)
            return
        if not dialogs.ask_confirm(
            self,
            f"Run workflow: {workflow['title']}?",
            "The following actions will run in order:\n\n" + "\n".join(lines),
        ):
            return
        token = CancelToken()
        progress = QProgressDialog("Preparing workflow…", "Cancel", 0, len(workflow["steps"]), self)
        progress.setWindowTitle("Running workflow")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)

        def update_progress(index: int, total: int, detail: str) -> None:
            progress.setMaximum(total)
            progress.setValue(index)
            progress.setLabelText(f"Step {index}/{total}: {detail}")
            QApplication.processEvents()
            if progress.wasCanceled():
                token.cancel()

        try:
            ok, message, completed = self.service.run(
                workflow, token=token, on_progress=update_progress
            )
        finally:
            progress.close()
        self.status.setText(f"{message} ({completed}/{len(workflow['steps'])})")
        if not ok:
            self.controller.show_error("Workflow", message)

    def _new(self) -> None:
        if dialogs.WorkflowDialog(self.service, parent=self).exec():
            self.reload()

    def _edit(self) -> None:
        workflow = self._selected()
        if workflow and dialogs.WorkflowDialog(self.service, workflow, parent=self).exec():
            self.reload()

    def _delete(self) -> None:
        workflow = self._selected()
        if workflow is None:
            return
        if not dialogs.ask_confirm(self, "Delete workflow", f"Delete “{workflow['title']}”?"):
            return
        self.service.delete(workflow["id"])
        self.reload()

    def _import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import workflows", "", "SeekR workflows (*.json)")
        if not path:
            return
        try:
            from features.workflows import MAX_IMPORT_BYTES
            if Path(path).stat().st_size > MAX_IMPORT_BYTES:
                dialogs.show_error(self, "Workflow import failed", "Workflow export is too large")
                return
            content = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            dialogs.show_error(self, "Could not read workflow file", str(exc))
            return
        ok, message, count = self.service.import_json(content)
        if not ok:
            dialogs.show_error(self, "Workflow import failed", message)
            return
        self.reload()
        self.status.setText(f"Imported {count} workflows")

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export workflows", "SeekR-workflows.json", "SeekR workflows (*.json)")
        if not path:
            return
        try:
            Path(path).write_text(self.service.export_json(), encoding="utf-8")
        except OSError as exc:
            dialogs.show_error(self, "Could not export workflows", str(exc))
            return
        self.status.setText("Workflows exported")



class SnippetsTab(QWidget):
    """Manage reusable text; content is copied only on explicit action."""

    def __init__(self, controller, window):
        super().__init__()
        self.controller = controller
        self.service = controller.snippet_service
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        layout.addWidget(label("Text snippets", "Heading"))
        layout.addWidget(label(
            "Store reusable text locally. Search with snip: and copy it only when you choose to.",
            "Muted", wrap=True,
        ))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter snippets…")
        self.search.textChanged.connect(self.reload)
        layout.addWidget(self.search)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Title", "Category", "Shortcut / alias"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(lambda _index: self._copy())
        layout.addWidget(self.table, 1)
        buttons = QHBoxLayout()
        buttons.addWidget(primary_button("Copy snippet", self._copy))
        buttons.addWidget(secondary_button("New…", self._new))
        buttons.addWidget(secondary_button("Edit…", self._edit))
        buttons.addWidget(danger_button("Delete", self._delete))
        buttons.addWidget(secondary_button("Import…", self._import))
        buttons.addWidget(secondary_button("Export…", self._export))
        buttons.addStretch(1)
        self.status = label("", "Muted")
        buttons.addWidget(self.status)
        layout.addLayout(buttons)
        self.reload()

    def reload(self) -> None:
        query = self.search.text().strip().casefold()
        rows = [row for row in self.service.snippets()
                if not query or query in " ".join((row["title"], row.get("category", ""),
                                                    row.get("shortcut", ""))).casefold()]
        self.table.setRowCount(0)
        for snippet in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            for column, value in enumerate((snippet["title"], snippet.get("category", ""),
                                            snippet.get("shortcut", ""))):
                item = QTableWidgetItem(str(value))
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, snippet)
                self.table.setItem(row, column, item)
        self.status.setText(f"{len(rows)} snippets")

    def _selected(self) -> Optional[dict]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _copy(self) -> None:
        snippet = self._selected()
        if snippet is None:
            self.status.setText("Select a snippet first")
            return
        if self.service.copy(snippet):
            self.status.setText(f"Copied {snippet['title']}")
        else:
            self.status.setText("Could not copy snippet")

    def _new(self) -> None:
        if dialogs.SnippetDialog(self.service, parent=self).exec():
            self.reload()

    def _edit(self) -> None:
        snippet = self._selected()
        if snippet and dialogs.SnippetDialog(self.service, snippet, parent=self).exec():
            self.reload()

    def _delete(self) -> None:
        snippet = self._selected()
        if snippet is None:
            return
        if not dialogs.ask_confirm(self, "Delete snippet", f"Delete “{snippet['title']}”?"):
            return
        self.service.delete(snippet["id"])
        self.reload()

    def _import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import snippets", "", "SeekR snippet backup (*.json);;JSON files (*.json)"
        )
        if not path:
            return
        try:
            from features.snippets import MAX_SNIPPET_IMPORT_BYTES
            if Path(path).stat().st_size > MAX_SNIPPET_IMPORT_BYTES:
                dialogs.show_error(self, "Snippet import failed", "Snippet export is too large")
                return
            content = Path(path).read_text(encoding="utf-8")
            ok, message, count = self.service.import_json(content)
        except (OSError, UnicodeError, ValueError) as exc:
            dialogs.show_error(self, "Snippet import failed", str(exc))
            return
        if not ok:
            dialogs.show_error(self, "Snippet import failed", message)
            return
        self.reload()
        self.status.setText(f"Imported {count} snippets")

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export snippets", "SeekR-snippets.json", "JSON files (*.json)"
        )
        if not path:
            return
        try:
            Path(path).write_text(self.service.export_json(), encoding="utf-8")
        except OSError as exc:
            dialogs.show_error(self, "Snippet export failed", str(exc))
            return
        self.status.setText("Snippet backup exported")

    def on_show(self) -> None:
        self.reload()



class TasksTab(QWidget):
    """Local task list with optional ISO due dates and completion tracking."""

    def __init__(self, controller, window):
        super().__init__()
        self.controller = controller
        self.service = controller.task_service
        self._editing_id = None
        self._editing_completed = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        layout.addWidget(label("Tasks", "Heading"))
        layout.addWidget(label(
            "A local task list with optional due dates. Search tasks from the launcher with task:.",
            "Muted", wrap=True,
        ))
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Task title")
        self.notes_edit = QLineEdit()
        self.notes_edit.setPlaceholderText("Notes (optional)")
        self.due_edit = QLineEdit()
        self.due_edit.setPlaceholderText("Due date YYYY-MM-DD (optional)")
        fields = QHBoxLayout()
        fields.addWidget(self.title_edit, 2)
        fields.addWidget(self.due_edit, 1)
        fields.addWidget(self.notes_edit, 2)
        layout.addLayout(fields)
        self.save_button = primary_button("Add task", self._save)
        layout.addWidget(self.save_button, 0, Qt.AlignmentFlag.AlignLeft)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter tasks…")
        self.search.textChanged.connect(self.reload)
        layout.addWidget(self.search)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Task", "Due date", "Status", "Notes"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(lambda _index: self._edit())
        layout.addWidget(self.table, 1)
        buttons = QHBoxLayout()
        buttons.addWidget(secondary_button("Edit…", self._edit))
        buttons.addWidget(secondary_button("Complete / reopen", self._toggle))
        buttons.addWidget(danger_button("Delete", self._delete))
        buttons.addStretch(1)
        self.status = label("", "Muted")
        buttons.addWidget(self.status)
        layout.addLayout(buttons)
        self.reload()

    def reload(self) -> None:
        query = self.search.text().strip().casefold()
        rows = [task for task in self.service.tasks()
                if not query or query in " ".join((task["title"], task.get("notes", ""),
                                                    task.get("due_date", ""))).casefold()]
        self.table.setRowCount(0)
        for task in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = [
                task["title"],
                task.get("due_date") or "—",
                "Completed" if task.get("completed") else "Open",
                task.get("notes", ""),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, task)
                self.table.setItem(row, column, item)
        self.status.setText(f"{len(rows)} tasks")

    def _selected(self) -> Optional[dict]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _save(self) -> None:
        data = {
            "id": self._editing_id,
            "title": self.title_edit.text(),
            "notes": self.notes_edit.text(),
            "due_date": self.due_edit.text().strip(),
            "completed": self._editing_completed,
        }
        ok, message = self.service.save(data)
        if not ok:
            dialogs.show_error(self, "Could not save task", message)
            return
        self._editing_id = None
        self._editing_completed = False
        self.title_edit.clear()
        self.notes_edit.clear()
        self.due_edit.clear()
        self.save_button.setText("Add task")
        self.reload()

    def _edit(self) -> None:
        task = self._selected()
        if task is None:
            return
        self._editing_id = task["id"]
        self._editing_completed = bool(task.get("completed"))
        self.title_edit.setText(task["title"])
        self.notes_edit.setText(task.get("notes", ""))
        self.due_edit.setText(task.get("due_date", ""))
        self.save_button.setText("Save changes")

    def _toggle(self) -> None:
        task = self._selected()
        if task is None:
            return
        self.service.complete(task["id"], not bool(task.get("completed")))
        self.reload()

    def _delete(self) -> None:
        task = self._selected()
        if task is None:
            return
        if not dialogs.ask_confirm(self, "Delete task", f"Delete “{task['title']}”?"):
            return
        self.service.delete(task["id"])
        self._editing_id = None
        self._editing_completed = False
        self.save_button.setText("Add task")
        self.reload()

    def on_show(self) -> None:
        self.reload()


__all__ = ["ClipboardTab", "NotesTab", "BookmarksTab", "ConnectionsTab", "ActionsTab", "WorkflowsTab", "SnippetsTab", "TasksTab"]
