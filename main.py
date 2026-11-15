"""SeekR entry point."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from core.application import SeekRApplication
from core.config_manager import ConfigManager
from core.database import Database
from core.errors import install_excepthook
from core.logging_setup import get_logger, setup_logging
from core.paths import ensure_app_dirs
from core.single_instance import SingleInstance
from core.version import APP_DESCRIPTION, APP_NAME, APP_VERSION
from ui.icons import app_icon


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="SeekR",
        description=f"{APP_NAME} {APP_VERSION} — {APP_DESCRIPTION}",
    )
    parser.add_argument("--version", action="store_true", help="Print the version and exit")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--no-hotkey", action="store_true", help="Do not register the global hotkey")
    parser.add_argument("--hidden", action="store_true", help="Start without showing the launcher")
    parser.add_argument("--settings", action="store_true", help="Open the settings window on start")
    parser.add_argument("--tools", action="store_true", help="Open the tools window on start")
    parser.add_argument("--reset-config", action="store_true", help="Reset the configuration to defaults")
    parser.add_argument(
        "--allow-multiple",
        action="store_true",
        help="Ignore the single-instance check (useful for development)",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.version:
        print(f"{APP_NAME} {APP_VERSION}")
        return 0

    ensure_app_dirs()
    config = ConfigManager()
    if args.reset_config and not config.reset():
        print("Could not reset the configuration file", file=sys.stderr)
    setup_logging(debug=args.debug or bool(config.get("advanced.debug", False)))
    log = get_logger("seekr.main")
    log.info("Starting %s %s on %s", APP_NAME, APP_VERSION, sys.platform)

    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Okyanus.SeekR.1")
        except Exception:
            log.debug("Could not set the AppUserModelID", exc_info=True)

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(APP_NAME)
    app.setDesktopFileName("SeekR")
    app.setWindowIcon(app_icon(256))
    app.setQuitOnLastWindowClosed(False)

    database = Database()
    controller: Optional[SeekRApplication] = None

    def report_unexpected(summary: str, _traceback_text: str) -> None:
        if controller is not None:
            controller.show_error("Unexpected error", summary)

    install_excepthook(report_unexpected)

    instance: Optional[SingleInstance] = None
    if config.get("advanced.single_instance", True) and not args.allow_multiple:
        instance = SingleInstance()
        if instance.notify_existing():
            log.info("SeekR is already running; asked the existing instance to show")
            return 0
        instance.listen()

    controller = SeekRApplication(app, config, database)
    if instance is not None:

        def show_from_other_instance() -> None:
            # Logged in the primary so a Windows validation run can tell a
            # forwarded request apart from one the window never honoured.
            log.info("Show request received from another instance")
            controller.show_launcher()

        instance.show_requested.connect(show_from_other_instance)

    start_minimized = bool(config.get("general.start_minimized", False))
    controller.start(
        show_window=not args.hidden and not start_minimized,
        register_hotkey=not args.no_hotkey,
    )
    if args.settings:
        controller.open_settings("general")
    if args.tools:
        controller.open_tools()

    exit_code = app.exec()
    if instance is not None:
        instance.close()
    log.info("SeekR exited with code %s", exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
