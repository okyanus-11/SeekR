"""Dialogs used across SeekR."""

from __future__ import annotations

from pathlib import Path
import json
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from features import quicklook
from features.quick_actions import KINDS
from ui.components import ScrollPage, SectionCard, primary_button, secondary_button


def show_info(parent: QWidget | None, title: str, text: str) -> None:
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setIcon(QMessageBox.Icon.Information)
    box.setText(text if len(text) < 600 else text[:600] + "…")
    if len(text) >= 600:
        box.setDetailedText(text)
    box.exec()


def show_error(parent: QWidget | None, title: str, text: str) -> None:
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setText(text or "Something went wrong")
    box.exec()


def ask_confirm(parent: QWidget | None, title: str, text: str) -> bool:
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setIcon(QMessageBox.Icon.Question)
    box.setText(text)
    box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    box.setDefaultButton(QMessageBox.StandardButton.No)
    return box.exec() == QMessageBox.StandardButton.Yes


class TextDialog(QDialog):
    """Read-only text output with a copy button."""

    def __init__(self, title: str, text: str, parent: QWidget | None = None, monospace: bool = True):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(760, 520)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        heading = QLabel(title)
        heading.setObjectName("Title")
        layout.addWidget(heading)

        self.editor = QPlainTextEdit()
        self.editor.setPlainText(text)
        self.editor.setReadOnly(True)
        if monospace:
            font = self.editor.font()
            font.setFamily("Consolas")
            font.setStyleHint(font.StyleHint.Monospace)
            self.editor.setFont(font)
        layout.addWidget(self.editor, 1)

        buttons = QHBoxLayout()
        copy_button = secondary_button("Copy", self._copy)
        buttons.addWidget(copy_button)
        buttons.addStretch(1)
        close_button = primary_button("Close", self.accept)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

    def _copy(self) -> None:
        from PySide6.QtGui import QGuiApplication

        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self.editor.toPlainText())


class QuickLookDialog(QDialog):
    """Preview images and text files without executing anything."""

    def __init__(self, path: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.path = path
        self.setWindowTitle(f"Preview — {Path(path).name}")
        self.resize(880, 640)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        try:
            summary = quicklook.file_summary(path)
        except quicklook.QuickLookError as exc:
            heading = QLabel("Preview unavailable")
            heading.setObjectName("Title")
            layout.addWidget(heading)
            layout.addWidget(QLabel(str(exc)))
            close = primary_button("Close", self.accept)
            layout.addWidget(close, 0, Qt.AlignmentFlag.AlignRight)
            return

        header = QHBoxLayout()
        title = QLabel(summary["name"])
        title.setObjectName("Title")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(QLabel(f"{summary['size_text']}  ·  {summary['modified_text']}"))
        layout.addLayout(header)

        path_label = QLabel(summary["path"])
        path_label.setObjectName("Muted")
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(path_label)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        kind = summary["kind"]
        if kind == "image":
            view = QLabel()
            try:
                pixmap: QPixmap = quicklook.load_image_preview(path)
                view.setPixmap(pixmap)
                view.setAlignment(Qt.AlignmentFlag.AlignCenter)
                view.setMinimumSize(320, 240)
            except quicklook.QuickLookError as exc:
                view.setText(str(exc))
        elif kind == "text":
            view = QPlainTextEdit()
            try:
                view.setPlainText(quicklook.load_text_preview(path))
            except quicklook.QuickLookError as exc:
                view.setPlainText(str(exc))
            view.setReadOnly(True)
            font = view.font()
            font.setFamily("Consolas")
            font.setStyleHint(font.StyleHint.Monospace)
            view.setFont(font)
        else:
            view = QLabel(
                "QuickLook supports images and common text files.\n"
                "Open the file with its default application to view it."
            )
            view.setAlignment(Qt.AlignmentFlag.AlignCenter)
            view.setWordWrap(True)
        content_layout.addWidget(view)
        layout.addWidget(content, 1)

        buttons = QHBoxLayout()
        open_button = secondary_button("Open with default app", self._open)
        buttons.addWidget(open_button)
        buttons.addStretch(1)
        buttons.addWidget(primary_button("Close", self.accept))
        layout.addLayout(buttons)

    def _open(self) -> None:
        from features import util

        ok, message = util.open_path_platform(self.path)
        if not ok:
            show_error(self, "Could not open the file", message)


class CommandEditorDialog(QDialog):
    """Create or edit a custom command."""

    def __init__(self, service, command: dict | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.service = service
        self.command = command or {}
        self.setWindowTitle("Edit command" if command else "New command")
        self.resize(560, 460)

        page = ScrollPage()
        card = SectionCard("Command details", "Commands run without a shell; arguments are passed safely.")
        form = QFormLayout()
        form.setSpacing(10)

        self.name_edit = QLineEdit(str(self.command.get("name", "")))
        self.name_edit.setPlaceholderText("My command")
        form.addRow("Name", self.name_edit)

        self.command_edit = QLineEdit(str(self.command.get("command", "")))
        self.command_edit.setPlaceholderText(r"C:\Windows\System32\ipconfig.exe or notepad")
        browse = secondary_button("Browse…", self._browse)
        command_row = QHBoxLayout()
        command_row.addWidget(self.command_edit, 1)
        command_row.addWidget(browse)
        form.addRow("Executable", command_row)

        self.args_edit = QLineEdit(str(self.command.get("args", "")))
        self.args_edit.setPlaceholderText("/all or {args}")
        form.addRow("Arguments", self.args_edit)

        self.description_edit = QLineEdit(str(self.command.get("description", "")))
        self.description_edit.setPlaceholderText("What does this command do?")
        form.addRow("Description", self.description_edit)

        self.aliases_edit = QLineEdit(str(self.command.get("aliases", "")))
        self.aliases_edit.setPlaceholderText("net, network")
        form.addRow("Aliases", self.aliases_edit)

        self.confirm_check = QCheckBox("Ask for confirmation before running")
        self.confirm_check.setChecked(bool(self.command.get("confirm", 1)))
        form.addRow("", self.confirm_check)

        holder = QWidget()
        holder.setLayout(form)
        card.add_widget(holder)
        page.add(card)
        page.add_stretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 12)
        layout.addWidget(page, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons, 0, Qt.AlignmentFlag.AlignRight)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select an executable")
        if path:
            self.command_edit.setText(path)

    def _save(self) -> None:
        data: dict[str, Any] = {
            "name": self.name_edit.text().strip(),
            "command": self.command_edit.text().strip(),
            "args": self.args_edit.text().strip(),
            "description": self.description_edit.text().strip(),
            "aliases": self.aliases_edit.text().strip(),
            "confirm": self.confirm_check.isChecked(),
        }
        if self.command.get("id"):
            data["id"] = self.command["id"]
        ok, message = self.service.save_custom(data)
        if not ok:
            show_error(self, "Could not save the command", message)
            return
        self.accept()


class SSHProfileDialog(QDialog):
    """Create or edit an SSH profile (key-based authentication only)."""

    def __init__(self, service, profile: dict | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.service = service
        self.profile = profile or {}
        self.setWindowTitle("Edit SSH profile" if profile else "New SSH profile")
        self.resize(520, 420)

        page = ScrollPage()
        card = SectionCard(
            "Connection",
            "SeekR launches your system OpenSSH client. Passwords are never stored.",
        )
        form = QFormLayout()
        form.setSpacing(10)

        self.name_edit = QLineEdit(str(self.profile.get("name", "")))
        self.name_edit.setPlaceholderText("Home server")
        form.addRow("Name", self.name_edit)

        self.host_edit = QLineEdit(str(self.profile.get("host", "")))
        self.host_edit.setPlaceholderText("192.168.1.20 or example.com")
        form.addRow("Host", self.host_edit)

        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(int(self.profile.get("port", 22) or 22))
        form.addRow("Port", self.port_spin)

        self.user_edit = QLineEdit(str(self.profile.get("user", "")))
        self.user_edit.setPlaceholderText("root")
        form.addRow("User", self.user_edit)

        key_row = QHBoxLayout()
        self.key_edit = QLineEdit(str(self.profile.get("key_path", "")))
        self.key_edit.setPlaceholderText(r"C:\Users\you\.ssh\id_ed25519")
        key_row.addWidget(self.key_edit, 1)
        key_row.addWidget(secondary_button("Browse…", self._browse))
        form.addRow("Private key", key_row)

        self.extra_edit = QLineEdit(str(self.profile.get("extra_args", "")))
        self.extra_edit.setPlaceholderText("-o ServerAliveInterval=30")
        form.addRow("Extra options", self.extra_edit)

        holder = QWidget()
        holder.setLayout(form)
        card.add_widget(holder)
        page.add(card)
        page.add_stretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 12)
        layout.addWidget(page, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons, 0, Qt.AlignmentFlag.AlignRight)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select private key")
        if path:
            self.key_edit.setText(path)

    def _save(self) -> None:
        data = {
            "name": self.name_edit.text().strip(),
            "host": self.host_edit.text().strip(),
            "port": self.port_spin.value(),
            "user": self.user_edit.text().strip(),
            "key_path": self.key_edit.text().strip(),
            "extra_args": self.extra_edit.text().strip(),
        }
        if self.profile.get("id"):
            data["id"] = self.profile["id"]
        ok, message = self.service.save(data)
        if not ok:
            show_error(self, "Could not save the profile", message)
            return
        self.accept()


class QuickActionDialog(QDialog):
    """Create or edit a quick action."""

    def __init__(self, service, action: dict | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.service = service
        self.action = action or {}
        self.setWindowTitle("Edit quick action" if action else "New quick action")
        self.resize(540, 380)

        page = ScrollPage()
        card = SectionCard("Action", "Quick actions appear in the launcher and in Tools → Quick Actions.")
        form = QFormLayout()
        form.setSpacing(10)

        self.title_edit = QLineEdit(str(self.action.get("title", "")))
        self.title_edit.setPlaceholderText("Open project folder")
        form.addRow("Title", self.title_edit)

        self.kind_combo = QComboBox()
        for key, label in KINDS.items():
            self.kind_combo.addItem(label, key)
        if self.action.get("kind"):
            index = self.kind_combo.findData(self.action["kind"])
            if index >= 0:
                self.kind_combo.setCurrentIndex(index)
        form.addRow("Type", self.kind_combo)

        target_row = QHBoxLayout()
        self.target_edit = QLineEdit(str(self.action.get("target", "")))
        self.target_edit.setPlaceholderText(r"C:\Projects or https://example.com")
        target_row.addWidget(self.target_edit, 1)
        target_row.addWidget(secondary_button("Browse…", self._browse))
        form.addRow("Target", target_row)

        self.description_edit = QLineEdit(str(self.action.get("description", "")))
        self.description_edit.setPlaceholderText("Optional description")
        form.addRow("Description", self.description_edit)

        holder = QWidget()
        holder.setLayout(form)
        card.add_widget(holder)
        page.add(card)
        page.add_stretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 12)
        layout.addWidget(page, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons, 0, Qt.AlignmentFlag.AlignRight)

    def _browse(self) -> None:
        kind = self.kind_combo.currentData()
        if kind == "launch_app":
            path, _ = QFileDialog.getOpenFileName(self, "Select an application")
        else:
            path = QFileDialog.getExistingDirectory(self, "Select a folder")
        if path:
            self.target_edit.setText(path)

    def _save(self) -> None:
        data = {
            "title": self.title_edit.text().strip(),
            "kind": self.kind_combo.currentData(),
            "target": self.target_edit.text().strip(),
            "description": self.description_edit.text().strip(),
        }
        if self.action.get("id"):
            data["id"] = self.action["id"]
        ok, message = self.service.save(data)
        if not ok:
            show_error(self, "Could not save the quick action", message)
            return
        self.accept()



class WorkflowDialog(QDialog):
    """Edit a structured workflow as readable JSON; arbitrary scripts are not accepted."""

    def __init__(self, service, workflow: dict | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.service = service
        self.workflow = workflow or {}
        self.setWindowTitle("Edit workflow" if workflow else "New workflow")
        self.resize(680, 620)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 12)
        form = QFormLayout()
        self.title_edit = QLineEdit(str(self.workflow.get("title", "")))
        self.title_edit.setPlaceholderText("Prepare work session")
        form.addRow("Title", self.title_edit)
        self.description_edit = QLineEdit(str(self.workflow.get("description", "")))
        self.description_edit.setPlaceholderText("Optional description")
        form.addRow("Description", self.description_edit)
        layout.addLayout(form)

        layout.addWidget(QLabel("Steps (JSON)"))
        self.steps_edit = QPlainTextEdit()
        self.steps_edit.setPlaceholderText(
            '[\n  {"type": "open_folder", "path": "C:/Projects"},\n'
            '  {"type": "open_url", "url": "https://example.com"},\n'
            '  {"type": "copy_text", "text": "Ready"}\n]'
        )
        steps = self.workflow.get("steps", [])
        self.steps_edit.setPlainText(json.dumps(steps, ensure_ascii=False, indent=2) if steps else "")
        layout.addWidget(self.steps_edit, 1)
        hint = QLabel(
            "Supported steps: open_folder, open_url, launch_app (executable + args list), "
            "copy_text, run_command (existing command key/title + args list). "
            "Destructive commands require confirmation; shell scripts and Python are not supported."
        )
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self) -> None:
        try:
            steps = json.loads(self.steps_edit.toPlainText())
        except (TypeError, ValueError) as exc:
            show_error(self, "Invalid workflow JSON", str(exc))
            return
        data = {
            "title": self.title_edit.text().strip(),
            "description": self.description_edit.text().strip(),
            "steps": steps,
        }
        if self.workflow.get("id"):
            data["id"] = self.workflow["id"]
        ok, message = self.service.save(data)
        if not ok:
            show_error(self, "Could not save workflow", message)
            return
        self.accept()



class SnippetDialog(QDialog):
    """Create or edit a reusable text snippet."""

    def __init__(self, service, snippet: dict | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.service = service
        self.snippet = snippet or {}
        self.setWindowTitle("Edit snippet" if snippet else "New snippet")
        self.resize(620, 520)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 12)
        form = QFormLayout()
        self.title_edit = QLineEdit(str(self.snippet.get("title", "")))
        self.title_edit.setPlaceholderText("Email signature")
        form.addRow("Title", self.title_edit)
        self.category_edit = QLineEdit(str(self.snippet.get("category", "")))
        self.category_edit.setPlaceholderText("Work, school, coding…")
        form.addRow("Category", self.category_edit)
        self.shortcut_edit = QLineEdit(str(self.snippet.get("shortcut", "")))
        self.shortcut_edit.setPlaceholderText("Optional search alias, e.g. sig")
        form.addRow("Shortcut / alias", self.shortcut_edit)
        layout.addLayout(form)
        layout.addWidget(QLabel("Text"))
        self.content_edit = QPlainTextEdit()
        self.content_edit.setPlainText(str(self.snippet.get("content", "")))
        self.content_edit.setPlaceholderText("Write reusable text here…")
        layout.addWidget(self.content_edit, 1)
        hint = QLabel("Snippets are stored locally and copied only when you explicitly select them.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self) -> None:
        data = {
            "title": self.title_edit.text().strip(),
            "category": self.category_edit.text().strip(),
            "shortcut": self.shortcut_edit.text().strip(),
            "content": self.content_edit.toPlainText(),
        }
        if self.snippet.get("id"):
            data["id"] = self.snippet["id"]
        ok, message = self.service.save(data)
        if not ok:
            show_error(self, "Could not save snippet", message)
            return
        self.accept()


class EngineDialog(QDialog):
    """Add or edit a custom web search engine."""

    def __init__(self, name: str = "", label: str = "", url: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Search engine")
        self.resize(480, 240)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        form = QFormLayout()
        self.name_edit = QLineEdit(name)
        self.name_edit.setPlaceholderText("myengine")
        form.addRow("Identifier", self.name_edit)
        self.label_edit = QLineEdit(label)
        self.label_edit.setPlaceholderText("My engine")
        form.addRow("Label", self.label_edit)
        self.url_edit = QLineEdit(url)
        self.url_edit.setPlaceholderText("https://example.com/search?q={query}")
        form.addRow("URL template", self.url_edit)
        layout.addLayout(form)
        hint = QLabel("Use {query} where the percent-encoded search text belongs.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.error = QLabel("")
        self.error.setObjectName("Muted")
        layout.addWidget(self.error)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self) -> None:
        identifier = self.name_edit.text().strip().lower().replace(" ", "_")
        label = self.label_edit.text().strip() or identifier.title()
        url = self.url_edit.text().strip()
        if not identifier:
            self.error.setText("An identifier is required")
            return
        if not url.startswith(("http://", "https://")):
            self.error.setText("The URL must start with http:// or https://")
            return
        if "{query}" not in url:
            self.error.setText("The URL must contain {query}")
            return
        self.result = {"key": identifier, "label": label, "url": url}
        self.accept()


__all__ = [
    "show_info",
    "show_error",
    "ask_confirm",
    "TextDialog",
    "QuickLookDialog",
    "CommandEditorDialog",
    "SSHProfileDialog",
    "QuickActionDialog",
    "WorkflowDialog",
    "SnippetDialog",
    "EngineDialog",
]
