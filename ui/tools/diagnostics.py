"""User-controlled local diagnostic report export."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QCheckBox, QFileDialog, QVBoxLayout, QWidget

from features.diagnostics import build_diagnostic_report
from ui.components import SectionCard, label, primary_button


class DiagnosticsTab(QWidget):
    """Export a diagnostic report only after an explicit user action."""

    def __init__(self, controller, window):
        super().__init__()
        self.controller = controller
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        layout.addWidget(label("Diagnostics", "Heading"))
        card = SectionCard(
            "Local diagnostic report",
            "Create a report you can inspect before choosing whether to share it.",
        )
        card.add_widget(label(
            "The default report contains only application/runtime versions and platform details. "
            "It never includes clipboard contents, notes, indexed file lists, or search history.",
            "Muted", wrap=True,
        ))
        self.include_logs = QCheckBox("Include recent application logs (best-effort redaction)")
        self.include_logs.setChecked(False)
        card.add_widget(self.include_logs)
        card.add_widget(label(
            "Logs can contain personal information. SeekR redacts common paths, email addresses, IP addresses, "
            "quoted search text, and secret-shaped values, but redaction is not guaranteed. Review the saved file "
            "before sharing it. Reports are saved locally; SeekR never uploads them.",
            "Muted", wrap=True,
        ))
        card.add_widget(primary_button("Export diagnostic report…", self.export_report))
        self.status = label("", "Muted", wrap=True)
        card.add_widget(self.status)
        layout.addWidget(card)
        layout.addStretch(1)

    def export_report(self) -> None:
        path, _selected = QFileDialog.getSaveFileName(
            self,
            "Export SeekR diagnostic report",
            str(Path.home() / "SeekR-diagnostics.txt"),
            "Text files (*.txt)",
        )
        if not path:
            return
        try:
            report = build_diagnostic_report(include_logs=self.include_logs.isChecked())
            Path(path).expanduser().write_text(report, encoding="utf-8")
        except OSError as exc:
            self.status.setText("Could not save the report: " + str(exc))
            return
        self.status.setText("Diagnostic report saved. Review it before sharing.")


__all__ = ["DiagnosticsTab"]
