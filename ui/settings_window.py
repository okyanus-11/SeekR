"""SeekR settings window."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFontComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core import startup
from core.constants import DATE_FORMAT_PRESETS, THEME_IDS, THEME_LABELS, WEB_ENGINES
from core.logging_setup import get_logger
from core.paths import app_data_dir, config_path, database_path, log_path
from core.version import (
    APP_AUTHOR,
    APP_COPYRIGHT,
    APP_DESCRIPTION,
    APP_LICENSE,
    APP_NAME,
    APP_REPO_URL,
    APP_VERSION,
)
from ui import dialogs, i18n
from ui.components import (
    refresh_localized_widgets,
    ColorButton,
    HotkeyEdit,
    InfoBanner,
    ScrollPage,
    SectionCard,
    SettingRow,
    Switch,
    danger_button,
    hline,
    label,
    primary_button,
    secondary_button,
)
from ui.dialogs import EngineDialog

log = get_logger(__name__)


# --------------------------------------------------------------------- helpers
def bind_switch(config, key: str, on_change: Optional[Callable[[bool], None]] = None) -> Switch:
    switch = Switch()
    switch.setChecked(bool(config.get(key, False)))
    def _changed(checked: bool) -> None:
        config.set(key, checked)
        if on_change is not None:
            on_change(checked)
    switch.toggled.connect(_changed)
    return switch


def bind_combo(config, key: str, options: list[tuple[Any, str]]) -> QComboBox:
    combo = QComboBox()
    for value, text in options:
        combo.addItem(text, value)
    index = combo.findData(config.get(key))
    if index < 0:
        index = combo.findText(str(config.get(key, "")))
    if index >= 0:
        combo.setCurrentIndex(index)
    combo.currentIndexChanged.connect(lambda _row: config.set(key, combo.currentData()))
    return combo


def bind_spin(config, key: str, low: int, high: int, suffix: str = "") -> QSpinBox:
    spin = QSpinBox()
    spin.setRange(low, high)
    spin.setValue(int(config.get(key, low) or low))
    if suffix:
        spin.setSuffix(suffix)
    spin.valueChanged.connect(lambda value: config.set(key, value))
    spin.setMinimumWidth(110)
    return spin


def bind_line(config, key: str, placeholder: str = "") -> QLineEdit:
    line = QLineEdit(str(config.get(key, "") or ""))
    line.setPlaceholderText(placeholder)
    line.editingFinished.connect(lambda: config.set(key, line.text().strip()))
    return line


class ListEditor(QWidget):
    """Edits a list of strings with add/remove buttons."""

    def __init__(
        self,
        values: list[str],
        on_change: Callable[[list[str]], None],
        picker: str = "text",
        placeholder: str = "Add an item",
    ):
        super().__init__()
        self.on_change = on_change
        self.picker = picker
        self.placeholder = placeholder
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("PlainList")
        self.list_widget.setMaximumHeight(140)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        layout.addWidget(self.list_widget)
        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        buttons.addWidget(secondary_button("Add…", self._add))
        buttons.addWidget(secondary_button("Remove", self._remove))
        buttons.addStretch(1)
        layout.addLayout(buttons)
        for value in values:
            self.list_widget.addItem(str(value))
        self.on_change(self.values())

    def values(self) -> list[str]:
        return [self.list_widget.item(i).text() for i in range(self.list_widget.count())]

    def _emit(self) -> None:
        self.on_change(self.values())

    def _add(self) -> None:
        if self.picker == "folder":
            value = QFileDialog.getExistingDirectory(self, "Select a folder")
            if value:
                self.list_widget.addItem(value)
                self._emit()
            return
        text, accepted = QInputDialog.getText(self, "Add item", self.placeholder)
        if accepted and text.strip():
            self.list_widget.addItem(text.strip())
            self._emit()

    def _remove(self) -> None:
        for item in self.list_widget.selectedItems():
            self.list_widget.takeItem(self.list_widget.row(item))
        self._emit()


class KeyValueEditor(QWidget):
    """A two-column table editor for alias mappings."""

    def __init__(self, values: dict, key_header: str, value_header: str, config, key: str):
        super().__init__()
        self.config = config
        self.config_key = key
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels([key_header, value_header])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setMinimumHeight(130)
        layout.addWidget(self.table)
        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        buttons.addWidget(secondary_button("Add row", self._add_row))
        buttons.addWidget(secondary_button("Remove row", self._remove_row))
        buttons.addStretch(1)
        buttons.addWidget(primary_button("Save", self.save))
        layout.addLayout(buttons)
        self.load(values)

    def load(self, values: dict) -> None:
        self.table.setRowCount(0)
        for name, aliases in (values or {}).items():
            items = aliases if isinstance(aliases, (list, tuple)) else [aliases]
            self._append(str(name), ", ".join(str(item) for item in items))

    def _append(self, first: str, second: str) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(first))
        self.table.setItem(row, 1, QTableWidgetItem(second))

    def _add_row(self) -> None:
        self._append("", "")
        self.table.setCurrentCell(self.table.rowCount() - 1, 0)
        self.table.editItem(self.table.item(self.table.rowCount() - 1, 0))

    def _remove_row(self) -> None:
        rows = sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.table.removeRow(row)

    def values(self) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for row in range(self.table.rowCount()):
            first = self.table.item(row, 0)
            second = self.table.item(row, 1)
            name = first.text().strip() if first is not None else ""
            aliases = second.text().strip() if second is not None else ""
            if not name:
                continue
            result[name] = [part.strip() for part in aliases.split(",") if part.strip()]
        return result

    def save(self) -> None:
        self.config.set(self.config_key, self.values())


class SettingsPage(ScrollPage):
    """Base class for a settings page."""

    title = ""
    subtitle = ""

    def __init__(self, window: "SettingsWindow"):
        super().__init__()
        self.window = window
        self.controller = window.controller
        self.config = window.config
        self.db = window.db
        self.settings = window

        header = QVBoxLayout()
        header.setSpacing(2)
        heading = label(self.title, "Heading")
        header.addWidget(heading)
        if self.subtitle:
            description = label(self.subtitle, "Muted", wrap=True)
            header.addWidget(description)
        self.layout.addLayout(header)
        self.layout.addSpacing(4)
        self.build()

    def build(self) -> None:  # pragma: no cover - overridden
        pass

    def section(self, title: str, subtitle: str = "") -> SectionCard:
        card = SectionCard(title, subtitle)
        self.layout.addWidget(card)
        return card

    def row(self, card: SectionCard, title: str, description: str, control: QWidget) -> SettingRow:
        row = SettingRow(title, description)
        row.add_control(control)
        card.add_row(row)
        return row

    def on_show(self) -> None:
        pass

    def saved(self, message: str = "Saved") -> None:
        self.window.show_status(message)


# ---------------------------------------------------------------------- General
class GeneralPage(SettingsPage):
    title = "General"
    subtitle = "Startup behaviour, the global hotkey and the launcher's language."

    def build(self) -> None:
        startup_card = self.section("Startup", "How SeekR starts and behaves when Windows starts.")
        self.startup_switch = Switch()
        self.startup_switch.setChecked(startup.is_enabled())
        self.startup_switch.toggled.connect(self._toggle_startup)
        self.row(
            startup_card,
            "Start with Windows",
            "Adds SeekR to your login items.",
            self.startup_switch,
        )
        self.row(
            startup_card,
            "Start minimised",
            "Open SeekR without showing the launcher window.",
            bind_switch(self.config, "general.start_minimized"),
        )
        self.row(
            startup_card,
            "Show tray icon",
            "Keep SeekR available in the notification area.",
            bind_switch(self.config, "general.show_tray_icon"),
        )

        hotkey_card = self.section("Global hotkey", "Summon SeekR from any application.")
        self.hotkey_edit = HotkeyEdit(str(self.config.get("general.hotkey", "Alt+Space")))
        hotkey_edit = self.hotkey_edit
        hotkey_row = QHBoxLayout()
        hotkey_row.addWidget(hotkey_edit, 1)
        hotkey_container = QWidget()
        hotkey_container.setLayout(hotkey_row)
        hotkey_row.addWidget(primary_button("Apply", self._apply_hotkey))
        hotkey_row.addWidget(secondary_button("Reset", self._reset_hotkey))
        self.row(
            hotkey_card,
            "Launcher shortcut",
            "Click the field and press a new combination. Conflicts are reported by Windows.",
            hotkey_container,
        )
        for platform_text, enabled in (
            ("Global hotkeys require Windows; the tray icon remains available on other systems.", os.name != "nt"),
        ):
            if enabled:
                note = label(platform_text, "Muted", wrap=True)
                hotkey_card.add_widget(note)

        launcher_card = self.section("Launcher", "Dismissal and query behaviour.")
        self.row(
            launcher_card,
            "Hide when focus is lost",
            "Clicking outside the launcher hides it.",
            bind_switch(self.config, "general.hide_on_focus_loss"),
        )
        self.row(
            launcher_card,
            "Remember the last query",
            "Reopen the launcher with the previous search text.",
            bind_switch(self.config, "general.remember_last_query"),
        )
        self.row(
            launcher_card,
            "Confirm destructive commands",
            "Ask before shutdown, restart, sleep and emptying the Recycle Bin.",
            bind_switch(self.config, "general.confirm_destructive_actions"),
        )

        language_card = self.section("Language", "Choose the language used by the launcher.")
        languages = [(code, name) for code, name in i18n.LANGUAGES.items()]
        self.row(
            language_card,
            "Interface language",
            "English, Turkish, Spanish, French, German, Italian, Brazilian Portuguese, Japanese and Simplified Chinese are available. The launcher, common controls, shared headings and Tools navigation are localized; longer descriptions and some dialogs remain in English.",
            bind_combo(self.config, "general.language", languages),
        )

    def _toggle_startup(self, checked: bool) -> None:
        ok, message = startup.set_enabled(checked)
        if not ok:
            self.startup_switch.blockSignals(True)
            self.startup_switch.setChecked(not checked)
            self.startup_switch.blockSignals(False)
            self.controller.show_error("Startup setting", message)
            return
        self.config.set("general.start_with_windows", checked)
        self.saved(message)

    def _apply_hotkey(self) -> None:
        value = self.hotkey_edit.text().strip()
        if not value:
            self.controller.show_error("Hotkey", "Enter a key combination first")
            return
        ok, message = self.controller.apply_hotkey(value)
        if not ok:
            self.controller.show_error("Hotkey unavailable", message)
            self.hotkey_edit.set_hotkey(str(self.config.get("general.hotkey", "Alt+Space")))
            return
        self.config.set("general.hotkey", value)
        self.saved(message)

    def _reset_hotkey(self) -> None:
        self.config.set("general.hotkey", "Alt+Space")
        self.hotkey_edit.set_hotkey("Alt+Space")
        self.saved("Hotkey reset to Alt+Space")


# -------------------------------------------------------------------- Appearance
class AppearancePage(SettingsPage):
    title = "Appearance"
    subtitle = "Theme, accent colour, typography, geometry and animations."

    def build(self) -> None:
        theme_card = self.section("Theme", "Every SeekR window follows the selected theme.")
        self.row(
            theme_card,
            "Theme",
            "Graphite, light, AMOLED and three popular developer palettes.",
            bind_combo(self.config, "appearance.theme", [(key, THEME_LABELS[key]) for key in THEME_IDS]),
        )
        accent = ColorButton(str(self.config.get("appearance.accent", "#68a9ff")))
        accent.colorChanged.connect(lambda value: self.config.set("appearance.accent", value))
        self.row(theme_card, "Accent colour", "Used for selection, focus rings and highlights.", accent)
        opacity_row = QHBoxLayout()
        self.opacity_value = label(f"{int(float(self.config.get('appearance.opacity', 0.98)) * 100)}%", "Muted")
        opacity_slider = QSlider(Qt.Orientation.Horizontal)
        opacity_slider.setRange(65, 100)
        opacity_slider.setValue(int(float(self.config.get("appearance.opacity", 0.98)) * 100))
        opacity_slider.setFixedWidth(170)
        def _opacity(value: int) -> None:
            self.opacity_value.setText(f"{value}%")
            self.config.set("appearance.opacity", value / 100.0)
        opacity_slider.valueChanged.connect(_opacity)
        opacity_row.addWidget(opacity_slider)
        opacity_row.addWidget(self.opacity_value)
        opacity_container = QWidget()
        opacity_container.setLayout(opacity_row)
        opacity_row.setContentsMargins(0, 0, 0, 0)
        self.row(theme_card, "Window opacity", "Lower values make the launcher slightly translucent.", opacity_container)

        text_card = self.section("Typography")
        font_combo = QFontComboBox()
        font_combo.setCurrentFont(QFont(str(self.config.get("appearance.font_family", "Segoe UI"))))
        font_combo.currentFontChanged.connect(
            lambda font: self.config.set("appearance.font_family", font.family())
        )
        self.row(text_card, "Font family", "Applies to every window and result row.", font_combo)
        self.row(text_card, "Font size", "Base interface size in points.", bind_spin(self.config, "appearance.font_size", 8, 28, " pt"))

        layout_card = self.section("Layout")
        self.row(layout_card, "Launcher width", "Width of the search window.", bind_spin(self.config, "appearance.window_width", 460, 1600, " px"))
        self.row(layout_card, "Launcher height", "Height of the search window.", bind_spin(self.config, "appearance.window_height", 300, 1200, " px"))
        self.row(layout_card, "Result spacing", "Extra space between result rows.", bind_spin(self.config, "appearance.result_spacing", 0, 20, " px"))
        self.row(layout_card, "Corner radius", "Rounded corners of the launcher.", bind_spin(self.config, "appearance.corner_radius", 0, 30, " px"))
        self.row(layout_card, "Show icons", "Use real file and application icons in results.", bind_switch(self.config, "appearance.show_icons"))
        self.row(layout_card, "Show categories", "Display the category chip on each result.", bind_switch(self.config, "appearance.show_categories"))

        motion_card = self.section("Motion")
        self.row(motion_card, "Animations", "Subtle open, close and selection transitions.", bind_switch(self.config, "appearance.animations"))
        self.row(motion_card, "Animation duration", "Longer durations feel softer but slower.", bind_spin(self.config, "appearance.animation_duration", 0, 800, " ms"))

        reset = secondary_button("Reset appearance to defaults", self._reset)
        self.layout.addWidget(reset, 0, Qt.AlignmentFlag.AlignLeft)

    def _reset(self) -> None:
        if not dialogs.ask_confirm(self, "Reset appearance", "Restore all appearance settings to their defaults?"):
            return
        for key in (
            "appearance.theme",
            "appearance.accent",
            "appearance.opacity",
            "appearance.font_family",
            "appearance.font_size",
            "appearance.window_width",
            "appearance.window_height",
            "appearance.result_spacing",
            "appearance.corner_radius",
            "appearance.animations",
            "appearance.animation_duration",
            "appearance.show_icons",
            "appearance.show_categories",
        ):
            self.config.set(key, self.config.defaults["appearance"][key.split(".")[-1]])
        self.controller.open_settings("appearance")



# ------------------------------------------------------------------------ Widgets
class WidgetsPage(SettingsPage):
    title = "Widgets"
    subtitle = "Choose what appears around the Alt+Space search results."

    def build(self) -> None:
        cards = self.section("Launcher widgets", "Enabled by default. Changes are saved immediately.")
        self.row(cards, "Clock", "Live local time and date · left rail.", bind_switch(self.config, "widgets.clock_enabled", self._widgets_changed))
        self.row(cards, "System usage", "Live CPU and memory usage · left rail.", bind_switch(self.config, "widgets.system_enabled", self._widgets_changed))
        self.row(cards, "Weather", "Current conditions for your chosen location · right rail.", bind_switch(self.config, "widgets.weather_enabled", self._widgets_changed))
        self.row(cards, "Daily meme", "A daily pick cached locally until the next day · right rail.", bind_switch(self.config, "widgets.meme_enabled", self._widgets_changed))
        location = self.section("Weather location", "Enter a city or town. SeekR uses Open-Meteo for geocoding and current conditions.")
        self.location_edit = QLineEdit(str(self.config.get("widgets.weather_location", "") or ""))
        self.location_edit.setPlaceholderText("e.g. Izmir, Türkiye")
        self.location_edit.editingFinished.connect(self._save_location)
        self.row(location, "Location", "No GPS permission is requested; this text is used for the weather lookup.", self.location_edit)
        location.add_widget(label("Weather and daily meme require an internet connection. System usage and clock stay local.", "Muted", wrap=True))

    def _widgets_changed(self, _checked: bool) -> None:
        launcher = getattr(self.controller, "launcher", None)
        if launcher is not None and hasattr(launcher, "launcher_widgets"):
            launcher.launcher_widgets.refresh_settings(animate=True)

    def _save_location(self) -> None:
        value = self.location_edit.text().strip()
        self.config.set("widgets.weather_location", value)
        self._widgets_changed(True)
        self.saved("Weather location saved")


# ------------------------------------------------------------------------ Search
class SearchPage(SettingsPage):
    title = "Search"
    subtitle = "Ranking, matching and result limits."

    def build(self) -> None:
        card = self.section("Matching")
        self.row(card, "Fuzzy matching", "Match non-contiguous text such as 'vsc' for 'Visual Studio Code'.", bind_switch(self.config, "search.fuzzy"))
        self.row(card, "Typo tolerance", "Find results even when the query is slightly misspelt.", bind_switch(self.config, "search.typo_tolerance"))
        self.row(card, "Automatic detection", "Recognise expressions and suggest keywords while typing.", bind_switch(self.config, "search.auto_detect"))
        self.row(card, "Prioritise recent items", "Boost applications and files you used recently.", bind_switch(self.config, "search.prioritize_recent"))
        self.row(card, "Maximum results", "Upper bound for the launcher list.", bind_spin(self.config, "search.max_results", 3, 50))
        self.row(card, "Search debounce", "Delay before a query runs while typing.", bind_spin(self.config, "search.debounce_ms", 40, 800, " ms"))

        history = self.section("History")
        self.row(history, "Save search history", "Stores executed queries locally to improve suggestions.", bind_switch(self.config, "privacy.save_search_history"))
        self.row(history, "History entries kept", "Older entries are pruned automatically.", bind_spin(self.config, "search.history_limit", 10, 5000))
        clear = danger_button("Clear search history", self._clear_history)
        history.add_widget(clear)

        providers = self.section(
            "Providers",
            "Disable capabilities you do not need; disabled providers stop producing results.",
        )
        disabled = set(self.config.get("search.disabled_providers", []) or [])
        container = QWidget()
        grid = QGridLayout(container)
        grid.setContentsMargins(0, 4, 0, 4)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(6)
        providers_sorted = sorted(self.controller.engine.providers, key=lambda item: (item.title or item.id).lower())
        for index, provider in enumerate(providers_sorted):
            switch = Switch()
            switch.setChecked(provider.id not in disabled)
            def _toggle(checked: bool, provider_id: str = provider.id) -> None:
                current = set(self.config.get("search.disabled_providers", []) or [])
                if checked:
                    current.discard(provider_id)
                else:
                    current.add(provider_id)
                self.config.set("search.disabled_providers", sorted(current))
            switch.toggled.connect(_toggle)
            label_text = QLabel(provider.title or provider.id)
            label_text.setObjectName("Muted")
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 2, 0, 2)
            row_layout.addWidget(switch)
            row_layout.addWidget(label_text)
            row_layout.addStretch(1)
            grid.addWidget(row_widget, index // 3, index % 3)
        providers.add_widget(container)

        aliases = self.section(
            "Keyword aliases",
            "Add alternative keywords, for example 'w' → 'web'. Save applies them immediately.",
        )
        self.alias_editor = KeyValueEditor(
            self.config.get("search.keyword_aliases", {}) or {},
            "Alias",
            "Keyword (web, calc, file…)",
            self.config,
            "search.keyword_aliases",
        )
        aliases.add_widget(self.alias_editor)

    def _clear_history(self) -> None:
        if not dialogs.ask_confirm(self, "Clear search history", "Delete all stored search queries?"):
            return
        self.db.clear_history(["search"])
        self.saved("Search history cleared")


# ------------------------------------------------------------------ Applications
class ApplicationsPage(SettingsPage):
    title = "Applications"
    subtitle = "Which applications are indexed and how they are refreshed."

    def build(self) -> None:
        card = self.section("Indexing")
        self.row(card, "Index Start Menu shortcuts", "Discovers installed applications from the Start Menu (or XDG menus).", bind_switch(self.config, "applications.index_start_menu"))
        self.row(
            card,
            "Scan Program Files",
            "Adds executables found under Program Files. This can take a while on large systems.",
            bind_switch(self.config, "applications.scan_program_files"),
        )
        self.row(
            card,
            "Refresh stale index at startup",
            "Re-scan installed applications when the stored index is older than the refresh interval.",
            bind_switch(self.config, "applications.refresh_on_start"),
        )

        extra = self.section(
            "Additional application folders",
            "Scan portable apps or shortcut folders that are not in the Start Menu.",
        )
        extra.add_widget(
            ListEditor(
                self.config.get("applications.directories", []) or [],
                lambda values: self.config.set("applications.directories", values),
                picker="folder",
            )
        )
        self.row(card, "Refresh interval", "How often the index is considered stale at startup.", bind_spin(self.config, "applications.refresh_interval_hours", 1, 720, " h"))

        stats_card = self.section("Index status")
        self.stats_label = label("", "Muted", wrap=True)
        stats_card.add_widget(self.stats_label)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        stats_card.add_widget(self.progress)
        button_row = QHBoxLayout()
        button_row.addWidget(primary_button("Refresh application index", self._refresh))
        button_row.addStretch(1)
        button_holder = QWidget()
        button_holder.setLayout(button_row)
        stats_card.add_widget(button_holder)
        self.controller.index_progress.connect(self._on_progress)
        self._refresh_stats()

    def _refresh(self) -> None:
        self.controller.refresh_applications()

    def _on_progress(self, percent: int, message: str) -> None:
        self.progress.setValue(percent)
        self.window.show_status(message)

    def _refresh_stats(self) -> None:
        count = self.db.count_apps()
        last = self.db.get_meta("apps_last_index")
        from features.util import format_ago

        self.stats_label.setText(
            f"{count} applications indexed" + (f"  ·  last refreshed {format_ago(float(last))}" if last else "")
        )

    def on_show(self) -> None:
        self._refresh_stats()

    def excluded(self) -> None:
        pass


# ------------------------------------------------------------------------- Files
class FilesPage(SettingsPage):
    title = "Files"
    subtitle = "Folders SeekR indexes for instant file and folder search."

    def build(self) -> None:
        card = self.section("Indexing")
        self.row(card, "Enable file search", "Turn file indexing and file results on or off.", bind_switch(self.config, "files.enabled"))
        self.row(card, "Index automatically at startup", "Rebuild the index when it is older than a day.", bind_switch(self.config, "files.auto_index"))
        self.row(card, "Include hidden files", "Index dotfiles and hidden entries.", bind_switch(self.config, "files.include_hidden"))
        self.row(card, "Include folders", "Folders appear in file search results.", bind_switch(self.config, "files.include_folders"))

        content = self.section("Document content search", "Optional on-demand local search. Disabled by default; only configured folders, extensions and size limits are read.")
        self.row(content, "Enable content search", "Search inside supported text files with content:. File contents are not uploaded.", bind_switch(self.config, "files.content_search_enabled"))
        self.row(content, "Maximum file size", "Larger files are skipped to keep searches responsive.", bind_spin(self.config, "files.content_search_max_file_bytes", 100000, 10000000, " bytes"))
        content.add_widget(
            ListEditor(
                self.config.get("files.content_search_extensions", [".txt", ".md", ".py", ".json", ".csv", ".html", ".xml"]),
                lambda values: self.config.set("files.content_search_extensions", values),
            )
        )
        self.row(card, "Maximum depth", "How deep SeekR walks each folder.", bind_spin(self.config, "files.max_depth", 1, 30))
        self.row(card, "Maximum entries", "Hard limit that keeps the index memory-friendly.", bind_spin(self.config, "files.max_files", 1000, 3000000))

        directories = self.section("Indexed folders", "Add the folders you search most often.")
        directories.add_widget(
            ListEditor(self.config.get("files.directories", []), lambda values: self.config.set("files.directories", values), picker="folder")
        )

        excluded_dirs = self.section("Excluded folders", "Folder names skipped anywhere in the tree.")
        excluded_dirs.add_widget(
            ListEditor(self.config.get("files.excluded_dirs", []), lambda values: self.config.set("files.excluded_dirs", values))
        )

        excluded_ext = self.section("Excluded extensions", "Files with these extensions are never indexed.")
        excluded_ext.add_widget(
            ListEditor(self.config.get("files.excluded_extensions", []), lambda values: self.config.set("files.excluded_extensions", values))
        )

        shots = self.section("Screenshots", "Where the screenshot tool saves captured images.")
        shot_row = QHBoxLayout()
        self.screenshot_edit = QLineEdit(str(self.config.get("screenshots.directory", "") or ""))
        self.screenshot_edit.setPlaceholderText("Default: Pictures\\SeekR")
        shot_row.addWidget(self.screenshot_edit, 1)
        shot_row.addWidget(secondary_button("Browse…", self._browse_screenshot_dir))
        shot_row.addWidget(secondary_button("Use default", self._reset_screenshot_dir))
        shot_holder = QWidget()
        shot_holder.setLayout(shot_row)
        shots.add_widget(shot_holder)
        self.screenshot_edit.editingFinished.connect(self._save_screenshot_dir)

        status = self.section("Index status")
        self.stats_label = label("", "Muted", wrap=True)
        status.add_widget(self.stats_label)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        status.add_widget(self.progress)
        buttons = QHBoxLayout()
        buttons.addWidget(primary_button("Index now", self._refresh))
        buttons.addWidget(secondary_button("Stop indexing", self._stop))
        buttons.addStretch(1)
        holder = QWidget()
        holder.setLayout(buttons)
        status.add_widget(holder)
        self.controller.index_progress.connect(self._on_progress)
        self._refresh_stats()

    def _save_screenshot_dir(self) -> None:
        from core.paths import default_screenshot_dir

        value = self.screenshot_edit.text().strip()
        if value and not Path(value).expanduser().is_dir():
            try:
                Path(value).expanduser().mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                self.controller.show_error("Screenshot folder", f"Could not use that folder:\n{exc}")
                self.screenshot_edit.setText(str(self.config.get("screenshots.directory", "")))
                return
        self.config.set("screenshots.directory", value or default_screenshot_dir())
        self.saved("Screenshot folder updated")

    def _browse_screenshot_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select the screenshot folder")
        if directory:
            self.screenshot_edit.setText(directory)
            self._save_screenshot_dir()

    def _reset_screenshot_dir(self) -> None:
        from core.paths import default_screenshot_dir

        self.screenshot_edit.setText(default_screenshot_dir())
        self._save_screenshot_dir()

    def _refresh(self) -> None:
        self.controller.refresh_files()

    def _stop(self) -> None:
        self.controller.cancel_file_index()
        self.window.show_status("Stopping the file index…")

    def _on_progress(self, percent: int, message: str) -> None:
        self.progress.setValue(percent)
        self.window.show_status(message)

    def _refresh_stats(self) -> None:
        from features.util import format_ago

        count = self.db.count_files()
        last = self.db.get_meta("files_last_index")
        text = f"{count} indexed items"
        if last:
            try:
                text += f"  ·  last indexed {format_ago(float(last))}"
            except ValueError:
                pass
        self.stats_label.setText(text)

    def on_show(self) -> None:
        self._refresh_stats()


# --------------------------------------------------------------------------- Web
class WebPage(SettingsPage):
    title = "Web"
    subtitle = "Default search engine, browser and custom search URLs."

    def build(self) -> None:
        card = self.section("Search engine")
        engines = self.controller.web_service.engines()
        self.engine_combo = QComboBox()
        for key, meta in engines.items():
            self.engine_combo.addItem(meta["label"], key)
        current = self.engine_combo.findData(self.config.get("web.engine"))
        if current >= 0:
            self.engine_combo.setCurrentIndex(current)
        self.engine_combo.currentIndexChanged.connect(
            lambda _row: self.config.set("web.engine", self.engine_combo.currentData())
        )
        self.row(card, "Default engine", "Used for web: suggestions and the web fallback result.", self.engine_combo)

        browser_row = QHBoxLayout()
        self.browser_edit = QLineEdit(str(self.config.get("web.browser", "system") or "system"))
        self.browser_edit.setPlaceholderText("system")
        self.browser_edit.editingFinished.connect(self._save_browser)
        browser_row.addWidget(self.browser_edit, 1)
        browser_row.addWidget(secondary_button("Browse…", self._browse_browser))
        browser_row.addWidget(secondary_button("Use system", self._system_browser))
        holder = QWidget()
        holder.setLayout(browser_row)
        self.row(card, "Browser", "Leave as 'system' to use your default browser, or pick a browser executable.", holder)
        self.browser_hint = label("", "Muted", wrap=True)
        card.add_widget(self.browser_hint)
        self._update_browser_hint()

        engines_card = self.section("Search engines", "Built-in engines plus your own templates using {query}.")
        self.engine_list = QListWidget()
        self.engine_list.setObjectName("PlainList")
        self.engine_list.setMaximumHeight(170)
        engines_card.add_widget(self.engine_list)
        buttons = QHBoxLayout()
        buttons.addWidget(secondary_button("Add engine…", self._add_engine))
        buttons.addWidget(secondary_button("Edit…", self._edit_engine))
        buttons.addWidget(secondary_button("Remove", self._remove_engine))
        buttons.addStretch(1)
        buttons_holder = QWidget()
        buttons_holder.setLayout(buttons)
        engines_card.add_widget(buttons_holder)
        self._reload_engines()

    def _save_browser(self) -> None:
        value = self.browser_edit.text().strip() or "system"
        if value.lower() != "system" and not Path(value).expanduser().exists():
            self.controller.show_error("Browser", f"Browser executable not found:\n{value}")
            return
        self.config.set("web.browser", value)
        self._update_browser_hint()
        self.saved("Browser updated")

    def _browse_browser(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select a browser executable")
        if path:
            self.browser_edit.setText(path)
            self._save_browser()

    def _system_browser(self) -> None:
        self.browser_edit.setText("system")
        self._save_browser()

    def _update_browser_hint(self) -> None:
        browser = str(self.config.get("web.browser", "system"))
        if browser.lower() == "system":
            self.browser_hint.setText("Using the operating system default browser.")
        else:
            exists = Path(browser).expanduser().exists()
            self.browser_hint.setText(
                ("Configured: " if exists else "Not found: ") + browser
            )

    def _reload_engines(self) -> None:
        self.engine_list.clear()
        for key, meta in self.controller.web_service.engines().items():
            item = QListWidgetItem(f"{meta['label']}   ·   {key}\n{meta['url']}")
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.engine_list.addItem(item)

    def _save_engines(self, engines: dict) -> None:
        self.config.set("web.engines", engines)
        current = self.engine_combo.currentData()
        self.engine_combo.blockSignals(True)
        self.engine_combo.clear()
        for key, meta in self.controller.web_service.engines().items():
            self.engine_combo.addItem(meta["label"], key)
        index = self.engine_combo.findData(current)
        if index >= 0:
            self.engine_combo.setCurrentIndex(index)
        self.engine_combo.blockSignals(False)
        self._reload_engines()

    def _add_engine(self) -> None:
        dialog = EngineDialog(parent=self)
        if dialog.exec():
            engines = dict(self.config.get("web.engines", {}) or {})
            engines[dialog.result["key"]] = {"label": dialog.result["label"], "url": dialog.result["url"]}
            self._save_engines(engines)
            self.window.show_status(f"Added search engine {dialog.result['label']}")

    def _edit_engine(self) -> None:
        item = self.engine_list.currentItem()
        if item is None:
            return
        key = item.data(Qt.ItemDataRole.UserRole)
        engines = self.controller.web_service.engines()
        meta = engines.get(key, {})
        dialog = EngineDialog(key, meta.get("label", key), meta.get("url", ""), parent=self)
        if dialog.exec():
            updated = dict(self.config.get("web.engines", {}) or {})
            old_key = dialog.result["key"]
            if old_key != key:
                updated.pop(key, None)
            updated[old_key] = {"label": dialog.result["label"], "url": dialog.result["url"]}
            self._save_engines(updated)

    def _remove_engine(self) -> None:
        item = self.engine_list.currentItem()
        if item is None:
            return
        key = item.data(Qt.ItemDataRole.UserRole)
        if key in WEB_ENGINES:
            self.controller.show_error("Remove engine", "Built-in engines cannot be removed. You can edit them instead.")
            return
        engines = dict(self.config.get("web.engines", {}) or {})
        engines.pop(key, None)
        self._save_engines(engines)


# -------------------------------------------------------------------- Calculator
class CalculatorPage(SettingsPage):
    title = "Calculator"
    subtitle = "Precision, angle unit and calculation history."

    def build(self) -> None:
        card = self.section("Calculation")
        self.row(card, "Precision", "Significant digits shown in results.", bind_spin(self.config, "calculator.precision", 1, 30))
        self.row(
            card,
            "Angle unit",
            "Applies to sin, cos and tan.",
            bind_combo(self.config, "calculator.angle_unit", [("rad", "Radians"), ("deg", "Degrees")]),
        )
        self.row(card, "History limit", "Number of calculations kept locally (0 disables history).", bind_spin(self.config, "calculator.history_limit", 0, 500))

        history = self.section("History")
        self.history_list = QListWidget()
        self.history_list.setObjectName("PlainList")
        self.history_list.setMinimumHeight(150)
        history.add_widget(self.history_list)
        buttons = QHBoxLayout()
        buttons.addWidget(primary_button("Open calculator", lambda: self.controller.open_tools("calculator")))
        buttons.addWidget(danger_button("Clear history", self._clear))
        buttons.addStretch(1)
        holder = QWidget()
        holder.setLayout(buttons)
        history.add_widget(holder)
        self._reload()

    def _reload(self) -> None:
        self.history_list.clear()
        entries = self.controller.calculator_service.history(100)
        if not entries:
            self.history_list.addItem("No calculations yet")
        else:
            self.history_list.addItems(entries)

    def _clear(self) -> None:
        if not dialogs.ask_confirm(self, "Clear calculator history", "Delete all stored calculations?"):
            return
        self.controller.calculator_service.clear_history()
        self._reload()
        self.saved("Calculation history cleared")

    def on_show(self) -> None:
        self._reload()


# ---------------------------------------------------------------------- Commands
class CommandsPage(SettingsPage):
    title = "Commands"
    subtitle = "User-defined commands and confirmation behaviour."

    def build(self) -> None:
        card = self.section("Safety")
        self.row(card, "Ask before destructive commands", "Shutdown, restart, sleep and Recycle Bin commands always require confirmation.", bind_switch(self.config, "commands.confirm_destructive"))
        self.row(
            card,
            "Custom commands always use argument-safe execution",
            "SeekR never invokes a shell; each command runs as an executable with an argument list.",
            label("Shell-free", "CategoryChip"),
        )

        custom = self.section("Custom commands", "Available through the comm: keyword.")
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Name", "Executable", "Arguments", "Confirm"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setMinimumHeight(190)
        self.table.doubleClicked.connect(lambda _index: self._edit())
        custom.add_widget(self.table)
        buttons = QHBoxLayout()
        buttons.addWidget(primary_button("New command…", self._new))
        buttons.addWidget(secondary_button("Edit…", self._edit))
        buttons.addWidget(danger_button("Delete", self._delete))
        buttons.addStretch(1)
        holder = QWidget()
        holder.setLayout(buttons)
        custom.add_widget(holder)

        history = self.section("Execution history", "The last commands SeekR started.")
        self.history_list = QListWidget()
        self.history_list.setObjectName("PlainList")
        self.history_list.setMaximumHeight(140)
        history.add_widget(self.history_list)
        history.add_widget(danger_button("Clear command history", self._clear_history))
        self._reload()

    def _reload(self) -> None:
        self.table.setRowCount(0)
        for command in self.controller.command_service.custom_commands():
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = [
                command.raw.get("name", ""),
                command.raw.get("command", ""),
                command.raw.get("args", ""),
                "Yes" if command.raw.get("confirm", 1) else "No",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, command.raw.get("id"))
                self.table.setItem(row, column, item)
        self.history_list.clear()
        entries = self.controller.command_service.history(30)
        self.history_list.addItems(entries or ["No commands run yet"])

    def _selected_id(self) -> Optional[int]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _selected_row(self) -> Optional[dict]:
        command_id = self._selected_id()
        if command_id is None:
            return None
        for command in self.controller.command_service.custom_commands():
            if command.raw.get("id") == command_id:
                return command.raw
        return None

    def _new(self) -> None:
        dialog = dialogs.CommandEditorDialog(self.controller.command_service, parent=self)
        if dialog.exec():
            self._reload()
            self.saved("Command saved")

    def _edit(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        dialog = dialogs.CommandEditorDialog(self.controller.command_service, row, parent=self)
        if dialog.exec():
            self._reload()
            self.saved("Command updated")

    def _delete(self) -> None:
        command_id = self._selected_id()
        if command_id is None:
            return
        if not dialogs.ask_confirm(self, "Delete command", "Delete the selected custom command?"):
            return
        self.controller.command_service.delete_custom(command_id)
        self._reload()
        self.saved("Command deleted")

    def _clear_history(self) -> None:
        if not dialogs.ask_confirm(self, "Clear command history", "Delete the recorded command history?"):
            return
        self.db.clear_history(["command"])
        self._reload()

    def on_show(self) -> None:
        self._reload()


# ---------------------------------------------------------------------- Clipboard
class ClipboardPage(SettingsPage):
    title = "Clipboard"
    subtitle = "Clipboard history capture and storage. Capture is off until you opt in."

    def build(self) -> None:
        card = self.section("Capture")
        card.add_widget(label(
            "Clipboard text is stored unencrypted in SeekR’s local SQLite database. "
            "Only enable history if you are comfortable storing copied text on this computer.",
            "Muted", wrap=True,
        ))
        self.row(card, "Enable clipboard history", "Opt in to recording copied text locally so it can be reused.", bind_switch(self.config, "clipboard.enabled"))
        self.row(card, "Keep duplicate entries out", "Skips the entry when it matches the newest one.", bind_switch(self.config, "clipboard.ignore_duplicates"))
        self.row(card, "Skip private-key shaped text", "Avoids storing text that looks like a private key.", bind_switch(self.config, "clipboard.exclude_sensitive"))
        self.row(card, "History limit", "Older unpinned entries are pruned beyond this limit.", bind_spin(self.config, "clipboard.limit", 10, 2000))
        self.row(card, "Poll interval", "Fallback polling interval for clipboard changes.", bind_spin(self.config, "clipboard.poll_interval_ms", 200, 5000, " ms"))

        actions = self.section("History")
        self.count_label = label("", "Muted")
        actions.add_widget(self.count_label)
        buttons = QHBoxLayout()
        buttons.addWidget(primary_button("Open clipboard history", self.controller.open_clipboard))
        buttons.addWidget(danger_button("Clear history", self._clear))
        buttons.addStretch(1)
        holder = QWidget()
        holder.setLayout(buttons)
        actions.add_widget(holder)
        self._refresh_count()

    def _refresh_count(self) -> None:
        count = self.controller.clipboard_service.count()
        self.count_label.setText(f"{count} clipboard entries stored")

    def _clear(self) -> None:
        if not dialogs.ask_confirm(self, "Clear clipboard history", "Delete all unpinned clipboard entries?"):
            return
        self.controller.clipboard_service.clear(keep_pinned=True)
        self._refresh_count()
        self.saved("Clipboard history cleared")

    def on_show(self) -> None:
        self._refresh_count()


# ------------------------------------------------------------------------ Privacy
class PrivacyPage(SettingsPage):
    title = "Privacy"
    subtitle = "Everything SeekR stores stays on this computer."

    def build(self) -> None:
        card = self.section("What is stored")
        self.row(
            card,
            "Clipboard history",
            "Opt in to storing copied text unencrypted in SeekR’s local SQLite database.",
            bind_switch(self.config, "privacy.clipboard_history"),
        )
        self.row(card, "Search history", "Allow executed queries to be stored.", bind_switch(self.config, "privacy.save_search_history"))
        self.row(card, "Usage tracking", "Count application launches to rank frequent apps.",
                bind_switch(self.config, "privacy.usage_tracking"))
        self.row(card, "Retention", "History older than this is deleted automatically.", bind_spin(self.config, "privacy.retention_days", 1, 3650, " days"))

        data_card = self.section("Local data", "Delete what SeekR has recorded.")
        buttons = QGridLayout()
        buttons.setHorizontalSpacing(8)
        buttons.addWidget(secondary_button("Clear search history", self._clear_search), 0, 0)
        buttons.addWidget(secondary_button("Clear clipboard history", self._clear_clipboard), 0, 1)
        buttons.addWidget(secondary_button("Clear application usage", self._clear_usage), 0, 2)
        buttons.addWidget(danger_button("Delete all stored history", self._clear_all), 1, 0, 1, 3)
        holder = QWidget()
        holder.setLayout(buttons)
        data_card.add_widget(holder)
        data_card.add_widget(label(f"Data folder: {app_data_dir()}", "Muted", wrap=True))
        data_card.add_widget(secondary_button("Open data folder", lambda: self.controller.open_path(str(app_data_dir()))))

        notes_card = self.section("Notes", "Quick notes are stored in the local database and never leave this computer.")
        notes_card.add_widget(
            label(
                "Use Tools → Quick Notes to manage notes. Deleting all stored history does not remove notes.",
                "Muted",
                wrap=True,
            )
        )

    def _clear_search(self) -> None:
        if dialogs.ask_confirm(self, "Clear search history", "Delete all stored search queries?"):
            self.db.clear_history(["search"])
            self.saved("Search history cleared")

    def _clear_clipboard(self) -> None:
        if dialogs.ask_confirm(self, "Clear clipboard history", "Delete all unpinned clipboard entries?"):
            self.controller.clipboard_service.clear(keep_pinned=True)
            self.saved("Clipboard history cleared")

    def _clear_usage(self) -> None:
        if dialogs.ask_confirm(self, "Clear usage data", "Reset launch counts and recent application history?"):
            self.db._write("UPDATE apps SET use_count = 0, last_used = 0")
            self.db.clear_history(["app", "file", "web", "command", "calc"])
            self.saved("Usage data cleared")

    def _clear_all(self) -> None:
        if not dialogs.ask_confirm(
            self,
            "Delete all stored history",
            "This deletes search history, clipboard history, application usage and recent items.\nNotes, commands and connections are kept.\n\nContinue?",
        ):
            return
        self.db.clear_history()
        self.db.clear_clipboard(keep_pinned=False)
        self.db._write("UPDATE apps SET use_count = 0, last_used = 0")
        self.saved("All stored history deleted")


# ----------------------------------------------------------------------- Advanced
class AdvancedPage(SettingsPage):
    title = "Advanced"
    subtitle = "Diagnostics, storage and maintenance."

    def build(self) -> None:
        card = self.section("Diagnostics")
        self.row(card, "Debug mode", "Verbose logging and developer behaviour.", bind_switch(self.config, "advanced.debug"))
        self.row(card, "Write logs to disk", "Logs live in the SeekR data folder. Restart required.", bind_switch(self.config, "advanced.logging"))
        self.row(card, "Performance statistics", "Show search timing in the launcher footer.", bind_switch(self.config, "advanced.performance_stats"))
        self.row(card, "Single instance", "Only allow one SeekR process. Applies on next launch.", bind_switch(self.config, "advanced.single_instance"))

        updates = self.section("Updates", "Checks use the official SeekR GitHub releases API; no installer is downloaded or run automatically.")
        self.row(
            updates,
            "Check automatically",
            "Check once per day in the background. This sends a request to GitHub and is off by default.",
            bind_switch(self.config, "updates.check_automatically"),
        )
        updates.add_widget(secondary_button("Check now", self._check_updates))

        paths = self.section("Storage")
        paths.add_widget(label(f"Configuration: {config_path()}", "Muted", wrap=True))
        paths.add_widget(label(f"Database: {database_path()}", "Muted", wrap=True))
        paths.add_widget(label(f"Logs: {log_path()}", "Muted", wrap=True))
        self.database_size = label("", "Muted")
        paths.add_widget(self.database_size)
        buttons = QHBoxLayout()
        buttons.addWidget(secondary_button("Open data folder", lambda: self.controller.open_path(str(app_data_dir()))))
        buttons.addWidget(secondary_button("Open logs", lambda: self.controller.open_path(str(log_path().parent))))
        buttons.addWidget(secondary_button("Vacuum database", self._vacuum))
        buttons.addWidget(danger_button("Reset configuration", self._reset))
        buttons.addStretch(1)
        holder = QWidget()
        holder.setLayout(buttons)
        paths.add_widget(holder)
        self._refresh_size()

    def _check_updates(self) -> None:
        from core.workers import run_async

        run_async(
            self.controller.update_service.check_latest,
            on_finished=self._update_check_finished,
            on_failed=self._update_check_failed,
        )

    def _update_check_finished(self, info: dict) -> None:
        if info.get("update_available"):
            self.controller.show_info(
                "SeekR update available",
                f"Version {info['latest_version']} is available. Open the official release page: {info['release_url']}",
            )
        else:
            self.saved(f"SeekR {info['current_version']} is up to date")

    def _update_check_failed(self, message: str, _traceback_text: str) -> None:
        self.controller.show_error("Update check", message)

    def _refresh_size(self) -> None:
        path = database_path()
        size = path.stat().st_size if path.exists() else 0
        from features.util import format_bytes

        self.database_size.setText(f"Database size: {format_bytes(size)}")

    def _vacuum(self) -> None:
        try:
            self.db.vacuum()
            self._refresh_size()
            self.saved("Database compacted")
        except Exception as exc:
            self.controller.show_error("Database", f"Vacuum failed: {exc}")

    def _reset(self) -> None:
        if not dialogs.ask_confirm(
            self,
            "Reset configuration",
            "Restore every setting to its default value? Stored notes, history and commands are kept.",
        ):
            return
        self.config.reset()
        self.window.show_status("Configuration reset to defaults")
        self.controller.open_settings("general")

    def on_show(self) -> None:
        self._refresh_size()


# ------------------------------------------------------------------------ Plugins
class PluginsPage(SettingsPage):
    title = "Plugins"
    subtitle = "The plugin marketplace is not part of version 1.0.0."

    def build(self) -> None:
        banner = InfoBanner(
            "PLUGIN MARKETPLACE",
            "Extend SeekR with community-developed plugins, custom integrations and powerful new capabilities. "
            "Plugin support is coming in a future release.",
            badge_text="COMING SOON…",
        )
        self.layout.addWidget(banner)

        roadmap = self.section("What to expect")
        for text in (
            "Plugins will register new search providers and keywords without changing SeekR itself.",
            "The current provider architecture already isolates every capability behind a stable interface.",
            "There are no install buttons yet: plugin loading is intentionally not part of this release.",
            "SeekR will never run third-party code without your explicit action.",
        ):
            item = label("•  " + text, "Muted", wrap=True)
            roadmap.add_widget(item)

        status = self.section("Status")
        status.add_widget(label("Plugin loading: not available (by design)", "Muted"))
        status.add_widget(label("Marketplace: planned for a future release", "Muted"))
        status.add_widget(label("No plugins are installed", "Muted"))


# -------------------------------------------------------------------------- About
class AboutPage(SettingsPage):
    title = "About SeekR"
    subtitle = "Version information, credits and project links."

    def build(self) -> None:
        header = QHBoxLayout()
        mark = QLabel("S")
        mark.setObjectName("BrandMark")
        mark.setFixedSize(56, 56)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(mark)
        text = QVBoxLayout()
        text.setSpacing(2)
        name = label(APP_NAME, "Heading")
        text.addWidget(name)
        text.addWidget(label(APP_DESCRIPTION, "Muted", wrap=True))
        header.addLayout(text, 1)
        holder = QWidget()
        holder.setLayout(header)
        self.layout.addWidget(holder)

        info = self.section("Release")
        info.add_widget(SettingRow("Version", APP_VERSION))
        info.add_widget(SettingRow("License", APP_LICENSE))
        info.add_widget(SettingRow("Author", APP_AUTHOR))
        info.add_widget(SettingRow("Copyright", APP_COPYRIGHT))

        links = self.section("Project")
        repo_label = label(APP_REPO_URL, "Muted", wrap=True)
        repo_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        links.add_widget(repo_label)
        buttons = QHBoxLayout()
        buttons.addWidget(primary_button("Open GitHub repository", lambda: self.controller.open_url(APP_REPO_URL)))
        buttons.addWidget(secondary_button("Open license", lambda: self.controller.open_url(APP_REPO_URL + "/blob/main/LICENSE")))
        buttons.addStretch(1)
        button_holder = QWidget()
        button_holder.setLayout(buttons)
        links.add_widget(button_holder)

        updates = self.section("Updates")
        updates.add_widget(
            label(
                "Automatic update checks are opt-in and run once per day when enabled. "
                "Manual checks are available in Settings → Advanced or with update:.",
                "Muted",
                wrap=True,
            )
        )
        updates.add_widget(secondary_button("Check the repository", lambda: self.controller.open_url(APP_REPO_URL + "/releases")))

        runtime = self.section("Runtime")
        import PySide6

        runtime.add_widget(SettingRow("Python", sys.version.split()[0]))
        runtime.add_widget(SettingRow("PySide6 / Qt", PySide6.__version__))
        runtime.add_widget(SettingRow("Data folder", str(app_data_dir())))
        runtime.add_widget(SettingRow("Configuration", str(config_path())))


# -------------------------------------------------------------------------- Window
class SettingsWindow(QMainWindow):
    """Sidebar-based settings window."""

    PAGES: list[tuple[str, str, type[SettingsPage]]] = [
        ("general", "General", GeneralPage),
        ("appearance", "Appearance", AppearancePage),
        ("widgets", "Widgets", WidgetsPage),
        ("search", "Search", SearchPage),
        ("applications", "Applications", ApplicationsPage),
        ("files", "Files", FilesPage),
        ("web", "Web", WebPage),
        ("calculator", "Calculator", CalculatorPage),
        ("commands", "Commands", CommandsPage),
        ("clipboard", "Clipboard", ClipboardPage),
        ("privacy", "Privacy", PrivacyPage),
        ("advanced", "Advanced", AdvancedPage),
        ("plugins", "Plugins", PluginsPage),
        ("about", "About", AboutPage),
    ]

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.config = controller.config
        self.db = controller.db
        self.setWindowTitle(f"{APP_NAME} — Settings")
        self.setMinimumSize(900, 640)
        self.resize(1020, 720)

        central = QWidget()
        central.setObjectName("WindowRoot")
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = QListWidget()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(210)
        self.sidebar.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        layout.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)
        self.statusBar().showMessage("Settings are saved automatically")

        self.pages: dict[str, SettingsPage] = {}
        self.page_keys: list[str] = []
        for key, title, page_class in self.PAGES:
            page = page_class(self)
            self.pages[key] = page
            self.page_keys.append(key)
            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.sidebar.addItem(item)
            self.stack.addWidget(page)

        self.sidebar.currentRowChanged.connect(self._on_sidebar_changed)
        self.sidebar.setCurrentRow(0)

    def _on_sidebar_changed(self, row: int) -> None:
        if 0 <= row < len(self.page_keys):
            self.stack.setCurrentIndex(row)
            page = self.pages[self.page_keys[row]]
            page.on_show()

    def refresh_texts(self) -> None:
        """Refresh translated shared widgets and the settings sidebar."""
        refresh_localized_widgets(self)
        for row, (_key, title, _page_class) in enumerate(self.PAGES):
            item = self.sidebar.item(row)
            if item is not None:
                item.setText(i18n.translate_text(title))

    def open_page(self, page: Optional[str] = None) -> None:
        if page is None:
            return
        if page not in self.pages:
            return
        self.sidebar.setCurrentRow(self.page_keys.index(page))

    def show_status(self, message: str) -> None:
        self.statusBar().showMessage(message, 6000)

    def closeEvent(self, event) -> None:  # noqa: N802
        # Keep the window instance alive so reopening is instant.
        event.accept()


__all__ = ["SettingsWindow"]
