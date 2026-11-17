"""System, processes, power and screenshots pages."""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.logging_setup import get_logger
from features import power, process_manager, screenshots, system_info, util
from ui import dialogs, i18n
from ui.components import (
    ScrollPage,
    SectionCard,
    danger_button,
    label,
    primary_button,
    secondary_button,
)

log = get_logger(__name__)


class SystemTab(ScrollPage):
    """Live system information refreshed from the OS."""

    def __init__(self, controller, window):
        super().__init__()
        self.controller = controller
        self.layout.addWidget(label("System information", "Heading"))
        top = QHBoxLayout()
        top.addWidget(label("Values come straight from the operating system and refresh every two seconds.", "Muted", wrap=True), 1)
        top.addWidget(primary_button("Refresh now", self.refresh))
        holder = QWidget()
        holder.setLayout(top)
        self.layout.addWidget(holder)

        self.cards: dict[str, QLabel] = {}
        for key, title, subtitle in (
            ("cpu", "Processor", "Usage, cores and clock speed"),
            ("memory", "Memory", "Physical and swap usage"),
            ("disk", "Storage", "Volumes and free space"),
            ("gpu", "Graphics", "Detected GPUs and utilisation where available"),
            ("battery", "Battery", "Charge level and state"),
            ("network", "Network", "Hostname, addresses and interfaces"),
            ("uptime", "Uptime", "Time since the system started"),
            ("os", "Operating system", "Platform and runtime details"),
        ):
            card = SectionCard(title, subtitle)
            value = label("—", "Muted", wrap=True)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            card.add_widget(value)
            self.layout.addWidget(card)
            self.cards[key] = value

        self.layout.addStretch(1)
        self.timer = QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self.refresh)
        self.refresh()

    def showEvent(self, event) -> None:  # noqa: N802
        self.timer.start()
        self.refresh()
        super().showEvent(event)

    def hideEvent(self, event) -> None:  # noqa: N802
        self.timer.stop()
        super().hideEvent(event)

    def refresh(self) -> None:
        try:
            data = system_info.snapshot()
        except Exception as exc:  # pragma: no cover - defensive
            log.exception("System snapshot failed")
            self.cards["cpu"].setText(f"Could not read system information: {exc}")
            return

        cpu = data["cpu"]
        if cpu.get("percent") is not None:
            frequency = f"{cpu['frequency_mhz']:.0f} MHz" if cpu.get("frequency_mhz") else "unknown clock"
            self.cards["cpu"].setText(
                f"{cpu['percent']:.1f}% in use  ·  {cpu.get('logical') or '?'} logical / {cpu.get('physical') or '?'} physical cores  ·  {frequency}"
            )
        else:
            self.cards["cpu"].setText("Unavailable")

        memory = data["memory"]
        if memory.get("total"):
            swap = (
                f"  ·  swap {util.format_bytes(memory.get('swap_used'))} / {util.format_bytes(memory.get('swap_total'))}"
                if memory.get("swap_total")
                else ""
            )
            self.cards["memory"].setText(
                f"{util.format_bytes(memory['used'])} used of {util.format_bytes(memory['total'])} "
                f"({memory['percent']:.1f}%)  ·  {util.format_bytes(memory['available'])} available{swap}"
            )
        else:
            self.cards["memory"].setText("Unavailable")

        disks = data["disks"]
        if disks:
            lines = [
                f"{disk['mountpoint']} ({disk['fstype']}): {util.format_bytes(disk['used'])} used of "
                f"{util.format_bytes(disk['total'])} — {disk['percent']:.0f}%"
                for disk in disks
            ]
            self.cards["disk"].setText("\n".join(lines))
        else:
            self.cards["disk"].setText("No volumes reported")

        gpus = data["gpu"]
        if gpus:
            lines = []
            for gpu in gpus:
                parts = [gpu["name"]]
                if gpu.get("utilization") is not None:
                    parts.append(f"{gpu['utilization']:.0f}% GPU")
                if gpu.get("memory_total"):
                    parts.append(f"{util.format_bytes(gpu['memory_total'])} memory")
                if gpu.get("driver"):
                    parts.append(f"driver {gpu['driver']}")
                lines.append("  ·  ".join(parts))
            self.cards["gpu"].setText("\n".join(lines))
        else:
            self.cards["gpu"].setText("No GPU information available")

        battery = data["battery"]
        if battery:
            state = "plugged in" if battery["plugged"] else "on battery"
            remaining = (
                f"  ·  {util.format_duration(battery['seconds_left'])} remaining"
                if battery.get("seconds_left")
                else ""
            )
            self.cards["battery"].setText(f"{battery['percent']:.0f}%  ·  {state}{remaining}")
        else:
            self.cards["battery"].setText("No battery detected")

        network = data["network"]
        lines = [f"Host {network.get('hostname') or 'unknown'}"]
        if network.get("ip"):
            lines.append(f"Primary address {network['ip']}")
        for interface in network.get("interfaces", []):
            addresses = ", ".join(interface["addresses"]) or "no IPv4 address"
            lines.append(f"{interface['name']}: {addresses}  ·  {interface['speed']} Mb/s")
        self.cards["network"].setText("\n".join(lines) if lines else "Unavailable")

        uptime = data["uptime"]
        if uptime is not None:
            started = dt.datetime.fromtimestamp(data["os"]["boot_time"]).strftime("%Y-%m-%d %H:%M")
            self.cards["uptime"].setText(f"{util.format_duration(uptime)}  ·  started {started}")
        else:
            self.cards["uptime"].setText("Unavailable")

        os_data = data["os"]
        self.cards["os"].setText(
            f"{os_data['system']} {os_data['release']} (build {os_data['version']})\n"
            f"{os_data['machine']}  ·  {os_data['processor'] or 'unknown processor'}  ·  Python {os_data['python']}"
        )


class ProcessesTab(QWidget):
    """Running processes with termination controls."""

    def __init__(self, controller, window):
        super().__init__()
        self.controller = controller
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        layout.addWidget(label("Processes", "Heading"))
        layout.addWidget(
            label(
                "Live CPU and memory figures. Terminating a process can lose unsaved work; SeekR asks first.",
                "Muted",
                wrap=True,
            )
        )

        controls = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter by process name…")
        self.search.textChanged.connect(self._apply_filter)
        controls.addWidget(self.search, 1)
        self.auto_refresh = QCheckBox("Auto refresh")
        self.auto_refresh.setChecked(True)
        self.auto_refresh.toggled.connect(self._toggle_timer)
        controls.addWidget(self.auto_refresh)
        controls.addWidget(primary_button("Refresh", self.refresh))
        layout.addLayout(controls)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["PID", "Name", "CPU %", "Memory", "User", "Status"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        buttons.addWidget(danger_button("Terminate process…", lambda: self._terminate(False)))
        buttons.addWidget(danger_button("Force kill…", lambda: self._terminate(True)))
        buttons.addWidget(secondary_button("Details", self._details))
        buttons.addWidget(secondary_button("Copy PID", self._copy_pid))
        buttons.addStretch(1)
        self.status = label("", "Muted")
        buttons.addWidget(self.status)
        layout.addLayout(buttons)

        self._processes: list[dict] = []
        self.timer = QTimer(self)
        self.timer.setInterval(5000)
        self.timer.timeout.connect(self.refresh)
        self.refresh()

    def showEvent(self, event) -> None:  # noqa: N802
        self.refresh()
        self._toggle_timer(self.auto_refresh.isChecked())
        super().showEvent(event)

    def hideEvent(self, event) -> None:  # noqa: N802
        self.timer.stop()
        super().hideEvent(event)

    def _toggle_timer(self, enabled: bool) -> None:
        if enabled and self.isVisible():
            self.timer.start()
        else:
            self.timer.stop()

    def refresh(self) -> None:
        selected = self._selected_pid()
        try:
            self._processes = process_manager.list_processes()
        except Exception as exc:  # pragma: no cover - defensive
            log.exception("Could not list processes")
            self.status.setText(f"Could not list processes: {exc}")
            return
        self._populate(selected)
        self.status.setText(f"{len(self._processes)} processes")

    def _populate(self, selected_pid: Optional[int] = None) -> None:
        query = self.search.text().strip().lower()
        rows = [
            process
            for process in self._processes
            if not query or query in process["name"].lower()
        ][:400]
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        for process in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = [
                str(process["pid"]),
                process["name"],
                f"{process['cpu']:.1f}",
                util.format_bytes(process["memory"]),
                process["user"] or "—",
                process["status"] or "—",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, process["pid"])
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if column == 2:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, column, item)
            if selected_pid is not None and process["pid"] == selected_pid:
                self.table.selectRow(row)
        self.table.setSortingEnabled(True)

    def _apply_filter(self, _text: str) -> None:
        self._populate(self._selected_pid())

    def _selected_pid(self) -> Optional[int]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return int(value) if value is not None else None

    def _copy_pid(self) -> None:
        pid = self._selected_pid()
        if pid is not None:
            self.controller.copy_text(str(pid))
            self.status.setText(f"Copied PID {pid}")

    def _terminate(self, force: bool) -> None:
        pid = self._selected_pid()
        if pid is None:
            self.status.setText("Select a process first")
            return
        name = next((process["name"] for process in self._processes if process["pid"] == pid), f"PID {pid}")
        action = "Force kill" if force else "Terminate"
        if not dialogs.ask_confirm(
            self,
            f"{action} {name}?",
            f"PID {pid} will be {'killed immediately' if force else 'asked to close'}.\nUnsaved work may be lost.",
        ):
            return
        if force:
            import psutil

            try:
                psutil.Process(pid).kill()
                ok, message = True, f"Killed {name}"
            except Exception as exc:
                ok, message = False, str(exc)
        else:
            ok, message = process_manager.terminate_process(pid)
        self.status.setText(message)
        if not ok:
            self.controller.show_error("Process", message)
        self.refresh()

    def _details(self) -> None:
        pid = self._selected_pid()
        if pid is None:
            self.status.setText("Select a process first")
            return
        details = process_manager.process_details(pid)
        if details is None:
            self.controller.show_error("Process details", "This process is no longer running or access was denied.")
            return
        text = "\n".join(
            [
                f"Name: {details['name']}",
                f"PID: {details['pid']}",
                f"Executable: {details['exe'] or 'unavailable'}",
                f"User: {details['user']}",
                f"Status: {details['status']}",
                f"CPU: {details['cpu']:.1f}%",
                f"Memory: {util.format_bytes(details['memory'])}",
                f"Threads: {details['threads']}",
                f"Started: {dt.datetime.fromtimestamp(details['created']).strftime('%Y-%m-%d %H:%M:%S')}",
                f"Command line: {' '.join(details['cmdline']) or 'unavailable'}",
            ]
        )
        dialogs.TextDialog(f"Process {pid}", text, self).exec()

    def on_show(self) -> None:
        self.refresh()


class PowerTab(QWidget):
    """Switch Windows power schemes or Linux power profiles."""

    def __init__(self, controller, window):
        super().__init__()
        self.controller = controller
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        layout.addWidget(label("Power profiles", "Heading"))
        self.hint = label("", "Muted", wrap=True)
        layout.addWidget(self.hint)
        self.list = QListWidget()
        self.list.setObjectName("PlainList")
        layout.addWidget(self.list, 1)
        buttons = QHBoxLayout()
        buttons.addWidget(primary_button("Apply selected profile", self._apply))
        buttons.addWidget(secondary_button("Refresh", self.refresh))
        buttons.addStretch(1)
        self.status = label("", "Muted")
        buttons.addWidget(self.status)
        layout.addLayout(buttons)
        self.refresh()

    def refresh(self) -> None:
        self.list.clear()
        self._schemes = []
        if not power.supported():
            self.hint.setText(
                "Power profile switching is available on Windows (powercfg) and on Linux systems with power-profiles-daemon."
            )
            self.status.setText("Unsupported on this system")
            return
        self.hint.setText("The active profile is marked with a check mark.")
        try:
            self._schemes = power.list_schemes()
        except Exception as exc:  # pragma: no cover - defensive
            self.status.setText(f"Could not read power profiles: {exc}")
            return
        for scheme in self._schemes:
            item = QListWidgetItem(f"{'✔  ' if scheme['active'] else '    '}{scheme['name']}")
            item.setData(Qt.ItemDataRole.UserRole, scheme["id"])
            if scheme["active"]:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            self.list.addItem(item)
        self.status.setText(f"{len(self._schemes)} profiles available")

    def _apply(self) -> None:
        item = self.list.currentItem()
        if item is None:
            self.status.setText("Select a profile first")
            return
        identifier = item.data(Qt.ItemDataRole.UserRole)
        ok, message = power.set_scheme(str(identifier))
        self.status.setText(message)
        if not ok:
            self.controller.show_error("Power profile", message)
        self.refresh()

    def on_show(self) -> None:
        self.refresh()


class RegionCaptureOverlay(QWidget):
    """Desktop-wide translucent overlay for selecting a screenshot region."""

    selected = Signal(QRect)
    cancelled = Signal()

    def __init__(self, geometry: QRect):
        super().__init__()
        self._origin = None
        self._selection = QRect()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(geometry)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 105))
        painter.setPen(QColor("#ffffff"))
        painter.drawText(20, 34, i18n.translate_text("Drag to select a region · Esc to cancel"))
        if not self._selection.isNull():
            painter.fillRect(self._selection, QColor(104, 169, 255, 45))
            painter.setPen(QPen(QColor("#68a9ff"), 2))
            painter.drawRect(self._selection)
        painter.end()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._origin = event.position().toPoint()
            self._selection = QRect(self._origin, self._origin)
            self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._origin is not None:
            self._selection = QRect(self._origin, event.position().toPoint()).normalized()
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton or self._origin is None:
            return
        rect = QRect(self._origin, event.position().toPoint()).normalized().intersected(self.rect())
        self._origin = None
        self.close()
        if rect.width() >= 2 and rect.height() >= 2:
            self.selected.emit(rect)
        else:
            self.cancelled.emit()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            self.cancelled.emit()
            return
        super().keyPressEvent(event)


class ScreenshotsTab(QWidget):
    """Capture the screen, preview it and save it."""

    def __init__(self, controller, window):
        super().__init__()
        self.controller = controller
        self.config = controller.config
        self._pixmap: Optional[QPixmap] = None
        self._last_path = ""
        self._region_overlay = None
        self._region_restore_window = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        layout.addWidget(label("Screenshots", "Heading"))
        layout.addWidget(
            label(
                f"Screenshots are saved to {screenshots.screenshot_directory(self.config)}.",
                "Muted",
                wrap=True,
            )
        )
        self.preview = QLabel("No screenshot captured yet")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(320)
        self.preview.setStyleSheet("background: rgba(128,128,128,0.12); border-radius: 12px;")
        layout.addWidget(self.preview, 1)
        buttons = QHBoxLayout()
        buttons.addWidget(primary_button("Capture screen", self._capture))
        buttons.addWidget(secondary_button("Capture region", self._capture_region))
        buttons.addWidget(secondary_button("Save as…", self._save_as))
        buttons.addWidget(secondary_button("Open screenshots folder", self._open_folder))
        if os.name == "nt":
            buttons.addWidget(secondary_button("Open Snipping Tool", self._snipping))
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.status = label("", "Muted", wrap=True)
        layout.addWidget(self.status)

    def _capture(self) -> None:
        try:
            self._pixmap = screenshots.capture_screen()
        except screenshots.ScreenshotError as exc:
            self.status.setText(str(exc))
            self.controller.show_error("Screenshot", str(exc))
            return
        self._show_pixmap(self._pixmap)
        self.status.setText(f"Captured {self._pixmap.width()}×{self._pixmap.height()} pixels")

    def _capture_region(self) -> None:
        self._region_restore_window = self.window()
        self._region_restore_window.hide()
        QTimer.singleShot(180, self._begin_region_capture)

    def _begin_region_capture(self) -> None:
        try:
            self._pixmap = screenshots.capture_screen()
        except screenshots.ScreenshotError as exc:
            self._restore_region_window()
            self.status.setText(str(exc))
            self.controller.show_error("Screenshot", str(exc))
            return
        screens = QGuiApplication.screens()
        if not screens:
            self._restore_region_window()
            self.status.setText("No display is available for region capture")
            return
        bounds = screens[0].geometry()
        for screen in screens[1:]:
            bounds = bounds.united(screen.geometry())
        overlay = RegionCaptureOverlay(bounds)
        overlay.selected.connect(self._save_region)
        overlay.cancelled.connect(self._region_cancelled)
        self._region_overlay = overlay

    def _restore_region_window(self) -> None:
        window = self._region_restore_window
        self._region_restore_window = None
        if window is not None:
            window.show()
            window.raise_()
            window.activateWindow()

    def _save_region(self, rect: QRect) -> None:
        if self._pixmap is None:
            self._restore_region_window()
            return
        cropped = self._pixmap.copy(rect)
        ok, path, error = screenshots.save_pixmap(self.config, cropped)
        self._region_overlay = None
        self._restore_region_window()
        if not ok:
            self.status.setText(error)
            self.controller.show_error("Screenshot", error)
            return
        self._pixmap = cropped
        self._last_path = path
        self._show_pixmap(cropped)
        self.status.setText(f"Region saved to {path}")
        self.controller.copy_text(path)

    def _region_cancelled(self) -> None:
        self._region_overlay = None
        self._restore_region_window()
        self.status.setText("Region capture cancelled")

    def _show_pixmap(self, pixmap: QPixmap) -> None:
        scaled = pixmap.scaled(
            max(320, self.preview.width() - 20),
            max(240, self.preview.height() - 20),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview.setPixmap(scaled)

    def _save_as(self) -> None:
        if self._pixmap is None:
            self.status.setText("Capture a screenshot first")
            return
        directory = screenshots.screenshot_directory(self.config)
        suggested = str(directory / f"SeekR_{dt.datetime.now():%Y-%m-%d_%H-%M-%S}.png")
        path, _ = QFileDialog.getSaveFileName(self, "Save screenshot", suggested, "PNG image (*.png)")
        if not path:
            return
        if self._pixmap.save(path, "PNG"):
            self._last_path = path
            self.status.setText(f"Saved to {path}")
            self.controller.copy_text(path)
        else:
            self.controller.show_error("Screenshot", f"Could not write {path}")

    def _open_folder(self) -> None:
        self.controller.open_path(str(screenshots.screenshot_directory(self.config)))

    def _snipping(self) -> None:
        ok, message = screenshots.open_snipping_tool()
        if not ok:
            self.controller.show_error("Snipping Tool", message)
        else:
            self.status.setText("Snipping overlay opened; the saved file appears in the folder above")

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._pixmap is not None:
            self._show_pixmap(self._pixmap)


__all__ = ["SystemTab", "ProcessesTab", "PowerTab", "ScreenshotsTab"]
