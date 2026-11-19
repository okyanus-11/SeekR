"""SeekR tools window."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from core.version import APP_NAME
from ui import i18n
from ui.components import refresh_localized_widgets
from ui.tools.basic import CalculatorTab, ColorTab, DateTimeTab, DeveloperTab, DictionaryTab
from ui.tools.data import ActionsTab, BookmarksTab, ClipboardTab, ConnectionsTab, NotesTab, WorkflowsTab, SnippetsTab
from ui.tools.system import PowerTab, ProcessesTab, ScreenshotsTab, SystemTab


class ToolsWindow(QMainWindow):
    """A single window hosting every SeekR utility."""

    PAGES: list[tuple[str, str, type]] = [
        ("calculator", "Calculator", CalculatorTab),
        ("developer", "Developer tools", DeveloperTab),
        ("datetime", "Date & time", DateTimeTab),
        ("color", "Color", ColorTab),
        ("dictionary", "Dictionary", DictionaryTab),
        ("screenshots", "Screenshots", ScreenshotsTab),
        ("system", "System", SystemTab),
        ("processes", "Processes", ProcessesTab),
        ("power", "Power", PowerTab),
        ("clipboard", "Clipboard", ClipboardTab),
        ("notes", "Quick notes", NotesTab),
        ("bookmarks", "Bookmarks", BookmarksTab),
        ("connections", "Quick Connect", ConnectionsTab),
        ("actions", "Quick actions", ActionsTab),
        ("workflows", "Workflows", WorkflowsTab),
        ("snippets", "Text snippets", SnippetsTab),
    ]

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.setWindowTitle(f"{APP_NAME} — Tools")
        self.setMinimumSize(940, 620)
        self.resize(1120, 760)

        central = QWidget()
        central.setObjectName("WindowRoot")
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = QListWidget()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(200)
        layout.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)
        self.statusBar().showMessage("")

        self.pages: dict[str, QWidget] = {}
        self.page_keys: list[str] = []
        for key, title, page_class in self.PAGES:
            page = page_class(controller, self)
            self.pages[key] = page
            self.page_keys.append(key)
            item = QListWidgetItem(i18n.tr(self.controller.config, f"tools.page.{key}"))
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.sidebar.addItem(item)
            self.stack.addWidget(page)

        self.sidebar.currentRowChanged.connect(self._on_sidebar_changed)
        self.sidebar.setCurrentRow(0)

    def refresh_texts(self) -> None:
        """Refresh localized sidebar labels after a language change."""
        refresh_localized_widgets(self)
        for row, key in enumerate(self.page_keys):
            item = self.sidebar.item(row)
            if item is not None:
                item.setText(i18n.tr(self.controller.config, f"tools.page.{key}"))

    def _on_sidebar_changed(self, row: int) -> None:
        if 0 <= row < len(self.page_keys):
            self.stack.setCurrentIndex(row)
            page = self.pages[self.page_keys[row]]
            on_show = getattr(page, "on_show", None)
            if callable(on_show):
                on_show()

    def open_page(self, page: Optional[str] = None) -> None:
        if page is None:
            return
        if page in self.pages:
            self.sidebar.setCurrentRow(self.page_keys.index(page))

    def select_note(self, note_id: int) -> None:
        self.open_page("notes")
        notes = self.pages.get("notes")
        if notes is not None and hasattr(notes, "select_note"):
            notes.select_note(note_id)

    def lookup_definition(self, word: str) -> None:
        self.open_page("dictionary")
        dictionary_page = self.pages.get("dictionary")
        if dictionary_page is not None and hasattr(dictionary_page, "lookup"):
            dictionary_page.lookup(word)

    def closeEvent(self, event) -> None:  # noqa: N802
        # Keep the instance so reopening is instant; timers stop on hide.
        event.accept()


__all__ = ["ToolsWindow"]
