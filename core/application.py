"""Application controller: owns services, windows and UI hooks."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QObject, QThread, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from features import system_info, util
from features.applications import AppService, ApplicationsProvider
from features.bookmarks import BookmarksProvider
from features.calculator import (
    CalculatorProvider,
    CalculatorService,
    UnitProvider,
    warm_up as warm_up_calculator,
)
from features.clipboard import ClipboardMonitor, ClipboardProvider, ClipboardService
from features.color_tools import ColorProvider
from features.commands import CommandChainProvider, CommandService, CommandsProvider
from features.date_time import DateTimeProvider
from features.dictionary import DefineProvider
from features.emoji_search import EmojiProvider
from features.files import FileService, FilesProvider
from features.file_content import FileContentProvider
from features.notes import NotesProvider, NotesService
from features.power import supported as power_supported
from features.process_manager import ProcessProvider
from features.quick_actions import QuickActionService, QuickActionsProvider
from features.quick_connect import QuickConnectService, SSHProvider
from features.screenshots import ScreenshotProvider
from features.snippets import SnippetProvider, SnippetService
from features.system_info import SystemInfoProvider
from features.web_search import (
    GitHubProvider,
    TranslateProvider,
    WebProvider,
    WebService,
    WikipediaProvider,
    YouTubeProvider,
)
from features.window_search import WindowProvider
from features.window_manager import WindowManagerProvider
from features.workflows import WorkflowProvider, WorkflowService
from ui import dialogs, i18n
from ui.icons import IconStore, app_icon
from ui.launcher_window import LauncherWindow
from ui.themes import apply_theme

from .config_manager import ConfigManager
from .database import Database
from .hooks import UIHooks
from .hotkey_manager import HotkeyManager
from .logging_setup import get_logger
from .paths import expand_path
from .search_engine import SearchEngine
from .version import APP_NAME, APP_VERSION
from .workers import CancelToken, run_async

log = get_logger(__name__)


class SeekRApplication(QObject, UIHooks):
    """Creates services, windows and platform integrations."""

    index_progress = Signal(int, str)
    index_finished = Signal(str, dict)
    index_failed = Signal(str, str)
    _task_failed_signal = Signal(str, str, str)

    def __init__(self, app: QApplication, config: ConfigManager, db: Database):
        QObject.__init__(self)
        self._task_failed_signal.connect(self._task_failed)
        self.app = app
        self.config = config
        i18n.set_language(config)
        self.db = db
        self.icons = IconStore()
        self.launcher: Optional[LauncherWindow] = None
        self.hotkey: Optional[HotkeyManager] = None
        self.tray: Optional[QSystemTrayIcon] = None
        self._tray_menu: Optional[QMenu] = None
        self.clipboard_monitor: Optional[ClipboardMonitor] = None
        self._settings_window = None
        self._tools_window = None
        self._preview_dialog = None
        self._apps_running = False
        self._files_running = False
        self._file_token = CancelToken()
        self._shutdown_done = False
        # Keep bulk indexing serialized and low-priority so it cannot
        # compete aggressively with interactive search and painting.
        self._index_pool = QThreadPool(self)
        self._index_pool.setMaxThreadCount(1)
        self._index_pool.setThreadPriority(QThread.Priority.LowPriority)

        self._build_services()
        self.engine = SearchEngine(config, db, self, parent=self)
        self._register_providers()

    # --------------------------------------------------------------- services
    def _build_services(self) -> None:
        self.app_service = AppService(self.config, self.db)
        self.file_service = FileService(self.config, self.db)
        self.notes_service = NotesService(self.config, self.db)
        self.clipboard_service = ClipboardService(self.config, self.db)
        self.calculator_service = CalculatorService(self.config, self.db)
        self.command_service = CommandService(self.config, self.db, self)
        self.web_service = WebService(self.config, self, self.db)
        self.quick_connect_service = QuickConnectService(self.config, self.db)
        self.quick_action_service = QuickActionService(self.config, self.db, self)
        self.workflow_service = WorkflowService(self.config, self.db, self, self.command_service)
        self.snippet_service = SnippetService(self.config, self.db, self)

    def _register_providers(self) -> None:
        providers = [
            ApplicationsProvider(self.config, self.db, self, self.app_service),
            FilesProvider(self.config, self.db, self, self.file_service),
            FileContentProvider(self.config, self.db, self),
            CalculatorProvider(self.config, self.db, self, self.calculator_service),
            UnitProvider(self.config, self.db, self, self.calculator_service),
            WebProvider(self.config, self.db, self, self.web_service),
            WikipediaProvider(self.config, self.db, self, self.web_service),
            YouTubeProvider(self.config, self.db, self, self.web_service),
            GitHubProvider(self.config, self.db, self, self.web_service),
            TranslateProvider(self.config, self.db, self, self.web_service),
            DefineProvider(self.config, self.db, self),
            CommandsProvider(self.config, self.db, self, self.command_service),
            CommandChainProvider(self.config, self.db, self, self.command_service),
            ClipboardProvider(self.config, self.db, self, self.clipboard_service),
            NotesProvider(self.config, self.db, self, self.notes_service),
            SystemInfoProvider(self.config, self.db, self),
            DateTimeProvider(self.config, self.db, self),
            WindowProvider(self.config, self.db, self),
            WindowManagerProvider(self.config, self.db, self),
            EmojiProvider(self.config, self.db, self),
            ColorProvider(self.config, self.db, self),
            ScreenshotProvider(self.config, self.db, self),
            ProcessProvider(self.config, self.db, self),
            BookmarksProvider(self.config, self.db, self),
            SSHProvider(self.config, self.db, self, self.quick_connect_service),
            QuickActionsProvider(self.config, self.db, self, self.quick_action_service),
            WorkflowProvider(self.config, self.db, self, self.workflow_service),
            SnippetProvider(self.config, self.db, self, self.snippet_service),
        ]
        for provider in providers:
            self.engine.register(provider)

    # -------------------------------------------------------------------- start
    def start(self, show_window: bool = True, register_hotkey: bool = True) -> None:
        from . import startup as startup_integration

        # The registry/autostart entry is the source of truth for this switch,
        # so reconcile a stale config value (for example after moving the exe).
        try:
            actual_startup = startup_integration.is_enabled()
            if bool(self.config.get("general.start_with_windows", False)) != actual_startup:
                self.config.set("general.start_with_windows", actual_startup)
        except Exception:
            log.debug("Could not reconcile the startup setting", exc_info=True)

        apply_theme(self.app, self.config)
        self.launcher = LauncherWindow(self)
        self.index_progress.connect(self.launcher.show_progress)
        self.index_finished.connect(self._on_index_finished)
        self.index_failed.connect(self._on_index_failed)

        if register_hotkey:
            self._setup_hotkey()
        self._create_tray()
        self.quick_action_service.seed_defaults()
        self._start_clipboard_monitor()
        self._prune_data()
        self.config.subscribe(self._on_config_changed)
        self.app.aboutToQuit.connect(self.shutdown)
        # Prime the cached GPU probe so the first sys: lookup has data without
        # ever running PowerShell/WMI on the GUI thread.
        system_info.warm_up()
        run_async(warm_up_calculator)

        if show_window:
            self.launcher.show_launcher()
        QTimer.singleShot(300, self._auto_index)
        log.info("SeekR %s started", APP_VERSION)

    def _setup_hotkey(self) -> None:
        if self.hotkey is None:
            self.hotkey = HotkeyManager(self)
            self.hotkey.activated.connect(self.toggle_launcher)
            self.hotkey.failed.connect(self._on_hotkey_failed)
            self.hotkey.unavailable.connect(lambda message: log.info("Hotkey unavailable: %s", message))
        hotkey = self.config.get("general.hotkey", "Alt+Space")
        self.hotkey.register(str(hotkey))

    def _on_hotkey_failed(self, message: str) -> None:
        log.warning("Global hotkey error: %s", message)
        if self.launcher is not None:
            self.launcher.show_status(message, "warning")
        self.notify(message, "warning")

    def _create_tray(self) -> None:
        if self.tray is not None:
            return
        if not self.config.get("general.show_tray_icon", True):
            return
        if not QSystemTrayIcon.isSystemTrayAvailable():
            log.info("No system tray available")
            return
        self.tray = QSystemTrayIcon(app_icon(64), self)
        self.tray.setToolTip(f"{APP_NAME} {APP_VERSION}")
        menu = QMenu()
        # QSystemTrayIcon does not take ownership of the menu, so keep a
        # reference or Python could collect it and leave a dead tray menu.
        self._tray_menu = menu
        menu.addAction("Open SeekR", self.show_launcher)
        menu.addSeparator()
        menu.addAction("Settings…", lambda: self.open_settings("general"))
        menu.addAction("Tools…", lambda: self.open_tools())
        menu.addAction("Clipboard history…", self.open_clipboard)
        menu.addAction("Quick notes…", lambda: self.open_notes())
        menu.addSeparator()
        menu.addAction("Refresh indexes", lambda: self.refresh_indexes("all"))
        menu.addAction("Quit SeekR", self.quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.toggle_launcher()

    def apply_hotkey(self, value: str) -> tuple[bool, str]:
        """Register *value* and report whether Windows accepted it."""
        if os.name != "nt":
            return True, "Hotkey saved (global hotkeys are Windows-only)"
        if self.hotkey is None:
            self._setup_hotkey()
        if self.hotkey is None:  # pragma: no cover - defensive
            return False, "The hotkey manager could not be created"
        if self.hotkey.register(value):
            return True, f"Hotkey set to {self.hotkey.current or value}"
        return False, self.hotkey.last_error or "Windows could not register that hotkey"

    # ------------------------------------------------------------------- index
    def _auto_index(self) -> None:
        first_run = self.db.count_apps() == 0
        stale_allowed = bool(self.config.get("applications.refresh_on_start", False))
        if first_run or (stale_allowed and self.app_service.refresh_needed()):
            self.refresh_applications()
        if not self.config.get("files.enabled", True) or not self.config.get("files.auto_index", True):
            return
        last = self.db.get_meta("files_last_index")
        stale = True
        if last:
            try:
                stale = (time.time() - float(last)) > 86400
            except ValueError:
                stale = True
        if self.db.count_files() == 0 or stale:
            self.refresh_files()

    def refresh_indexes(self, which: str = "all") -> None:
        if which in {"all", "applications"}:
            self.refresh_applications()
        if which in {"all", "files"}:
            self.refresh_files()

    def refresh_applications(self) -> None:
        if self._apps_running:
            self.notify("Application indexing is already running")
            return
        self._apps_running = True
        self.index_progress.emit(0, "Indexing applications…")
        run_async(
            self.app_service.refresh,
            progress=self._emit_progress,
            on_finished=self._apps_indexed,
            on_failed=lambda message, tb: self._task_failed_signal.emit("applications", message, tb),
            on_cleanup=self.db.close_thread_connection,
            pool=self._index_pool,
        )

    def _apps_indexed(self, stats: dict) -> None:
        self._apps_running = False
        found = int(stats.get("found", 0)) if isinstance(stats, dict) else 0
        self.index_finished.emit("applications", stats if isinstance(stats, dict) else {})
        self.notify(f"Applications indexed: {found}")

    def refresh_files(self) -> None:
        if self._files_running:
            self.notify("File indexing is already running")
            return
        self._files_running = True
        self._file_token = CancelToken()
        self.index_progress.emit(0, "Indexing files…")
        run_async(
            self.file_service.index,
            progress=self._emit_progress,
            token=self._file_token,
            on_finished=self._files_indexed,
            on_failed=lambda message, tb: self._task_failed_signal.emit("files", message, tb),
            on_cleanup=self.db.close_thread_connection,
            pool=self._index_pool,
        )

    def cancel_file_index(self) -> None:
        """Ask the running file indexer to stop."""
        self._file_token.cancel()

    def _files_indexed(self, stats: dict) -> None:
        self._files_running = False
        indexed = int(stats.get("indexed", 0)) if isinstance(stats, dict) else 0
        self.index_finished.emit("files", stats if isinstance(stats, dict) else {})
        if isinstance(stats, dict) and stats.get("cancelled"):
            self.notify(f"File indexing stopped after {indexed} items")
        else:
            self.notify(f"Files indexed: {indexed}")

    def _emit_progress(self, percent: int, message: str) -> None:
        self.index_progress.emit(percent, message)

    def _on_index_finished(self, kind: str, stats: dict) -> None:
        if self.launcher is not None:
            self.launcher.show_status(f"Index updated ({kind})")

    def _on_index_failed(self, message: str, _traceback: str) -> None:
        self.notify(f"Indexing failed: {message}", "error")

    def _task_failed(self, kind: str, message: str, traceback_text: str) -> None:
        if kind == "applications":
            self._apps_running = False
        if kind == "files":
            self._files_running = False
        log.error("%s indexing failed: %s\n%s", kind, message, traceback_text)
        self.index_failed.emit(message, traceback_text)
        self.notify(f"{kind.title()} indexing failed: {message}", "error")

    # ---------------------------------------------------------------- clipboard
    def _start_clipboard_monitor(self) -> None:
        if not self.clipboard_service.enabled:
            return
        if self.clipboard_monitor is None:
            self.clipboard_monitor = ClipboardMonitor(self.clipboard_service, self)
        if not self.clipboard_monitor.start():
            log.info("Clipboard monitoring could not start on this platform")

    def _stop_clipboard_monitor(self) -> None:
        if self.clipboard_monitor is not None:
            self.clipboard_monitor.stop()

    def _prune_data(self) -> None:
        try:
            self.db.prune_history(int(self.config.get("privacy.retention_days", 90) or 90))
            self.db.prune_clipboard(int(self.config.get("clipboard.limit", 200) or 200))
        except Exception:
            log.exception("Could not prune stored data")

    # ------------------------------------------------------------------ config
    def _on_config_changed(self, path: str, _value: Any) -> None:
        if path == "*" or path.startswith("general.language"):
            i18n.set_language(self.config)
        if path == "*" and self.launcher is not None:
            self.launcher.launcher_widgets.refresh_settings(animate=False)
        if path == "*" or path.startswith("appearance.") or path.startswith("general.language"):
            apply_theme(self.app, self.config)
            if self.launcher is not None:
                self.launcher.refresh_texts()
                # Repaint/re-measure without reopening the launcher: reopening
                # would clear the query while the user drags a slider.
                self.launcher.refresh_appearance()
            if path.startswith("general.language") and self._tools_window is not None:
                self._tools_window.refresh_texts()
            if path.startswith("general.language") and self._settings_window is not None:
                self._settings_window.refresh_texts()
        if path in {"general.hotkey", "*"} and self.hotkey is not None:
            self.hotkey.register(str(self.config.get("general.hotkey", "Alt+Space")))
        if path in {"clipboard.enabled", "privacy.clipboard_history", "clipboard.poll_interval_ms", "*"}:
            self._stop_clipboard_monitor()
            self.clipboard_monitor = None
            self._start_clipboard_monitor()
        if path in {"general.show_tray_icon", "*"}:
            wanted = bool(self.config.get("general.show_tray_icon", True))
            if wanted and self.tray is None:
                # The tray may have been disabled at startup; create it on demand
                # instead of leaving the setting silently broken.
                self._create_tray()
            elif self.tray is not None:
                self.tray.setVisible(wanted)

    # -------------------------------------------------------------------- hooks
    def _dialog_parent(self):
        if self.launcher is not None and self.launcher.isVisible():
            return self.launcher
        if self._settings_window is not None and self._settings_window.isVisible():
            return self._settings_window
        if self._tools_window is not None and self._tools_window.isVisible():
            return self._tools_window
        return None

    def open_path(self, path: str) -> bool:
        ok, message = util.open_path_platform(path)
        self.notify(message, "info" if ok else "error")
        return ok

    def reveal_path(self, path: str) -> bool:
        ok, message = util.reveal_path_platform(path)
        if not ok:
            self.notify(message, "error")
        return ok

    def open_url(self, url: str) -> bool:
        if not url:
            return False
        opened = QDesktopServices.openUrl(QUrl(url))
        if not opened:
            self.notify(f"Could not open {url}", "error")
        return opened

    def copy_text(self, text: str) -> bool:
        clipboard = QGuiApplication.clipboard()
        if clipboard is None:
            return False
        clipboard.setText(text or "")
        return True

    def show_info(self, title: str, text: str) -> None:
        if len(text) > 700:
            dialog = dialogs.TextDialog(title, text, self._dialog_parent())
            dialog.exec()
        else:
            dialogs.show_info(self._dialog_parent(), title, text)

    def show_error(self, title: str, text: str) -> None:
        dialogs.show_error(self._dialog_parent(), title, text)

    def confirm(self, title: str, message: str) -> bool:
        return dialogs.ask_confirm(self._dialog_parent(), title, message)

    def notify(self, message: str, level: str = "info") -> None:
        log.log(40 if level == "error" else 20, "Notify: %s", message)
        if self.launcher is not None:
            self.launcher.show_status(message, level)
        if self.tray is not None and (self.launcher is None or not self.launcher.isVisible()):
            icon = QSystemTrayIcon.MessageIcon.Warning if level in {"error", "warning"} else QSystemTrayIcon.MessageIcon.Information
            try:
                self.tray.showMessage(APP_NAME, message, icon, 4000)
            except Exception:
                pass

    def open_settings(self, page: Optional[str] = None) -> None:
        from ui.settings_window import SettingsWindow

        if self._settings_window is None:
            self._settings_window = SettingsWindow(self)
        self._settings_window.open_page(page)
        self._settings_window.show()
        self._settings_window.raise_()
        self._settings_window.activateWindow()

    def open_tools(self, tab: Optional[str] = None) -> None:
        from ui.tools_window import ToolsWindow

        if self._tools_window is None:
            self._tools_window = ToolsWindow(self)
        self._tools_window.open_page(tab)
        self._tools_window.show()
        self._tools_window.raise_()
        self._tools_window.activateWindow()

    def open_clipboard(self) -> None:
        self.open_tools("clipboard")

    def open_notes(self, note_id: Optional[int] = None) -> None:
        self.open_tools("notes")
        if note_id is not None and self._tools_window is not None:
            self._tools_window.select_note(note_id)

    def open_tool_window(self, name: str) -> None:
        self.open_tools(name)

    def lookup_definition(self, word: str) -> None:
        self.open_tools("dictionary")
        if self._tools_window is not None:
            self._tools_window.lookup_definition(word)

    def preview(self, path: str) -> None:
        dialog = dialogs.QuickLookDialog(path, self._dialog_parent())
        self._preview_dialog = dialog
        dialog.exec()
        self._preview_dialog = None

    def fill_query(self, text: str) -> None:
        if self.launcher is None:
            self.launcher = LauncherWindow(self)
        self.launcher.set_query(text)

    def hide_launcher(self) -> None:
        if self.launcher is not None:
            self.launcher.hide_launcher()

    def show_launcher(self) -> None:
        """Raise the launcher for the hotkey, the tray or a second instance."""
        if self.launcher is None:
            # No event-loop work runs between the single-instance socket being
            # opened and this slot being connected, so this is a diagnostic
            # guard rather than the normal path. Log it instead of dropping a
            # user-visible activation request silently.
            log.warning("Show requested before the launcher was created; request dropped")
            return
        self.launcher.show_launcher()

    def toggle_launcher(self) -> None:
        if self.launcher is not None:
            self.launcher.toggle()

    def open_connection(self, profile: dict) -> None:
        ok, message = self.quick_connect_service.connect(profile)
        self.notify(message, "info" if ok else "error")

    def power_supported(self) -> bool:
        return power_supported()

    # -------------------------------------------------------------------- exit
    def quit(self) -> None:
        # ``QCoreApplication.quit()`` is documented as "the same as exit(0)",
        # but it is a no-op once the application state it guards has been
        # touched: with this controller running, ``app.quit()`` left the event
        # loop running at every delay from 100 ms to 3 s, so the tray's Quit
        # action did nothing. ``exit(0)`` is the primitive and always stops the
        # loop, so call it directly.
        self.app.exit(0)

    def shutdown(self) -> None:
        if self._shutdown_done:
            return
        self._shutdown_done = True
        log.info("Shutting down SeekR")
        self._file_token.cancel()
        try:
            self._stop_clipboard_monitor()
        except Exception:
            log.exception("Clipboard monitor shutdown failed")
        if self.hotkey is not None:
            self.hotkey.cleanup()
        if self.tray is not None:
            self.tray.hide()
        try:
            self.db.close()
        except Exception:
            log.exception("Database shutdown failed")


__all__ = ["SeekRApplication"]
