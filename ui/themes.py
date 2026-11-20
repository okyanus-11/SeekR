"""Theme palettes and application stylesheet."""

from __future__ import annotations

from typing import Any

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from core.config_manager import ConfigManager

THEMES: dict[str, dict[str, str]] = {
    "dark": {
        "window": "#10151d",
        "window_alt": "#141b24",
        "surface": "#19222d",
        "surface_alt": "#202b38",
        "surface_hover": "#2a3746",
        "border": "#2c3948",
        "text": "#edf3f8",
        "muted": "#9aabba",
        "accent": "#68a9ff",
        "accent_text": "#10151d",
        "danger": "#e87979",
        "success": "#58c99a",
        "warning": "#e8bd78",
    },
    "light": {
        "window": "#f4f5f9",
        "window_alt": "#ffffff",
        "surface": "#ffffff",
        "surface_alt": "#f0f2f7",
        "surface_hover": "#e7eaf3",
        "border": "#d8dce7",
        "text": "#1b1f27",
        "muted": "#5f6b7d",
        "accent": "#326fd1",
        "accent_text": "#ffffff",
        "danger": "#d33d3a",
        "success": "#1f9d63",
        "warning": "#b97b12",
    },
    "amoled": {
        "window": "#000000",
        "window_alt": "#070809",
        "surface": "#0b0c0e",
        "surface_alt": "#121316",
        "surface_hover": "#1a1c20",
        "border": "#22252a",
        "text": "#f5f7fa",
        "muted": "#8b919c",
        "accent": "#68a9ff",
        "accent_text": "#ffffff",
        "danger": "#ff5c5c",
        "success": "#3ddc97",
        "warning": "#ffc857",
    },
    "catppuccin_mocha": {
        "window": "#1e1e2e",
        "window_alt": "#181825",
        "surface": "#252538",
        "surface_alt": "#313244",
        "surface_hover": "#3a3a52",
        "border": "#45475a",
        "text": "#cdd6f4",
        "muted": "#a6adc8",
        "accent": "#cba6f7",
        "accent_text": "#1e1e2e",
        "danger": "#f38ba8",
        "success": "#a6e3a1",
        "warning": "#f9e2af",
    },
    "dracula": {
        "window": "#282a36",
        "window_alt": "#21222c",
        "surface": "#2f3241",
        "surface_alt": "#383a4c",
        "surface_hover": "#44475a",
        "border": "#44475a",
        "text": "#f8f8f2",
        "muted": "#bdc0d4",
        "accent": "#bd93f9",
        "accent_text": "#21222c",
        "danger": "#ff5555",
        "success": "#50fa7b",
        "warning": "#f1fa8c",
    },
    "nord": {
        "window": "#2e3440",
        "window_alt": "#292e39",
        "surface": "#343b49",
        "surface_alt": "#3b4252",
        "surface_hover": "#434c5e",
        "border": "#4c566a",
        "text": "#eceff4",
        "muted": "#aeb8c8",
        "accent": "#88c0d0",
        "accent_text": "#2e3440",
        "danger": "#bf616a",
        "success": "#a3be8c",
        "warning": "#ebcb8b",
    },
}


def palette_for(theme_id: str) -> dict[str, str]:
    """Return the semantic palette shared by every themed component."""
    palette = dict(THEMES.get(theme_id, THEMES["dark"]))
    palette.update({
        "focus": palette["accent"],
        "disabled": palette["muted"],
        "error": palette["danger"],
        "selection": palette["surface_hover"],
        "info": palette["accent"],
    })
    return palette


DESIGN_TOKENS: dict[str, dict[str, int]] = {
    "spacing": {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "xxl": 32},
    "radius": {"sm": 6, "md": 8, "lg": 12, "xl": 16},
    "animation": {"fast": 100, "normal": 160, "slow": 240},
}


def tokens_for(group: str) -> dict[str, int]:
    """Return a copy of shared spacing, radius or animation design tokens."""
    return dict(DESIGN_TOKENS.get(group, {}))


def _rgba(hex_color: str, alpha: float) -> str:
    color = QColor(hex_color)
    if not color.isValid():
        color = QColor("#68a9ff")
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {alpha:.2f})"


def _readable_on(color_name: str) -> str:
    """Choose whichever of near-black or white has stronger WCAG contrast."""
    color = QColor(color_name)
    if not color.isValid():
        return "#ffffff"

    def linear(channel: int) -> float:
        value = channel / 255.0
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    luminance = (
        0.2126 * linear(color.red())
        + 0.7152 * linear(color.green())
        + 0.0722 * linear(color.blue())
    )
    white_contrast = 1.05 / (luminance + 0.05)
    dark_contrast = (luminance + 0.05) / 0.05
    return "#10151d" if dark_contrast >= white_contrast else "#ffffff"


def build_stylesheet(config: ConfigManager) -> str:
    """Return the QSS for the configured theme, accent and typography."""
    theme_id = config.get("appearance.theme", "dark")
    palette = palette_for(theme_id)
    accent = QColor(str(config.get("appearance.accent", palette["accent"])))
    if not accent.isValid():
        accent = QColor(palette["accent"])
    accent_hex = accent.name()
    accent_text = _readable_on(accent_hex)
    font_family = str(config.get("appearance.font_family", "Segoe UI") or "Segoe UI")
    font_size = int(config.get("appearance.font_size", 13) or 13)
    radius = int(config.get("appearance.corner_radius", 14) or 14)
    selection = _rgba(accent_hex, 0.22)
    selection_strong = _rgba(accent_hex, 0.32)

    window = palette["window"]
    surface = palette["surface"]
    surface_alt = palette["surface_alt"]
    border = palette["border"]
    text = palette["text"]
    muted = palette["muted"]

    return f"""
* {{
    font-family: "{font_family}", "Segoe UI", "Inter", "Helvetica Neue", sans-serif;
    font-size: {font_size}pt;
    outline: none;
}}
QWidget {{
    color: {text};
    background: transparent;
}}
QMainWindow, QDialog, QWidget#WindowRoot, QWidget#PageRoot {{
    background: {window};
}}
QWidget#LauncherRoot {{
    background: {window};
    border: 1px solid {border};
    border-radius: {radius}px;
}}
QWidget#HeaderBar {{
    background: transparent;
    border-bottom: 1px solid {border};
}}
QLabel {{
    background: transparent;
    color: {text};
}}
QLabel#Muted {{ color: {muted}; }}
QLabel#Title {{ font-size: {font_size + 2}px; font-weight: 600; }}
QLabel#Heading {{ font-size: {font_size + 6}px; font-weight: 700; }}
QLabel#AppName {{ font-size: {font_size + 4}px; font-weight: 700; letter-spacing: 1px; }}
QLabel#BrandMark {{
    background: {accent_hex};
    color: {accent_text};
    border-radius: 9px;
    font-weight: 700;
    font-size: {font_size + 2}px;
}}
QLabel#Badge {{
    color: {accent_text};
    background: {accent_hex};
    border-radius: 8px;
    padding: 2px 8px;
    font-size: {max(9, font_size - 2)}px;
    font-weight: 600;
}}
QLabel#CategoryChip {{
    color: {muted};
    background: {_rgba(accent_hex, 0.10)};
    border: 1px solid {_rgba(accent_hex, 0.22)};
    border-radius: 8px;
    padding: 2px 8px;
    font-size: {max(9, font_size - 2)}px;
}}
QLabel#ResultGlyph {{
    background: {_rgba(accent_hex, 0.12)};
    border: 1px solid {_rgba(accent_hex, 0.22)};
    border-radius: 9px;
    font-size: {font_size + 2}px;
}}
QLabel#Kbd {{
    color: {muted};
    background: {surface_alt};
    border: 1px solid {border};
    border-radius: 5px;
    padding: 1px 6px;
    font-size: {max(9, font_size - 2)}px;
}}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit {{
    background: {surface_alt};
    color: {text};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 7px 10px;
    selection-background-color: {selection_strong};
    selection-color: {text};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus,
QPlainTextEdit:focus, QTextEdit:focus {{
    border: 1px solid {accent_hex};
}}
QLineEdit#SearchInput {{
    background: transparent;
    border: none;
    font-size: {font_size + 5}px;
    padding: 4px 6px;
}}
QLineEdit#SearchInput:focus {{ border: none; }}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background: {surface};
    color: {text};
    border: 1px solid {border};
    border-radius: 8px;
    selection-background-color: {selection_strong};
    padding: 4px;
}}
QPushButton {{
    background: {surface_alt};
    color: {text};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 7px 14px;
}}
QPushButton:hover {{ background: {palette['surface_hover']}; }}
QPushButton:pressed {{ background: {surface}; }}
QPushButton:disabled {{ color: {muted}; }}
QPushButton:focus, QToolButton:focus, QListWidget:focus,
QTableWidget:focus, QTreeWidget:focus {{
    border: 2px solid {palette['focus']};
}}
QPushButton#Primary {{
    background: {accent_hex};
    color: {accent_text};
    border: 1px solid {accent_hex};
    font-weight: 600;
}}
QPushButton#Primary:hover {{ background: {QColor(accent_hex).lighter(112).name()}; }}
QPushButton#Danger {{
    background: transparent;
    color: {palette['danger']};
    border: 1px solid {_rgba(palette['danger'], 0.5)};
}}
QPushButton#Danger:hover {{ background: {_rgba(palette['danger'], 0.14)}; }}
QToolButton {{
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 4px;
    color: {muted};
}}
QToolButton:hover {{ background: {surface_alt}; color: {text}; }}
QListWidget, QTreeWidget, QTableWidget, QListView, QTableView {{
    background: transparent;
    border: none;
    color: {text};
    selection-background-color: {selection};
    alternate-background-color: {surface_alt};
}}
QListWidget#ResultList::item {{
    background: transparent;
    border: none;
    margin: 0;
    padding: 0;
}}
QListWidget#ResultList::item:selected {{
    background: {selection};
    border-radius: 10px;
}}
QListWidget#ResultList::item:hover:!selected {{
    background: {_rgba(palette['text'], 0.05)};
    border-radius: 10px;
}}
QListWidget#Sidebar {{
    background: {palette['window_alt']};
    border-right: 1px solid {border};
    padding: 10px 8px;
}}
QListWidget#Sidebar::item {{
    padding: 9px 12px;
    border-radius: 8px;
    margin: 1px 2px;
    color: {muted};
}}
QListWidget#Sidebar::item:selected {{
    background: {selection_strong};
    color: {text};
    font-weight: 600;
}}
QListWidget#Sidebar::item:hover:!selected {{ background: {surface_alt}; color: {text}; }}
QListWidget#PlainList::item {{
    padding: 7px 10px;
    border-radius: 7px;
    margin: 1px 0;
}}
QListWidget#PlainList::item:selected {{ background: {selection_strong}; }}
QListWidget#PlainList::item:hover:!selected {{ background: {surface_alt}; }}
QTableWidget {{
    gridline-color: {border};
    selection-background-color: {selection_strong};
    border: 1px solid {border};
    border-radius: 10px;
}}
QHeaderView::section {{
    background: {surface_alt};
    color: {muted};
    border: none;
    border-bottom: 1px solid {border};
    padding: 6px 8px;
    font-weight: 600;
}}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{
    background: transparent;
    color: {muted};
    padding: 8px 14px;
    border-radius: 8px;
    margin-right: 4px;
}}
QTabBar::tab:selected {{ background: {selection_strong}; color: {text}; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {_rgba(muted, 0.35)};
    border-radius: 5px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{ background: {_rgba(accent_hex, 0.6)}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {_rgba(muted, 0.35)};
    border-radius: 5px;
    min-width: 28px;
}}
QFrame#Card {{
    background: {surface};
    border: 1px solid {border};
    border-radius: 12px;
}}
QFrame#Row {{
    background: transparent;
    border-bottom: 1px solid {_rgba(border, 0.6)};
}}
QFrame#Divider {{ background: {border}; max-height: 1px; border: none; }}
QCheckBox, QRadioButton {{ spacing: 8px; color: {text}; }}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 17px;
    height: 17px;
    border-radius: 5px;
    border: 1px solid {border};
    background: {surface_alt};
}}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background: {accent_hex};
    border: 1px solid {accent_hex};
}}
QSlider::groove:horizontal {{
    height: 5px;
    background: {surface_alt};
    border-radius: 3px;
}}
QSlider::sub-page:horizontal {{ background: {accent_hex}; border-radius: 3px; }}
QSlider::handle:horizontal {{
    width: 15px;
    height: 15px;
    margin: -6px 0;
    border-radius: 8px;
    background: {accent_hex};
}}
QProgressBar {{
    background: {surface_alt};
    border: none;
    border-radius: 4px;
    height: 7px;
    text-align: center;
}}
QProgressBar::chunk {{ background: {accent_hex}; border-radius: 4px; }}
QMenu {{
    background: {surface};
    color: {text};
    border: 1px solid {border};
    border-radius: 9px;
    padding: 6px;
}}
QMenu::item {{ padding: 7px 26px 7px 14px; border-radius: 6px; }}
QMenu::item:selected {{ background: {selection_strong}; }}
QMenu::separator {{ height: 1px; background: {border}; margin: 5px 8px; }}
QToolTip {{
    background: {surface};
    color: {text};
    border: 1px solid {border};
    border-radius: 6px;
    padding: 5px 8px;
}}
QSplitter::handle {{ background: {border}; }}
QGroupBox {{
    border: 1px solid {border};
    border-radius: 10px;
    margin-top: 14px;
    padding: 10px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
    color: {muted};
}}
QCalendarWidget QWidget {{ background: {surface}; }}
QStatusBar {{ background: {palette['window_alt']}; color: {muted}; }}
"""


def apply_theme(app: QApplication, config: ConfigManager) -> None:
    """Apply the theme stylesheet, palette and global motion preference."""
    app.setProperty("seekrAnimationsEnabled", bool(config.get("appearance.animations", True)))
    stylesheet = build_stylesheet(config)
    app.setStyleSheet(stylesheet)
    palette = palette_for(config.get("appearance.theme", "dark"))
    accent = QColor(str(config.get("appearance.accent", palette["accent"])))
    if not accent.isValid():
        accent = QColor(palette["accent"])
    qt_palette = QPalette()
    qt_palette.setColor(QPalette.ColorRole.Window, QColor(palette["window"]))
    qt_palette.setColor(QPalette.ColorRole.WindowText, QColor(palette["text"]))
    qt_palette.setColor(QPalette.ColorRole.Base, QColor(palette["surface_alt"]))
    qt_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(palette["surface"]))
    qt_palette.setColor(QPalette.ColorRole.Text, QColor(palette["text"]))
    qt_palette.setColor(QPalette.ColorRole.Button, QColor(palette["surface_alt"]))
    qt_palette.setColor(QPalette.ColorRole.ButtonText, QColor(palette["text"]))
    qt_palette.setColor(QPalette.ColorRole.Highlight, accent)
    qt_palette.setColor(QPalette.ColorRole.HighlightedText, QColor(_readable_on(accent.name())))
    qt_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(palette["surface"]))
    qt_palette.setColor(QPalette.ColorRole.ToolTipText, QColor(palette["text"]))
    qt_palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(palette["muted"]))
    app.setPalette(qt_palette)


__all__: list[Any] = ["THEMES", "palette_for", "DESIGN_TOKENS", "tokens_for", "build_stylesheet", "apply_theme"]
