"""Clipboard, notes, bookmarks, connections and quick actions pages."""

from __future__ import annotations

import datetime as dt
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
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
                "Capture is off until you opt in. Pin entries to keep them when the limit is reached.",
                "Muted", wrap=True,
            )
        )
        controls = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search clipboard history…")
        self.search.textChanged.connect(self.reload)
        controls.addWidget(self.search, 1)
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
        self.list.itemDoubleClicked.connect(lambda _item: self._copy())
        layout.addWidget(self.list, 1)

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
        self.list.clear()
        items = self.service.items(self.search.text().strip(), 300)
        for entry in items:
            text = entry.get("text", "")
            preview = " ".join(text.split())
            title = preview[:140] + ("…" if len(preview) > 140 else "")
            stamp = dt.datetime.fromtimestamp(entry.get("created", 0)).strftime("%Y-%m-%d %H:%M")
            prefix = "📌 " if entry.get("pinned") else ""
            item = QListWidgetItem(f"{prefix}{title}\n{stamp}")
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self.list.addItem(item)
        self.status.setText(f"{len(items)} entries")
        self.monitor_switch.blockSignals(True)
        self.monitor_switch.setChecked(self.service.enabled)
        self.monitor_switch.blockSignals(False)

    def _selected(self) -> Optional[dict]:
        item = self.list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def _copy(self) -> None:
        entry = self._selected()
        if entry is None:
            self.status.setText("Select an entry first")
            return
        self.controller.copy_text(entry["text"])
        self.status.setText("Copied to clipboard")

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


__all__ = ["ClipboardTab", "NotesTab", "BookmarksTab", "ConnectionsTab", "ActionsTab"]
