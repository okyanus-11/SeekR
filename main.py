"""SeekR entry point."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Optional

from PySide6.QtCore import Qt, QTimer
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
    parser.add_argument("--verify-ui", action="store_true", help="Show the launcher, verify all enabled widgets render, then exit")
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
        show_window=not args.hidden and not start_minimized and not args.verify_ui,
        register_hotkey=not args.no_hotkey,
    )
    if args.settings:
        controller.open_settings("general")
    if args.tools:
        controller.open_tools()

    if args.verify_ui:
        # Used by CI against the packaged portable and installed executables.
        # This exercises the real application entry point, Qt layout, widget
        # ownership and visible geometry rather than merely importing modules.
        def verify_launcher_widgets() -> None:
            launcher = controller.launcher
            widgets = launcher.launcher_widgets if launcher is not None else None
            failures = []
            if launcher is None or not launcher.isVisible():
                failures.append("launcher window is not visible")
            if widgets is None:
                failures.append("launcher widget coordinator is missing")
            else:
                if not widgets.left_column.isVisible():
                    failures.append("left widget rail is not visible")
                if not widgets.right_column.isVisible():
                    failures.append("right widget rail is not visible")
                for name, card in widgets._cards.items():
                    if not bool(config.get(f"widgets.{name}_enabled", True)):
                        continue
                    if not card.isVisible():
                        failures.append(f"{name} widget is not visible after delayed repaint")
                    if card.width() <= 0 or card.height() <= 0:
                        failures.append(f"{name} widget has empty geometry")
                    if card.graphicsEffect() is not None:
                        failures.append(f"{name} widget unexpectedly has an opacity/graphics effect")
                    snapshot = card.grab()
                    if snapshot.isNull() or snapshot.width() <= 0 or snapshot.height() <= 0:
                        failures.append(f"{name} widget produced an empty render snapshot")
                for name in ("clock", "system", "weather", "meme", "media"):
                    if not bool(config.get(f"widgets.{name}_enabled", True)):
                        continue
                    card = widgets._cards[name]
                    timer = getattr(card, "timer", None) or getattr(card, "day_timer", None)
                    if timer is None or not timer.isActive():
                        failures.append(f"{name} widget refresh timer is not active")
                if widgets.clock.time_label.text() == initial_clock_text:
                    failures.append("clock widget did not update during the delayed visibility check")
            if failures:
                log.error("UI_SMOKE_FAIL: %s", "; ".join(failures))
                app.exit(3)
            else:
                log.info("UI_SMOKE_OK: all enabled widgets remained visible, rendered and live after delayed repaint")
                app.exit(0)

        initial_clock_text = controller.launcher.launcher_widgets.clock.time_label.text()
        controller.show_launcher()
        QTimer.singleShot(2200, verify_launcher_widgets)

    exit_code = app.exec()
    if instance is not None:
        instance.close()
    log.info("SeekR exited with code %s", exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
